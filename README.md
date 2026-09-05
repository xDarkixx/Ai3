# AI3 — eigener Token-Server für KI & KI-Agenten

AI3 ist ein selbst gehosteter Token- und API-Gateway für KI-Anwendungen und KI-Agenten. Es verwaltet eigene `ai3_`-Tokens und kann Anfragen an einen lokalen OpenAI-kompatiblen KI-Server weiterreichen.

OpenClaw unterstützt benutzerdefinierte Provider mit `baseUrl` und `openai-completions`; damit kann OpenClaw AI3 als eigenen lokalen Provider verwenden. citeturn0search1turn0search2

## Weboberfläche

AI3 enthält jetzt ein integriertes **Control Center** direkt im selben Server. Es wird unter `http://localhost:8080/` geöffnet und benötigt keinen separaten Webserver oder Frontend-Container. FastAPI kann statische Frontends direkt ausliefern. citeturn0search3turn0search5

Die Oberfläche bietet:

- Dashboard mit Server- und Gateway-Status
- AI-Chat über das AI3-Gateway
- Benutzer-/Agent-Verwaltung
- Token-Erstellung und Widerruf
- Anzeige der verfügbaren Modelle
- Verbindungsinformationen
- responsive Darstellung für PC und Smartphone

Die Admin-Funktionen sind durch denselben `X-AI3-Admin-Key` geschützt wie die Admin-API. Aus Sicherheitsgründen werden vollständige Tokens nur bei der Erstellung angezeigt; die Token-Liste liefert niemals den geheimen Tokenwert zurück.

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
- integrierte Weboberfläche
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

Danach die Weboberfläche öffnen:

```text
http://localhost:8080/
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
docker compose up -d --build
```

Danach:

```text
http://localhost:8080/
```

Der Standardaufbau besteht aus:

```text
Browser / OpenClaw / KI-App
          |
          | AI3 Admin UI oder Bearer Token
          v
+--------------------------+
|       AI3 Gateway        |
| Web UI / Token / Scope   |
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

## Testen

```bash
curl http://localhost:8080/health
curl http://localhost:8080/v1/models -H "Authorization: Bearer DEIN_AI3_TOKEN"
```

Oder einfach die Weboberfläche unter `http://localhost:8080/` öffnen.

## Sicherheit

- AI3-Tokens werden nicht im Klartext in SQLite gespeichert.
- Der AI3-Token wird nicht an den lokalen Modellserver weitergereicht.
- `AI3_LLM_API_KEY` ist optional und nur für einen geschützten Upstream nötig.
- `AI3_LLM_BASE_URL` ist ausschließlich Server-Konfiguration.
- Der Admin-Key gehört niemals in Git.
- Die generierte OpenClaw-Datei mit Token wird automatisch ignoriert.
- Für öffentlichen Betrieb sollte AI3 hinter HTTPS, z. B. Nginx oder Caddy, betrieben werden.
- Für produktive Umgebungen sollten Tokens mit Ablaufzeit verwendet und bei Verdacht widerrufen werden.
- Die Weboberfläche zeigt vollständige Tokenwerte nur unmittelbar nach Erstellung an.

## Tests

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Die Tests prüfen jetzt zusätzlich, dass die Weboberfläche und ihre Assets ausgeliefert werden.

## API

- `GET /` — integrierte Weboberfläche
- `GET /web/*` — Web-Assets
- `GET /health`
- `POST /v1/principals` — Admin
- `GET /v1/admin/principals` — Admin
- `POST /v1/tokens` — Admin
- `GET /v1/admin/tokens` — Admin
- `GET /v1/admin/models` — Admin
- `POST /v1/tokens/revoke?token_prefix=...` — Admin
- `GET /v1/me`
- `GET /v1/agents`
- `GET /v1/models`
- `GET /v1/models/{model}`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/embeddings`

Alle KI-Endpunkte benötigen einen gültigen AI3-Bearer-Token mit `ai:inference` oder `admin`.
