#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT_DIR"
need_cmd(){ command -v "$1" >/dev/null 2>&1 || { echo "Fehlt: $1"; exit 1; }; }
need_cmd docker; need_cmd curl; need_cmd python3; docker compose version >/dev/null
mkdir -p secrets
if [ ! -f secrets/ai3_data_encryption_key ]; then python3 - <<'PY' > secrets/ai3_data_encryption_key
import secrets
print(secrets.token_hex(32))
PY
fi
chmod 600 secrets/ai3_data_encryption_key
if [ ! -f .env ]; then
 ADMIN_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"; ADMIN_PASSWORD="$(python3 -c 'import secrets;print("AI3-"+secrets.token_urlsafe(18))')"
 cat > .env <<EOF
AI3_ADMIN_KEY=$ADMIN_KEY
AI3_ADMIN_PASSWORD=$ADMIN_PASSWORD
AI3_ADMIN_SESSION_HOURS=12
AI3_DOMAIN=${AI3_DOMAIN:-localhost}
AI3_PUBLIC_BASE_URL=${AI3_PUBLIC_BASE_URL:-https://${AI3_DOMAIN:-localhost}}
AI3_TLS_EMAIL=${AI3_TLS_EMAIL:-}
AI3_MAIL_ENABLED=1
AI3_MAIL_DOMAIN=${AI3_MAIL_DOMAIN:-${AI3_DOMAIN:-localhost}}
AI3_MAIL_HOST=${AI3_MAIL_HOST:-mail.${AI3_DOMAIN:-localhost}}
AI3_MODEL=llama3.2:3b
AI3_OLLAMA_URL=http://ollama:11434
AI3_LLM_BASE_URL=http://ollama:11434/v1
AI3_LLM_TIMEOUT=300
AI3_BACKEND=ollama
AI3_ENABLE_ADVANCED_SECURITY=1
AI3_ACCESS_TOKEN_MINUTES=15
AI3_REFRESH_TOKEN_DAYS=30
AI3_RATE_LIMIT_RPM=120
AI3_DAILY_REQUEST_LIMIT=0
AI3_DDOS_IP_RPM=120
AI3_DDOS_MAX_CONCURRENT_PER_IP=20
AI3_MAX_REQUEST_BYTES=2000000
AI3_MAX_CHAT_STORAGE_BYTES=2000000
AI3_DATA_ENCRYPTION_KEY_FILE=/run/secrets/ai3_data_key
AI3_PKI_DIR=/data/pki
AI3_VERIFICATION_MAX_BYTES=8388608
AI3_VERIFICATION_RETENTION_DAYS=30
AI3_BACKUP_DIR=/data/backups
EOF
 chmod 600 .env; echo "Admin-Passwort: $ADMIN_PASSWORD"
fi
ADMIN_KEY="$(grep '^AI3_ADMIN_KEY=' .env|cut -d= -f2-)"; MODEL="$(grep '^AI3_MODEL=' .env|cut -d= -f2-)"; DOMAIN="$(grep '^AI3_DOMAIN=' .env|cut -d= -f2-)"
docker network inspect ai3-public >/dev/null 2>&1 || docker network create ai3-public >/dev/null
COMPOSE_FILES=(-f docker-compose.yml)
if [ "${AI3_USE_GPU:-}" = "1" ]; then COMPOSE_FILES+=(-f docker-compose.gpu.yml); elif [ "${AI3_USE_GPU:-}" != "0" ] && command -v nvidia-smi >/dev/null 2>&1 && docker run --rm --gpus all nvidia/cuda:12.6.2-base-ubuntu24.04 nvidia-smi >/dev/null 2>&1; then COMPOSE_FILES+=(-f docker-compose.gpu.yml); fi
docker compose "${COMPOSE_FILES[@]}" up -d --build
chmod +x scripts/setup-mail.sh scripts/mail-check.sh 2>/dev/null || true
if [ "${AI3_MAIL_ENABLED:-1}" = "1" ]; then ./scripts/setup-mail.sh; fi
for _ in $(seq 1 90); do curl -kfsS https://localhost/health >/dev/null 2>&1 && break; sleep 2; done
curl -kfsS https://localhost/health >/dev/null
mkdir -p openclaw
curl -kfsS -X POST https://localhost/v1/principals -H "X-AI3-Admin-Key: $ADMIN_KEY" -H 'Content-Type: application/json' -d '{"name":"assistant-01","kind":"agent"}' >/dev/null || true
TOKEN_JSON="$(curl -kfsS -X POST https://localhost/v1/tokens -H "X-AI3-Admin-Key: $ADMIN_KEY" -H 'Content-Type: application/json' -d '{"principal":"assistant-01","name":"local","scopes":["ai:inference","agents:read"]}')"
TOKEN="$(printf '%s' "$TOKEN_JSON"|python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])')"
cat > openclaw/ai3-provider.generated.json5 <<EOF
{models:{mode:"merge",providers:{ai3:{baseUrl:"https://$DOMAIN/v1",apiKey:"$TOKEN",api:"openai-completions",timeoutSeconds:300,models:[{id:"$MODEL",name:"AI3 Local $MODEL",reasoning:false,input:["text"],cost:{input:0,output:0,cacheRead:0,cacheWrite:0},contextWindow:32768,maxTokens:8192}]}}},agents:{defaults:{model:{primary:"ai3/$MODEL"}}}}
EOF
chmod 600 openclaw/ai3-provider.generated.json5
curl -kfsS https://localhost/v1/pki/ca >/dev/null
printf '\nAI3 One-Click fertig: https://%s\nLokales Modell: %s\nHTTPS: automatisch\nEigene PKI: aktiv\nOwn Verification: aktiv\nEigener Mailserver: https://mail.%s\nMailports: 25,465,587,110,143,993,995,4190\nOpenClaw-Konfiguration: openclaw/ai3-provider.generated.json5\n' "$DOMAIN" "$MODEL" "$DOMAIN"
