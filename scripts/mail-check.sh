#!/usr/bin/env bash
set -euo pipefail
DOMAIN="${1:-${AI3_DOMAIN:-}}"
if [[ -z "$DOMAIN" || "$DOMAIN" == "localhost" ]]; then echo "AI3 mail-check: keine öffentliche Domain gesetzt."; exit 0; fi
for cmd in getent; do command -v "$cmd" >/dev/null || { echo "Fehlt: $cmd"; exit 1; }; done
echo "=== AI3 Mail-Diagnose: $DOMAIN ==="
echo "MX:"; getent ahosts "mail.$DOMAIN" || true
echo "Domain:"; getent ahosts "$DOMAIN" || true
echo "Hinweis: SPF, DKIM, DMARC, PTR/rDNS und Port 25 müssen beim eigenen DNS/Netz geprüft werden."
echo "AI3 selbst verwendet keinen externen SMTP-Anbieter."
