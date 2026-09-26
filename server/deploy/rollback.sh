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
  staging)    ROOT="$STAGING_ROOT"; SERVICE="nordicamo-backend-staging.service nordicamo-frontend-staging.service"; PORT=8502 ;;
  production) ROOT="$PROD_ROOT";    SERVICE="nordicamo-frontend.service";         PORT=8501 ;;
  *) echo "First argument must be 'staging' or 'production'."; exit 1 ;;
esac

cd "$ROOT"
git fetch origin --tags --prune
git checkout --detach "$REF"

systemctl --user restart $SERVICE
sleep 5
curl -fsS -m 5 "http://127.0.0.1:$PORT/_stcore/health" >/dev/null
echo "OK: $TARGET rolled back to $(git log --oneline -1) and healthy on :$PORT"
if [[ "$TARGET" == "production" ]]; then
  echo "Production is now on a detached ref. Run ./server/deploy/deploy_production.sh to return to main."
fi
