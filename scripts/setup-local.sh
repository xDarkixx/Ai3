#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker ist nicht installiert. Bitte Docker Engine + Compose installieren."
  exit 1
fi

if [ ! -f .env ]; then
  ADMIN_KEY="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"
  ADMIN_PASSWORD="$(python3 - <<'PY'
import secrets
print('AI3-' + secrets.token_urlsafe(18))
PY
)"
  cat > .env <<EOF
AI3_ADMIN_KEY=$ADMIN_KEY
AI3_ADMIN_PASSWORD=$ADMIN_PASSWORD
AI3_ADMIN_SESSION_HOURS=12
AI3_MODEL=llama3.2:3b
AI3_OLLAMA_URL=http://ollama:11434
AI3_LLM_BASE_URL=http://ollama:11434/v1
AI3_LLM_API_KEY=
AI3_LLM_TIMEOUT=300
AI3_VLLM_URL=
AI3_LLAMACPP_URL=
AI3_BACKEND=ollama
EOF
  chmod 600 .env
  echo ".env wurde mit zufälligem Admin-Key und Admin-Passwort erstellt."
  echo "Admin-Passwort (einmalig anzeigen): $ADMIN_PASSWORD"
fi

echo "Starte Ollama, lade das lokale Modell und starte AI3 ..."
docker compose up -d --build

echo "Warte auf AI3 ..."
for _ in $(seq 1 60); do
  if curl -fsS http://localhost:8080/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if ! curl -fsS http://localhost:8080/health; then
  echo "AI3 wurde nicht rechtzeitig erreichbar. Logs: docker compose logs --tail=100"
  exit 1
fi

echo
echo "Erstelle den Standard-Agenten ..."
ADMIN_KEY="$(grep '^AI3_ADMIN_KEY=' .env | cut -d= -f2-)"
MODEL="$(grep '^AI3_MODEL=' .env | cut -d= -f2-)"

curl -fsS -X POST http://localhost:8080/v1/principals \
  -H "X-AI3-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"assistant-01","kind":"agent"}' >/dev/null || true

TOKEN_JSON="$(curl -fsS -X POST http://localhost:8080/v1/tokens \
  -H "X-AI3-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"principal":"assistant-01","name":"local","scopes":["ai:inference","agents:read"]}')"

TOKEN="$(printf '%s' "$TOKEN_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')"

cat > openclaw/ai3-provider.generated.json5 <<EOF
{
  models: {
    mode: "merge",
    providers: {
      ai3: {
        baseUrl: "http://127.0.0.1:8080/v1",
        apiKey: "$TOKEN",
        api: "openai-completions",
        timeoutSeconds: 300,
        models: [
          {
            id: "$MODEL",
            name: "AI3 Local $MODEL",
            reasoning: false,
            input: ["text"],
            cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
            contextWindow: 32768,
            maxTokens: 8192
          }
        ]
      }
    }
  },
  agents: {
    defaults: {
      model: { primary: "ai3/$MODEL" }
    }
  }
}
EOF

chmod 600 openclaw/ai3-provider.generated.json5

echo
echo "Fertig. AI3: http://localhost:8080"
echo "Modell: $MODEL"
echo "AI3-Token wurde erzeugt und in openclaw/ai3-provider.generated.json5 geschrieben."
echo "Wichtig: Dieses Token und .env nicht in Git committen."
echo "Admin-Passwort kann später in AI3 System geändert werden."
echo
echo "Test: curl http://localhost:8080/v1/models -H 'Authorization: Bearer $TOKEN'"
