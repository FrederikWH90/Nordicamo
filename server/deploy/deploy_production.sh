#!/usr/bin/env bash
set -euo pipefail

# Deploy production frontend from main branch.
# Usage:
#   ./server/deploy/deploy_production.sh

ROOT="/home/frede/NAMO_nov25"

cd "$ROOT"
git fetch origin
git checkout main
git pull --ff-only origin main

active_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$active_branch" != "main" ]]; then
  echo "Refusing production deploy: active branch is '$active_branch', expected 'main'."
  exit 1
fi

systemctl --user daemon-reload
systemctl --user restart nordicamo-backend.service nordicamo-frontend.service
sleep 6
curl -fsS -m 5 http://127.0.0.1:8001/health | grep -q '"healthy"'
curl -fsS -m 5 http://127.0.0.1:8501/_stcore/health >/dev/null

echo "OK: production deployed from main and healthy on :8501"
