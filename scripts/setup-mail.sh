#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
need_cmd(){ command -v "$1" >/dev/null 2>&1 || { echo "Fehlt: $1"; exit 1; }; }
need_cmd docker
if [ "${EUID:-$(id -u)}" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi
DOMAIN="${AI3_DOMAIN:-$(grep '^AI3_DOMAIN=' .env 2>/dev/null | cut -d= -f2- || true)}"
DOMAIN="${DOMAIN:-localhost}"

printf '%s\n' "========================================" " AI3 — EIGENER MAILSERVER" "========================================" "Domain: $DOMAIN"

docker network inspect ai3-public >/dev/null 2>&1 || docker network create ai3-public >/dev/null

echo "[1/4] Starte eigenen Mailserver ..."
docker compose -f mail/docker-compose.yml up -d

echo "[2/4] Warte auf Mailserver ..."
for _ in $(seq 1 60); do
  if curl -fsS --max-time 3 "http://127.0.0.1:8081/" >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -fsS --max-time 10 "http://127.0.0.1:8081/" >/dev/null 2>&1 || echo "Hinweis: Webmail/Admin ist noch nicht bereit; Container läuft weiter."

echo "[3/4] Öffne Mailports in UFW (falls bereits vorhanden/aktiv) ..."
if command -v ufw >/dev/null 2>&1; then
  for p in 25 465 587 110 143 993 995 4190; do $SUDO ufw allow "$p/tcp" >/dev/null || true; done
fi

echo "[4/4] Mail-Diagnose ..."
if [ -x scripts/mail-check.sh ]; then scripts/mail-check.sh "$DOMAIN" || true; fi

echo
printf '%s\n' "Mailserver läuft selbst gehostet." "Webmail/Admin: https://mail.$DOMAIN" "SMTP: 25 / 465 / 587" "IMAP: 143 / 993" "POP3: 110 / 995" "Sieve: 4190" "" "Öffentliche Mailzustellung benötigt öffentliche DNS-Einträge, PTR/rDNS und eine nicht blockierte TCP/25-Verbindung." "========================================"
