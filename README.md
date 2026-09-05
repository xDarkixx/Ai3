# AI3 — eigener Token-Server für KI & KI-Agenten

AI3 ist ein selbst gehosteter Token- und API-Gateway für KI-Anwendungen und KI-Agenten. Es verwaltet eigene `ai3_`-Tokens und kann Anfragen an einen **lokalen OpenAI-kompatiblen KI-Server** weiterreichen.

Damit kann z. B. OpenClaw AI3 als eigenen Provider verwenden. OpenClaw unterstützt benutzerdefinierte Provider mit `baseUrl` und `openai-completions`; lokale Server wie vLLM und andere OpenAI-kompatible Backends sind dafür vorgesehen. citeturn0search0turn0search3

## Funktionen

- Eigene opaque API-Tokens mit `ai3_`-Prefix
- Tokens werden nur als SHA-256-Hash gespeichert
- Benutzer, KI-Agenten und Services als Principals
- Scopes pro Token
- Token-Ablauf und Widerruf
- `/v1/me` zur Identitätsprüfung
- geschützte Agenten-API
- OpenAI-kompatible Gateway-Endpunkte:
  - `GET /v1/models`
  - `GET /v1/models/{model}`
  - `POST /v1/chat/completions` inklusive Streaming
  - `POST /v1/responses`
  - `POST /v1/embeddings`
- Weiterleitung an Ollama, vLLM, llama.cpp, SGLang oder andere OpenAI-kompatible lokale Server
- SQLite ohne externen Datenbankdienst
- Docker/Ubuntu-freundlich
- automatisierte Tests mit pytest und GitHub Actions

## Kosten: für dich ohne KI-API-Gebühren

AI3 selbst benötigt keinen kostenpflichtigen Cloud-Dienst und keine bezahlte KI-API. Für einen komplett kostenlosen Betrieb kannst du einen lokalen Open-Source-Inferenzserver verwenden, z. B. Ollama oder vLLM. Dann werden die KI-Anfragen nicht an eine bezahlte Cloud-API geschickt.

**Aber:** Hardware, Strom, Internet oder ein gemieteter Server können natürlich Kosten verursachen. AI3 selbst erzeugt diese API-Gebühren nicht und verlangt keinen kostenpflichtigen KI-Provider.

## Start mit Docker

```bash
cp .env.example .env
# AI3_ADMIN_KEY in .env durch einen langen zufälligen Wert ersetzen
docker compose up -d --build
```

Standardmäßig erwartet AI3 einen lokalen OpenAI-kompatiblen Server unter:

```text
http://host.docker.internal:11434/v1
```

Das ist passend für einen lokal laufenden Ollama-Server. Für vLLM beispielsweise:

```text
AI3_LLM_BASE_URL=http://host.docker.internal:8000/v1
```

Healthcheck:

```bash
curl http://localhost:8080/health
```

## Ersten KI-Agenten und Token anlegen

```bash
curl -X POST http://localhost:8080/v1/principals \
  -H "X-AI3-Admin-Key: DEIN_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"assistant-01","kind":"agent"}'
```

Danach Token ausstellen:

```bash
curl -X POST http://localhost:8080/v1/tokens \
  -H "X-AI3-Admin-Key: DEIN_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"principal":"assistant-01","name":"openclaw","scopes":["ai:inference","agents:read"]}'
```

Das Token wird **nur bei der Ausstellung** im Klartext zurückgegeben. Danach liegt nur sein Hash in der Datenbank.

## OpenClaw verbinden

OpenClaw kann einen benutzerdefinierten Provider über `models.providers` mit `baseUrl`, `apiKey` und `api: "openai-completions"` verwenden. citeturn0search0turn0search2

Beispiel:

```json5
{
  models: {
    mode: "merge",
    providers: {
      ai3: {
        baseUrl: "http://127.0.0.1:8080/v1",
        apiKey: "DEIN_AI3_TOKEN",
        api: "openai-completions",
        timeoutSeconds: 300,
        models: [
          {
            id: "DEIN_LOKALES_MODELL",
            name: "AI3 Local Model",
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
      model: {
        primary: "ai3/DEIN_LOKALES_MODELL"
      }
    }
  }
}
```

Für einen Docker-Aufbau sollte OpenClaw statt `127.0.0.1` den erreichbaren Docker-Service-Namen von AI3 verwenden.

OpenClaw benötigt für einen OpenAI-kompatiblen lokalen Provider `/v1/chat/completions`; die AI3-Gateway-Schicht stellt diesen Endpunkt bereit und authentifiziert vorher den `ai3_`-Token. citeturn0search5turn0search3

## Ablauf

```text
OpenClaw / KI-App
       |
       | Authorization: Bearer ai3_...
       v
+--------------------------+
|       AI3 Gateway        |
| Token / Scope / Ablauf   |
+------------+-------------+
             |
             | OpenAI-compatible API
             v
+--------------------------+
| Ollama / vLLM / llama.cpp|
| lokales Open-Source-Modell|
+--------------------------+
```

AI3 sendet den `ai3_`-Token **nicht** an den lokalen Modellserver weiter. Wenn `AI3_LLM_API_KEY` gesetzt ist, verwendet AI3 stattdessen diesen separaten Upstream-Schlüssel.

## Identität testen

```bash
curl http://localhost:8080/v1/me \
  -H "Authorization: Bearer DEIN_AI3_TOKEN"
```

Modelle testen:

```bash
curl http://localhost:8080/v1/models \
  -H "Authorization: Bearer DEIN_AI3_TOKEN"
```

Chat testen:

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer DEIN_AI3_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"DEIN_LOKALES_MODELL","messages":[{"role":"user","content":"Hallo"}]}'
```

## Tests

Lokal:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Der Workflow `.github/workflows/test.yml` führt die Tests bei Pushes auf `main` und bei Pull Requests automatisch aus.

## API

- `GET /health` — Healthcheck
- `POST /v1/principals` — Principal anlegen (Admin)
- `POST /v1/tokens` — Token ausstellen (Admin)
- `POST /v1/tokens/revoke?token_prefix=...` — Token widerrufen (Admin)
- `GET /v1/me` — aktuelles Token prüfen
- `GET /v1/agents` — aktive Principals lesen, benötigt `agents:read` oder `admin`
- `GET /v1/models` — Modelle des lokalen Upstreams
- `GET /v1/models/{model}` — einzelnes Modell
- `POST /v1/chat/completions` — Chat-Completions, inklusive Streaming
- `POST /v1/responses` — Responses an den Upstream weiterleiten
- `POST /v1/embeddings` — Embeddings an den Upstream weiterleiten

Alle KI-Endpunkte benötigen einen gültigen AI3-Bearer-Token mit `ai:inference` oder `admin`.

## Sicherheit

Für den produktiven Betrieb sollte der Dienst hinter HTTPS (z. B. Nginx/Caddy) betrieben werden. Der Admin-Key gehört ausschließlich in eine Secret-Variable und niemals in Git. Tokens sollten möglichst kurze Ablaufzeiten haben und bei Verdacht sofort widerrufen werden.

`AI3_LLM_BASE_URL` ist eine Server-Konfiguration und wird nicht aus Benutzeranfragen übernommen. Dadurch kann ein Benutzer den Gateway-Upstream nicht beliebig umbiegen.
