#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
need_cmd(){ command -v "$1" >/dev/null 2>&1 || { echo "Fehlt: $1"; exit 1; }; }
need_cmd docker
DOMAIN="${AI3_DOMAIN:-$(grep '^AI3_DOMAIN=' .env 2>/dev/null | cut -d= -f2- || true)}"
DOMAIN="${DOMAIN:-localhost}"
if [ "$DOMAIN" = "localhost" ]; then
  echo "Lokaler Mailbetrieb: mail.localhost"
else
  echo "Öffentlicher Mailbetrieb: mail.$DOMAIN"
fi

docker network inspect ai3-public >/dev/null 2>&1 || docker network create ai3-public >/dev/null

echo "[1/3] Starte eigenen Mailserver ..."
docker compose -f mail/docker-compose.yml up -d

echo "[2/3] Öffne Mailports in UFW (falls vorhanden) ..."
if command -v ufw >/dev/null 2>&1; then
  for p in 25 465 587 110 143 993 995 4190; do sudo ufw allow "$p/tcp" >/dev/null || true; done
fi

echo "[3/3] Mail-Diagnose ..."
if [ -x scripts/mail-check.sh ]; then scripts/mail-check.sh "$DOMAIN" || true; fi

echo
printf '%s\n' "========================================" " AI3 MAILSERVER AKTIV" "========================================" "Webmail/Admin: https://mail.$DOMAIN" "SMTP: 25 / 465 / 587" "IMAP: 143 / 993" "POP3: 110 / 995" "Sieve: 4190" "" "Beim ersten Aufruf den Mailserver-Administrator im Webinterface einrichten." "Für öffentliche Zustellung müssen MX, A/AAAA, PTR/rDNS, SPF, DKIM und DMARC stimmen." "========================================"
