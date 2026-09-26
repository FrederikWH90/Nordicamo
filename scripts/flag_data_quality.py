#!/usr/bin/env python3
"""Flag non-article and boilerplate rows so they drop out of clean_articles.

Runs after every weekly load (see run_weekly_server.sh, step 1d) and can be
re-run safely at any time:

- Only rows whose data_quality_flag is empty are considered, so existing
  manual or earlier flags are never overwritten.
- Every change is written to data_quality_change_log with a run id, and
  `--revert RUN_ID` undoes that run exactly.
- Without --apply it is a dry run: it prints what it would change.

Rules (generic, so future scrapes are caught too):
  dq_repeated_title_page  title repeated >= 200 times and >= 5% of an outlet's
                          rows with mostly identical text, or a known paywall title
  dq_boilerplate_body     identical body text under >= 5 different titles
                          (>= 20 rows) within one outlet: cookie banners,
                          browser warnings, paywall notices, site footers, or
                          another article's text grabbed from a sidebar
  dq_non_article_page     tag/category/author/archive listings, pagination,
                          WordPress attachment pages
  dq_near_empty           under 150 characters of text (recorded teasers excepted)

Teasers (real article, only the free lead is public) are kept: they are
recorded in article_content_status and the appended paywall text is cut off
via dashboard_content_overrides. Double-encoded UTF-8 ("nÃ¤r") in titles and
text is repaired, with the old value logged.

Audit that motivated these rules: reports/data_quality_2026-09-26/README.md
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import uuid

try:
    from psycopg2.extras import execute_values
except ImportError:  # pure helpers stay importable for tests
    execute_values = None

KNOWN_PAYWALL_TITLES = [
    "Tack för att du läser – så här läser du vidare!",  # tidningensyre.se
]

REPEATED_TITLE_MIN_COPIES = 200
REPEATED_TITLE_MIN_SHARE = 0.05
# A recurring column (same title, different text each time) is a real series, not a junk page.
REPEATED_TITLE_MAX_BODY_DIVERSITY = 0.2
BOILERPLATE_MIN_ROWS = 20
BOILERPLATE_MIN_TITLES = 5
NEAR_EMPTY_CHARS = 150

NON_ARTICLE_URL = (
    r"(/tag/|/tags/|/category/|/kategori/|/author/|/forfatter/|/skribent/"
    r"|/page/[0-9]+/?$|/side/[0-9]+/?$|/sida/[0-9]+/?$|/arkiv/?$|/archive/?$"
    r"|/attachment/|[?&]attachment_id=)"
)
NON_ARTICLE_TITLE = r"^(stikkord|kategori|forfatter|tag|tagg|avainsana)\s*:"

# Phrases where a paywall cuts the article off. Text from the phrase onwards is
# boilerplate; the lead before it is the real (teaser) article.
TEASER_CUT = (
    r"(logg inn for å lese videre|artikeln fortsätter|få tillgång till exklusivt material med samnytt plus"
    r"|för att fortsätta läsa|kun for abonnenter|log ind for at læse|vain tilaajille)"
)

_MOJIBAKE_PAIR = re.compile("[ÂÃ][\u0080-¿]|â€")
MOJIBAKE_SQL = "Ã[\u0080-¿]|â€"


# ---------------------------------------------------------------------------
# Pure helpers (unit tested)
# ---------------------------------------------------------------------------

def strip_paywall_tail(text: str | None) -> str | None:
    """Cut text at the first paywall phrase. Returns None when nothing to cut or no lead remains."""
    if not text:
        return None
    match = re.search(TEASER_CUT, text, flags=re.IGNORECASE)
    if not match:
        return None
    lead = text[: match.start()].rstrip()
    return lead or None


def repair_mojibake(text: str | None) -> str | None:
    """Undo UTF-8 decoded as Latin-1/cp1252. Returns None if nothing changed."""
    if not text or not _MOJIBAKE_PAIR.search(text):
        return None
    for codec in ("cp1252", "latin-1"):
        try:
            fixed = text.encode(codec).decode("utf-8")
            return fixed if fixed != text else None
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    # Partially damaged text: repair the pairs that decode, leave the rest.
    fixed = re.sub(
        "[ÂÃ][\u0080-¿]",
        lambda m: m.group().encode("latin-1").decode("utf-8"),
        text,
    )
    fixed = re.sub(r"(?<=\s)â(?=\s)", "–", fixed)
    return fixed if fixed != text else None


def is_non_article(url: str | None, title: str | None) -> bool:
    return bool(re.search(NON_ARTICLE_URL, url or "", re.IGNORECASE)) or bool(
        re.search(NON_ARTICLE_TITLE, (title or "").strip(), re.IGNORECASE)
    )


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

SETUP_SQL = """
CREATE TABLE IF NOT EXISTS data_quality_change_log (
    id bigserial PRIMARY KEY,
    run_id text NOT NULL,
    article_id bigint NOT NULL,
    field text NOT NULL,            -- data_quality_flag | content_override | title | content_status
    old_value text,
    new_value text,
    rule text NOT NULL,
    changed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS data_quality_change_log_run_idx ON data_quality_change_log (run_id);
CREATE TABLE IF NOT EXISTS article_content_status (
    article_id bigint PRIMARY KEY,
    status text NOT NULL,           -- teaser
    rule text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
"""

CANDIDATES_SQL = """
CREATE TEMP TABLE dq_base ON COMMIT DROP AS
SELECT a.id, regexp_replace(lower(a.domain), '^www\\.', '') AS outlet, a.url,
       coalesce(a.title, '') AS title,
       coalesce(o.content_clean, a.content, '') AS body,
       md5(coalesce(o.content_clean, a.content, '')) AS body_hash
FROM articles a
LEFT JOIN dashboard_content_overrides o ON o.article_id = a.id
WHERE a.data_quality_flag IS NULL OR a.data_quality_flag = '';

CREATE TEMP TABLE dq_outlet_n ON COMMIT DROP AS
SELECT outlet, count(*) AS n FROM dq_base GROUP BY 1;

CREATE TEMP TABLE dq_new_flags ON COMMIT DROP AS
WITH repeated_titles AS (
    SELECT b.outlet, b.title FROM dq_base b JOIN dq_outlet_n n USING (outlet)
    WHERE b.title <> ''
    GROUP BY b.outlet, b.title, n.n
    HAVING count(*) >= %(rt_copies)s AND count(*) >= %(rt_share)s * n.n
       AND count(DISTINCT b.body_hash) <= %(rt_max_diversity)s * count(*)
),
boilerplate AS (
    SELECT outlet, body_hash FROM dq_base WHERE length(body) > 0
    GROUP BY 1, 2 HAVING count(*) >= %(bp_rows)s AND count(DISTINCT title) >= %(bp_titles)s
)
SELECT b.id,
  CASE
    WHEN b.title = ANY(%(paywall_titles)s) OR rt.title IS NOT NULL THEN 'dq_repeated_title_page'
    WHEN bp.body_hash IS NOT NULL THEN 'dq_boilerplate_body'
    WHEN b.url ~* %(url_re)s OR b.title ~* %(title_re)s THEN 'dq_non_article_page'
    WHEN length(b.body) < %(near_empty)s AND NOT (b.body ~* %(teaser_re)s) AND s.article_id IS NULL THEN 'dq_near_empty'
  END AS flag
FROM dq_base b
LEFT JOIN repeated_titles rt ON rt.outlet = b.outlet AND rt.title = b.title
LEFT JOIN boilerplate bp ON bp.outlet = b.outlet AND bp.body_hash = b.body_hash
-- Trimmed teasers are short by design; never treat them as empty pages.
LEFT JOIN article_content_status s ON s.article_id = b.id;
DELETE FROM dq_new_flags WHERE flag IS NULL;
"""


def connect():
    import psycopg2

    return psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "namo_db"),
        user=os.getenv("DB_USER", "namo_user"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def run(apply: bool, run_id: str) -> None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(SETUP_SQL)
            cur.execute("SET LOCAL work_mem = '256MB'")
            cur.execute(
                CANDIDATES_SQL,
                {
                    "rt_copies": REPEATED_TITLE_MIN_COPIES,
                    "rt_share": REPEATED_TITLE_MIN_SHARE,
                    "rt_max_diversity": REPEATED_TITLE_MAX_BODY_DIVERSITY,
                    "bp_rows": BOILERPLATE_MIN_ROWS,
                    "bp_titles": BOILERPLATE_MIN_TITLES,
                    "paywall_titles": KNOWN_PAYWALL_TITLES,
                    "url_re": NON_ARTICLE_URL,
                    "title_re": NON_ARTICLE_TITLE,
                    "near_empty": NEAR_EMPTY_CHARS,
                    "teaser_re": TEASER_CUT,
                },
            )
            cur.execute(
                """SELECT regexp_replace(lower(a.domain), '^www\\.', ''), f.flag, count(*)
                   FROM dq_new_flags f JOIN articles a ON a.id = f.id
                   GROUP BY 1, 2 ORDER BY 3 DESC"""
            )
            flag_rows = cur.fetchall()
            total_flags = sum(r[2] for r in flag_rows)
            print(f"Rows to flag: {total_flags:,}")
            for outlet, flag, count in flag_rows[:40]:
                print(f"  {str(outlet):<28} {flag:<24} {count:>7,}")
            cur.execute(
                """SELECT f.flag, count(*) FROM dq_new_flags f JOIN clean_articles c ON c.id = f.id
                   GROUP BY 1 ORDER BY 2 DESC"""
            )
            visible = cur.fetchall()
            print(f"Of these, currently visible in clean_articles: {sum(r[1] for r in visible):,}")
            for flag, count in visible:
                print(f"  {flag:<24} {count:>7,}")

            # Teasers: among rows that stay visible, cut the paywall tail.
            cur.execute(
                """SELECT b.id, b.body FROM dq_base b
                   LEFT JOIN dq_new_flags f ON f.id = b.id
                   LEFT JOIN article_content_status s ON s.article_id = b.id
                   WHERE f.id IS NULL AND s.article_id IS NULL AND b.body ~* %s""",
                (TEASER_CUT,),
            )
            teasers = [(aid, strip_paywall_tail(body)) for aid, body in cur.fetchall()]
            teasers = [(aid, lead) for aid, lead in teasers if lead]
            print(f"Teasers to record and trim: {len(teasers):,}")

            # Garbled text among rows that stay visible.
            cur.execute(
                """SELECT b.id, b.title, b.body FROM dq_base b
                   LEFT JOIN dq_new_flags f ON f.id = b.id
                   WHERE f.id IS NULL AND (b.title ~ %s OR b.body ~ %s)""",
                (MOJIBAKE_SQL, MOJIBAKE_SQL),
            )
            garbled = cur.fetchall()
            print(f"Rows with garbled text to repair: {len(garbled):,}")

            if not apply:
                print("Dry run: nothing written. Re-run with --apply to write.")
                conn.rollback()
                return

            cur.execute(
                """INSERT INTO data_quality_change_log (run_id, article_id, field, old_value, new_value, rule)
                   SELECT %s, a.id, 'data_quality_flag', a.data_quality_flag, f.flag, f.flag
                   FROM dq_new_flags f JOIN articles a ON a.id = f.id""",
                (run_id,),
            )
            cur.execute(
                """UPDATE articles a SET data_quality_flag = f.flag
                   FROM dq_new_flags f WHERE a.id = f.id"""
            )

            trimmed = {aid: lead for aid, lead in teasers}
            overrides: dict[int, tuple[str, str]] = {aid: (lead, "teaser_trim") for aid, lead in teasers}
            title_fixes = []
            for aid, title, body in garbled:
                new_title = repair_mojibake(title)
                if new_title:
                    title_fixes.append((aid, title, new_title))
                new_body = repair_mojibake(trimmed.get(aid, body))
                if new_body:
                    rule = "teaser_trim+mojibake_repair" if aid in trimmed else "mojibake_repair"
                    overrides[aid] = (new_body, rule)

            _apply_overrides(cur, run_id, overrides)
            execute_values(
                cur,
                "INSERT INTO article_content_status (article_id, status, rule) VALUES %s ON CONFLICT (article_id) DO NOTHING",
                [(aid, "teaser", "teaser_cut_phrase") for aid, _ in teasers],
                page_size=5000,
            )
            _log_many(cur, run_id, [(aid, "content_status", None, "teaser", "teaser_cut_phrase") for aid, _ in teasers])
            _log_many(cur, run_id, [(aid, "title", old, new, "mojibake_repair") for aid, old, new in title_fixes])
            execute_values(
                cur,
                "UPDATE articles a SET title = v.title FROM (VALUES %s) AS v(id, title) WHERE a.id = v.id",
                [(aid, new) for aid, _, new in title_fixes],
                page_size=5000,
            )
            fixed_titles, fixed_bodies = len(title_fixes), sum(1 for _, r in overrides.values() if "mojibake" in r)
            conn.commit()
            print(f"Applied run {run_id}: {total_flags:,} flagged, {len(teasers):,} teasers, "
                  f"{fixed_titles:,} titles and {fixed_bodies:,} texts repaired.")
    finally:
        conn.close()


def _log_many(cur, run_id, rows) -> None:
    """rows: (article_id, field, old_value, new_value, rule)."""
    if rows:
        execute_values(
            cur,
            "INSERT INTO data_quality_change_log (run_id, article_id, field, old_value, new_value, rule) VALUES %s",
            [(run_id, *row) for row in rows],
            page_size=5000,
        )


def _apply_overrides(cur, run_id, overrides: dict) -> None:
    """Upsert dashboard_content_overrides, logging each previous value."""
    if not overrides:
        return
    cur.execute(
        "SELECT article_id, content_clean FROM dashboard_content_overrides WHERE article_id = ANY(%s)",
        (list(overrides),),
    )
    previous = dict(cur.fetchall())
    _log_many(cur, run_id, [
        (aid, "content_override", previous.get(aid), content, rule) for aid, (content, rule) in overrides.items()
    ])
    execute_values(
        cur,
        """INSERT INTO dashboard_content_overrides (article_id, content_clean) VALUES %s
           ON CONFLICT (article_id) DO UPDATE SET content_clean = EXCLUDED.content_clean, updated_at = now()""",
        [(aid, content) for aid, (content, _) in overrides.items()],
        page_size=5000,
    )


def revert(run_id: str) -> None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT article_id, field, old_value FROM data_quality_change_log
                   WHERE run_id = %s ORDER BY id DESC""",
                (run_id,),
            )
            changes = cur.fetchall()
            if not changes:
                print(f"No changes logged for run {run_id}.")
                return
            for aid, field, old in changes:
                if field == "data_quality_flag":
                    cur.execute("UPDATE articles SET data_quality_flag = %s WHERE id = %s", (old, aid))
                elif field == "title":
                    cur.execute("UPDATE articles SET title = %s WHERE id = %s", (old, aid))
                elif field == "content_status":
                    cur.execute("DELETE FROM article_content_status WHERE article_id = %s", (aid,))
                elif field == "content_override":
                    if old is None:
                        cur.execute("DELETE FROM dashboard_content_overrides WHERE article_id = %s", (aid,))
                    else:
                        cur.execute(
                            "UPDATE dashboard_content_overrides SET content_clean = %s WHERE article_id = %s",
                            (old, aid),
                        )
            cur.execute("DELETE FROM data_quality_change_log WHERE run_id = %s", (run_id,))
        conn.commit()
        print(f"Reverted run {run_id}: {len(changes):,} changes undone.")
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    parser.add_argument("--revert", metavar="RUN_ID", help="undo a previous run")
    parser.add_argument("--run-id", default=None, help="label for this run (default: random)")
    args = parser.parse_args(argv)
    if args.revert:
        revert(args.revert)
        return 0
    run(apply=args.apply, run_id=args.run_id or f"dq-{uuid.uuid4().hex[:10]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
