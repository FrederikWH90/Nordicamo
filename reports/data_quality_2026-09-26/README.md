# Data-quality audit — 26 Sep 2026

Scope: every row in `clean_articles` (the analysis-ready view behind the dashboard), 763,624 rows.
Read-only: run with a session temp table; nothing in the database was changed.
Scripts: `dq_audit.sql` (six broad checks) and `dq_classify.sql` (one category per row), both in this folder.

## Result

**605,645 rows (79.3%) look like normal articles.** The rest:

| Category | Rows | % | What it is | Suggested action |
|---|---:|---:|---|---|
| A. Paywall page | 38,039 | 5.0 | Syre's "Tack för att du läser – så här läser du vidare!" page stored as an article | Exclude |
| B. Same text under many titles | 17,456 | 2.3 | Body text is a cookie banner, browser warning, paywall notice, site footer — or another article's text (scraper grabbed a sidebar) | Exclude text; re-scrape if titles/dates are wanted |
| C. Non-article page | 19,739 | 2.6 | Tag/category/author/archive listings and WordPress image-attachment pages | Exclude |
| D. Teaser only | 80,254 | 10.5 | Real article, but only the free lead paragraph + "log in to read on" | Keep, flag as teaser; strip the appended paywall text |
| E. Near-empty | 2,491 | 0.3 | Under 150 characters of text | Exclude |
| Garbled text (overlaps) | 16,538 | — | UTF-8 decoded twice ("lÃ¦rer"): document.no 15,185, riks.se 1,321 | Repair in DB (reversible byte fix) |

Unusable (A+B+C+E) = 77,725 rows (10.2%). By country: Sweden 19.9%, Denmark 4.3%, Finland 3.2%, Norway 2.9%.
Teasers are concentrated in Norway (72,042 rows, almost all document.no).

## Worst-affected outlets

| Outlet | Rows | Unusable | Teaser | Main problem (verified by sampling) |
|---|---:|---:|---:|---|
| tidningensyre.se | 42,322 | 91% | — | Paywall page; the rest is a cookie banner as body text |
| swebbtv.se | 3,374 | 97% | — | "PeerTube: incompatible browser" / "JavaScript disabled" as body text |
| arbetaren.se | 1,063 | 72% | 3% | Site footer (address, GDPR text) as body text |
| hemali.no | 1,529 | 59% | — | Tag pages ("Dyr Arkiver") |
| insikt24.se | 658 | 57% | — | "Det här innehållet är låst" (locked content) |
| nyadagbladet.se | 29,400 | 54% | — | 14,239 image-attachment pages; ~1,300 rows carry another article's text; donation banner |
| redox.dk | 891 | 49% | — | Cookie banner as body text; tag pages |
| solidaritet.dk | 6,270 | 24% | — | Cookie banner; tag/archive pages |
| frihetskamp.no | 16,997 | 20% | — | 3,082 tag pages ("Stikkord: …") |
| radikalpolitikk.no | 3,332 | 15% | — | Site tagline as body text |
| denkorteavis.dk | 23,817 | 14% | — | Cookie banner as body text (3,344 rows; titles are real) |
| nyatider.nu | 15,036 | 13% | 37% | "Artikeln fortsätter… logga in" paywall |
| document.no | 107,789 | 0.5% | 64% | Teasers ("Logg inn for å lese videre") + 14% garbled text |
| mvlehti.net | 50,000 | 5% | — | UMV-Premium paywall text |
| samnytt.se | 24,372 | ~1% | ~9% | "Samnytt PLUS" teasers |

Full per-outlet table: `dq_final_by_outlet.csv`. Five random rows per outlet and category for manual review: `dq_final_samples_for_review.csv`.

## What this changes in the dashboard

- Sweden's article totals, Syre's position as Sweden's largest outlet, Sweden's Left share and the "Technology" topic spike are all inflated by category A/B rows.
- Topic tags for B and D rows were computed from boilerplate or lead paragraphs only.
- Nya Dagbladet's volume is roughly double its real article count.

## Not covered

- Cross-outlet duplicates (syndicated articles) and near-duplicates with small edits.
- Wrong publication dates (partly covered by existing `date_inferred` / `bulk_date_artifact` flags).
- Language mismatches.

## Applied on 26 Sep 2026

Script: `scripts/flag_data_quality.py` (tests: `scripts/tests/test_flag_data_quality.py`). Two runs:

| Run id | Flagged | Teasers recorded + trimmed | Titles repaired | Texts repaired |
|---|---:|---:|---:|---:|
| `dq-2026-09-26-initial` | 136,032 | 110,161 | 12,961 | 20,178 |
| `dq-2026-09-26-teasers` | 0 | 9,683 (paywall phrase was garbled before the repair) | 0 | 0 |

Flags cover the whole raw table; 77,816 of them were visible in `clean_articles`.
A third pass changes nothing (idempotent). Before/after per-outlet counts: `~/namo_backups/clean_counts_{before,after}_dq_20260926.csv` on the server.

| Country | Before | After | Removed |
|---|---:|---:|---:|
| Denmark | 138,181 | 132,264 | 4.3% |
| Finland | 114,055 | 110,384 | 3.2% |
| Norway | 198,437 | 192,590 | 2.9% |
| Sweden | 312,951 | 250,570 | 19.9% |
| **Total** | **763,624** | **685,808** | **10.2%** |

Rule adjustment after sampling: a repeated title only counts as a junk page when the text is also mostly identical,
so recurring columns (e.g. newspeek.info "BLANDEDE BOLSJER", 303 distinct texts) are kept.

Undo a run on the server:

```bash
cd /home/frede/NAMO_nov25 && DB_PASSWORD=namo_password /usr/bin/python3 scripts/flag_data_quality.py --revert dq-2026-09-26-initial
```

New tables: `data_quality_change_log` (every change, with old value) and `article_content_status` (teasers).
Weekly pipeline hook: `server/pipeline/weekly_data_quality_step.patch` (not yet applied — needs approval).
