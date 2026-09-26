# Versions, checkpoints and rollback

How to save a version of the dashboard, try new versions on staging, and go
back and forth between them. GitHub (`origin`) holds every version.

## The three words you need

| Term | What it is | Example |
|---|---|---|
| **Branch** | A line of work in progress. `main` is what production runs. | `redesign/live-observatory` |
| **Checkpoint tag** | A permanent, named bookmark on one exact version. Never moves. | `checkpoint/2026-09-26-pre-redesign` |
| **Commit** | One saved change. Every commit has a short id. | `559cb34` |

Any of these can be deployed or rolled back to.

## Where things run on the server

| Environment | Code path | Service | Port |
|---|---|---|---|
| Production (nordicamo.org) | `/home/frede/NAMO_nov25` (always `main`) | `nordicamo-frontend.service` | 8501 |
| Staging | `/home/frede/NAMO_nov25_staging` (git worktree) | `nordicamo-frontend-staging.service` | 8502 |
| Production backend | `/home/frede/NAMO_nov25/backend` | `nordicamo-backend.service` | 8001 |
| Staging backend | `/home/frede/NAMO_nov25_staging/backend` | `nordicamo-backend-staging.service` | 8021 |

Staging is a separate git worktree with its own frontend and backend, so
switching staging to another version never touches production. Both backends
read the same database: a database change is a production change. The staging
backend has no email credentials, so access requests sent from staging are
stored, not emailed.

## 1. Save the current version (checkpoint)

On your laptop, from the repo root:

```bash
git fetch origin
git tag -a checkpoint/$(date +%F)-short-name origin/main -m "What this version is"
git push origin --tags
```

List all checkpoints:

```bash
git tag -l 'checkpoint/*' -n1
```

## 2. Try a version on staging

On the server:

```bash
ssh -p 2111 frede@212.27.13.34
cd /home/frede/NAMO_nov25
./server/deploy/deploy_staging.sh redesign/live-observatory      # a branch
./server/deploy/deploy_staging.sh checkpoint/2026-09-26-pre-redesign   # or a checkpoint
```

View it from your laptop:

```bash
ssh -p 2111 -L 8502:127.0.0.1:8502 frede@212.27.13.34
```

Then open http://127.0.0.1:8502.

## 3. Put a version live (production)

Production only ever runs `main`. To go live, merge the branch into `main` on
GitHub (pull request), then on the server:

```bash
cd /home/frede/NAMO_nov25
./server/deploy/deploy_production.sh
```

## 4. Go back (rollback)

The version production ran before the redesign is saved as
`checkpoint/2026-09-26-production-exact` (byte-identical to what was live).

Roll production back (restarts backend and frontend, checks both):

```bash
cd /home/frede/NAMO_nov25
./server/deploy/rollback.sh production checkpoint/2026-09-26-production-exact
```

Go forward again to the latest `main` (the script prints this command too,
because older versions don't contain the deploy scripts):

```bash
cd /home/frede/NAMO_nov25 && git checkout main && git pull --ff-only origin main && systemctl --user restart nordicamo-backend.service nordicamo-frontend.service
```

To make a rollback permanent, revert the change on `main` (GitHub: open the
merged pull request and press **Revert**), then run `deploy_production.sh`.

Staging works the same way: `./server/deploy/rollback.sh staging <ref>`.

### Code rollback does not undo database changes

Code and database are versioned separately. Older code works with the current
database, so a code rollback is always safe; database changes have their own undo:

| Database change | Effect if kept after a code rollback | Undo |
|---|---|---|
| Data-quality flags (26 Sep 2026) | Old pages show cleaned numbers | `DB_PASSWORD=... /usr/bin/python3 scripts/flag_data_quality.py --revert <run_id>` (run ids in `reports/data_quality_2026-09-26/README.md`) |
| Full-text index `idx_articles_fts_simple` | None (unused by old code) | `DROP INDEX CONCURRENTLY idx_articles_fts_simple;` |
| Tables `data_quality_change_log`, `article_content_status` | None | Keep: they are the undo log |

## 5. Compare two versions

```bash
git diff checkpoint/2026-09-26-pre-redesign redesign/live-observatory -- frontend/
```

Or on GitHub:
`https://github.com/Frederikmh90/NAMO/compare/checkpoint/2026-09-26-pre-redesign...redesign/live-observatory`
