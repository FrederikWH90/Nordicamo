#!/usr/bin/env bash
set -euo pipefail

# Roll back frontend code to a specific git ref (tag, commit or branch) and restart it.
# Usage:
#   ./server/deploy/rollback.sh <staging|production> <git-ref>
# List available checkpoints with:
#   git tag -l 'checkpoint/*'

PROD_ROOT="/home/frede/NAMO_nov25"
STAGING_ROOT="/home/frede/NAMO_nov25_staging"
TARGET="${1:-}"
REF="${2:-}"

if [[ -z "$TARGET" || -z "$REF" ]]; then
  echo "Usage: $0 <staging|production> <git-ref>"
  exit 1
fi

case "$TARGET" in
  staging)
    ROOT="$STAGING_ROOT"
    SERVICES="nordicamo-backend-staging.service nordicamo-frontend-staging.service"
    BACKEND_PORT=8021; FRONTEND_PORT=8502 ;;
  production)
    ROOT="$PROD_ROOT"
    SERVICES="nordicamo-backend.service nordicamo-frontend.service"
    BACKEND_PORT=8001; FRONTEND_PORT=8501 ;;
  *) echo "First argument must be 'staging' or 'production'."; exit 1 ;;
esac

cd "$ROOT"
git fetch origin --tags --prune
git checkout --detach "$REF"

# Backend and frontend together: releases can change both.
systemctl --user restart $SERVICES
sleep 6
curl -fsS -m 5 "http://127.0.0.1:$BACKEND_PORT/health" | grep -q '"healthy"'
curl -fsS -m 5 "http://127.0.0.1:$FRONTEND_PORT/_stcore/health" >/dev/null
echo "OK: $TARGET rolled back to $(git log --oneline -1); backend :$BACKEND_PORT and frontend :$FRONTEND_PORT healthy"
echo
echo "Older versions may not contain these deploy scripts. To go forward again, run:"
if [[ "$TARGET" == "production" ]]; then
  echo "  cd $ROOT && git checkout main && git pull --ff-only origin main && systemctl --user restart $SERVICES"
else
  echo "  cd $ROOT && git checkout --detach origin/<branch> && systemctl --user restart $SERVICES"
fi
