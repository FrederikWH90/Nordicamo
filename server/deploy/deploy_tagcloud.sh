#!/usr/bin/env bash
# Publish the tag cloud generator from the production checkout (main).
# Static files only; no service restart. Usage on the server:
#   cd /home/frede/NAMO_nov25 && git pull --ff-only origin main && ./server/deploy/deploy_tagcloud.sh
set -euo pipefail

SRC="/home/frede/NAMO_nov25/tagcloud"
WEBROOT="/var/www/nordicamo-tagcloud"

for f in index.html favicon.png css/style.css js/app.js js/core.js js/layout.js js/export.js js/stopwords.js js/example.js; do
  test -f "$SRC/$f" || { echo "Missing $SRC/$f"; exit 1; }
done
mkdir -p "$WEBROOT/css" "$WEBROOT/js"
# Only the published files: no tests, package.json or README.
cp "$SRC/index.html" "$SRC/favicon.png" "$WEBROOT/"
cp "$SRC/css/style.css" "$WEBROOT/css/"
cp "$SRC/js/"*.js "$WEBROOT/js/"
find "$WEBROOT" -type f -exec chmod 644 {} +
echo "OK: tag cloud published from $(git -C "$SRC/.." log --oneline -1)"
