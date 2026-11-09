#!/usr/bin/env bash
# One-time setup for tagcloud.nordicamo.org. Run on the server with sudo:
#   sudo bash /home/frede/NAMO_nov25/server/tagcloud/setup_once.sh
# Prerequisite: a DNS A record tagcloud.nordicamo.org -> 212.27.13.34.
set -euo pipefail

SITE=tagcloud.nordicamo.org
WEBROOT=/var/www/nordicamo-tagcloud
OWNER=frede
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "1/4 Web folder $WEBROOT (owned by $OWNER, so updates need no sudo)"
mkdir -p "$WEBROOT"
chown "$OWNER":"$OWNER" "$WEBROOT"
chmod 755 "$WEBROOT"

echo "2/4 Copy the site files"
sudo -u "$OWNER" bash "$HERE/../deploy/deploy_tagcloud.sh"

echo "3/4 nginx site"
install -m 644 "$HERE/$SITE.conf" "/etc/nginx/sites-available/$SITE.conf"
ln -sf "/etc/nginx/sites-available/$SITE.conf" "/etc/nginx/sites-enabled/$SITE.conf"
nginx -t
systemctl reload nginx

echo "4/4 HTTPS certificate"
if getent hosts "$SITE" >/dev/null; then
  certbot --nginx -d "$SITE" --redirect --non-interactive --agree-tos --keep-until-expiring
else
  echo "DNS for $SITE does not resolve yet. Add the A record, then run:"
  echo "  sudo certbot --nginx -d $SITE --redirect"
fi
echo "Done: https://$SITE"
