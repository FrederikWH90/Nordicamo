#!/usr/bin/env bash
set -euo pipefail

# Deploy frontend staging from a branch, tag or commit.
# Staging is a separate git worktree, so production's checkout is never touched.
# Usage:
#   ./server/deploy/deploy_staging.sh <branch|tag|commit>

PROD_ROOT="/home/frede/NAMO_nov25"
STAGING_ROOT="/home/frede/NAMO_nov25_staging"
REF="${1:-}"

if [[ -z "$REF" ]]; then
  echo "Usage: $0 <branch|tag|commit>"
  exit 1
fi

if [[ ! -e "$STAGING_ROOT/.git" ]]; then
  echo "Creating staging worktree at $STAGING_ROOT"
  git -C "$PROD_ROOT" worktree add --detach "$STAGING_ROOT" origin/main
fi

cd "$STAGING_ROOT"
git fetch origin --tags --prune
if git rev-parse --verify --quiet "origin/$REF" >/dev/null; then
  git checkout --detach "origin/$REF"
else
  git checkout --detach "$REF"
fi

systemctl --user restart nordicamo-frontend-staging.service
sleep 5
curl -fsS -m 5 http://127.0.0.1:8502/_stcore/health >/dev/null

echo "OK: staging now at $(git log --oneline -1) and healthy on :8502"
echo "Production checkout untouched: $(git -C "$PROD_ROOT" log --oneline -1)"
