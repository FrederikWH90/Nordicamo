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

Fast, temporary rollback to any checkpoint, commit or branch:

```bash
cd /home/frede/NAMO_nov25
./server/deploy/rollback.sh production checkpoint/2026-09-26-pre-redesign
```

This leaves production on a "detached" version. To make the rollback
permanent, revert the change on `main` (GitHub: open the merged pull request
and press **Revert**), then run `deploy_production.sh`. To go forward again,
just run `deploy_production.sh`.

Staging works the same way: `./server/deploy/rollback.sh staging <ref>`.

## 5. Compare two versions

```bash
git diff checkpoint/2026-09-26-pre-redesign redesign/live-observatory -- frontend/
```

Or on GitHub:
`https://github.com/Frederikmh90/NAMO/compare/checkpoint/2026-09-26-pre-redesign...redesign/live-observatory`
