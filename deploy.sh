#!/bin/bash
# deploy.sh — sync ЖК Lakeview static site + PHP backend to production
# Usage:
#   SSHPASS='your-password' SFTP_USER=uj593106 SFTP_HOST=uj593106.ftp.tools ./deploy.sh
# Or, store creds in .deploy-env (gitignored):
#   source .deploy-env && ./deploy.sh
#
# What it does:
#   1. (first run only) Backups existing WordPress to ~/lakeview.com.ua/www-wp-backup
#   2. rsync --delete syncs local files to ~/lakeview.com.ua/www/ (respects .deployignore)
#   3. Uploads api/config.php separately (gitignored, contains Telegram token)
#   4. Sets perms, runs smoke test

set -euo pipefail

# Load .deploy-env if present
[ -f .deploy-env ] && source .deploy-env

: "${SSHPASS:?Set SSHPASS env var (or .deploy-env)}"
SFTP_USER="${SFTP_USER:-uj593106}"
SFTP_HOST="${SFTP_HOST:-uj593106.ftp.tools}"
DOCROOT="lakeview.com.ua/www"
DOMAIN="https://www.lakeview.com.ua"

if ! command -v sshpass >/dev/null; then echo "Install sshpass: brew install hudochenkov/sshpass/sshpass"; exit 1; fi
if ! command -v rsync >/dev/null;  then echo "rsync required"; exit 1; fi
[ -f api/config.php ] || { echo "api/config.php missing locally — needed for production"; exit 1; }

SSH_OPTS='-o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 -o ServerAliveInterval=10'
sftp_ssh() { sshpass -e ssh $SSH_OPTS "${SFTP_USER}@${SFTP_HOST}" "$@"; }

echo "▶ Backup check + docroot prep..."
TS=$(date +%Y%m%d-%H%M%S)
sftp_ssh "
  set -e
  cd \$HOME/lakeview.com.ua
  if [ -d www ] && [ -f www/wp-config.php ]; then
    if [ -d www-wp-backup ]; then
      mv www-wp-backup www-wp-backup-old-${TS}
      echo 'Renamed previous backup → www-wp-backup-old-${TS}'
    fi
    mv www www-wp-backup
    echo 'WordPress backed up: www → www-wp-backup'
  fi
  mkdir -p www
"

echo "▶ Syncing site files (incl. api/config.php with real secrets)..."
sshpass -e rsync -avz --delete --delete-excluded \
  -e "ssh $SSH_OPTS" \
  --exclude-from=.deployignore \
  ./ "${SFTP_USER}@${SFTP_HOST}:~/${DOCROOT}/"

echo "▶ Setting permissions..."
sftp_ssh "
  cd \$HOME/${DOCROOT}
  chmod 600 api/config.php
  chmod 755 logs api
  [ -f logs/.gitkeep ] && chmod 644 logs/.gitkeep
  echo '--- Key files on host ---'
  ls -la index.html api/submit.php api/config.php logs/.htaccess .htaccess 2>&1 | head -10
"

echo "▶ Smoke test..."
sleep 2
HTTP=$(curl -s -o /tmp/deploy-smoke.html -w '%{http_code}' "${DOMAIN}/")
echo "  HTTP ${HTTP}"
TITLE=$(grep -o '<title>[^<]*</title>' /tmp/deploy-smoke.html | head -1)
echo "  ${TITLE}"

curl -s -o /dev/null -w "  /thanks.html: HTTP %{http_code}\n" "${DOMAIN}/thanks.html"
curl -s -o /dev/null -w "  /privacy.html: HTTP %{http_code}\n" "${DOMAIN}/privacy.html"
curl -s -o /dev/null -w "  /robots.txt: HTTP %{http_code}\n" "${DOMAIN}/robots.txt"
curl -s -o /dev/null -w "  /sitemap.xml: HTTP %{http_code}\n" "${DOMAIN}/sitemap.xml"
curl -s -o /dev/null -w "  /favicon.svg: HTTP %{http_code}\n" "${DOMAIN}/favicon.svg"
curl -s -o /dev/null -w "  /llms.txt: HTTP %{http_code}\n" "${DOMAIN}/llms.txt"

echo
echo "✓ Deploy complete: ${DOMAIN}/"
