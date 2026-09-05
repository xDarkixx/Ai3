# AI3 — eigener Token-Server für KI & KI-Agenten

AI3 ist ein selbst gehosteter Token- und API-Gateway für KI-Anwendungen und KI-Agenten. Es verwaltet eigene `ai3_`-Tokens und kann Anfragen an einen lokalen OpenAI-kompatiblen KI-Server weiterreichen.

OpenClaw unterstützt benutzerdefinierte Provider mit `baseUrl` und `openai-completions`; damit kann OpenClaw AI3 als eigenen lokalen Provider verwenden. citeturn0search1turn0search2

## Funktionen

- Eigene opaque API-Tokens mit `ai3_`-Prefix
- Tokens werden nur als SHA-256-Hash gespeichert
- Benutzer, KI-Agenten und Services als Principals
- Scopes pro Token
- Token-Ablauf und Widerruf
- `/v1/me` zur Identitätsprüfung
- geschützte Agenten-API
- OpenAI-kompatible Gateway-Endpunkte: `/v1/models`, `/v1/models/{model}`, `/v1/chat/completions`, `/v1/responses`, `/v1/embeddings`
- Chat-Streaming
- integrierter lokaler Ollama-Stack
- Weiterleitung an Ollama, vLLM, llama.cpp, SGLang oder andere OpenAI-kompatible Server
- SQLite ohne externen Datenbankdienst
- Docker/Ubuntu-freundlich
- automatisierte Tests mit pytest und GitHub Actions

## Kosten: ohne KI-API-Gebühren

Der Standardaufbau verwendet **Ollama + ein lokales Open-Source-Modell**. Ollama stellt unter anderem `/v1/models`, `/v1/chat/completions` und `/v1/embeddings` bereit. citeturn0search0

Dadurch benötigt AI3 für die KI-Anfragen **keine kostenpflichtige Cloud-KI-API**. Die lokale Standardauswahl `llama3.2:3b` ist etwa 2 GB groß und für lokale Nutzung relativ klein. citeturn1search0

Hardware, Strom, Internet oder ein gemieteter Server können natürlich Kosten verursachen. AI3 selbst verlangt keine monatliche Gebühr und erzwingt keinen kostenpflichtigen KI-Provider.

## Schnellstart — alles lokal

Voraussetzung: Docker Engine mit Docker Compose und `curl`.

```bash
chmod +x scripts/setup-local.sh
./scripts/setup-local.sh
```

Das Skript:

1. erzeugt bei Bedarf automatisch einen zufälligen `AI3_ADMIN_KEY`,
2. startet Ollama,
3. lädt automatisch `llama3.2:3b`,
4. startet AI3,
5. legt den Agenten `assistant-01` an,
6. erzeugt einen AI3-Token mit `ai:inference` und `agents:read`,
7. erstellt eine lokale OpenClaw-Konfigurationsdatei.

Das Modell wird im Docker-Volume `ollama-data` gespeichert und deshalb bei späteren Starts nicht erneut heruntergeladen.

Ollama kann offiziell als Docker-Container betrieben werden. citeturn0search9

## Manuell mit Docker Compose

```bash
cp .env.example .env
```

In `.env` einen langen eigenen Admin-Key setzen und anschließend:

```bash
docker compose up -d --build
```

Der Standardaufbau besteht aus:

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
|          Ollama          |
|       llama3.2:3b        |
+--------------------------+
```

AI3 ist auf Port `8080` erreichbar. Ollama bleibt im Docker-Netzwerk und wird nicht unnötig als Host-Port veröffentlicht.

## OpenClaw verbinden

OpenClaw verwendet für benutzerdefinierte OpenAI-kompatible Provider `models.providers` mit `baseUrl`, `apiKey` und `api: "openai-completions"`. citeturn0search1turn0search3

Nach `./scripts/setup-local.sh` liegt die generierte Konfiguration unter:

```text
openclaw/ai3-provider.generated.json5
```

Sie enthält ein persönliches AI3-Token und wird deshalb von `.gitignore` ausgeschlossen.

Vorlage:

```text
openclaw/ai3-provider.example.json5
```

Die Konfiguration sieht grundsätzlich so aus:

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
            id: "llama3.2:3b",
            name: "AI3 Local Llama 3.2 3B",
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
      model: { primary: "ai3/llama3.2:3b" }
    }
  }
}
```

Wenn OpenClaw in einem anderen Container läuft, muss `127.0.0.1` durch den für OpenClaw erreichbaren AI3-Host bzw. Docker-Service ersetzt werden. OpenClaw hat dafür einen Netzwerk-Schutz für lokale/private Provider-Endpunkte. citeturn0search1

## Andere lokale Modelle / Server

AI3 ist nicht auf Ollama festgelegt. Für einen lokalen vLLM-Server beispielsweise:

```env
AI3_LLM_BASE_URL=http://host.docker.internal:8000/v1
AI3_LLM_API_KEY=
```

OpenClaw dokumentiert vLLM ausdrücklich als OpenAI-kompatiblen lokalen Provider mit `/v1/models` und `/v1/chat/completions`. citeturn0search4

Auch llama.cpp, SGLang und andere kompatible lokale Gateways können verwendet werden. citeturn0search8

## Testen

```bash
curl http://localhost:8080/health
curl http://localhost:8080/v1/models -H "Authorization: Bearer DEIN_AI3_TOKEN"
```

Chat:

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer DEIN_AI3_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.2:3b","messages":[{"role":"user","content":"Hallo"}]}'
```

## Sicherheit

- AI3-Tokens werden nicht im Klartext in SQLite gespeichert.
- Der AI3-Token wird nicht an den lokalen Modellserver weitergereicht.
- `AI3_LLM_API_KEY` ist optional und nur für einen geschützten Upstream nötig.
- `AI3_LLM_BASE_URL` ist ausschließlich Server-Konfiguration.
- Der Admin-Key gehört niemals in Git.
- Die generierte OpenClaw-Datei mit Token wird automatisch ignoriert.
- Für öffentlichen Betrieb sollte AI3 hinter HTTPS, z. B. Nginx oder Caddy, betrieben werden.
- Für produktive Umgebungen sollten Tokens mit Ablaufzeit verwendet und bei Verdacht widerrufen werden.

## Tests

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Der Workflow `.github/workflows/test.yml` führt die Tests bei Pushes auf `main` und bei Pull Requests automatisch aus.

## API

- `GET /health`
- `POST /v1/principals` — Admin
- `POST /v1/tokens` — Admin
- `POST /v1/tokens/revoke?token_prefix=...` — Admin
- `GET /v1/me`
- `GET /v1/agents`
- `GET /v1/models`
- `GET /v1/models/{model}`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/embeddings`

Alle KI-Endpunkte benötigen einen gültigen AI3-Bearer-Token mit `ai:inference` oder `admin`.
