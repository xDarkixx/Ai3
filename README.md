# AI3 — eigener universeller KI-, Agent- und API-Gateway

AI3 ist ein selbst gehosteter Gateway für lokale KI-Modelle, KI-Agenten und OpenAI-kompatible Anwendungen. **Branding: xDarkixx. Copyright © 2026 xDarkixx.** Der Standardstack benötigt keinen kostenpflichtigen KI-API-Anbieter.

## Für andere Nutzer / Clients

AI3 ist dafür gebaut, dass **andere Personen, Agents und Programme** ihn wie einen normalen KI-Provider benutzen können:

```text
Client / OpenClaw / Open WebUI / Bot / App
                    |
                    | HTTPS + AI3 Bearer Token
                    v
             https://DEIN-HOST/v1
                    |
                    v
             AI3 Gateway
                    |
             lokales Backend
                    |
                 Modell
```

Jeder Nutzer/Agent/Service bekommt eine eigene Identität und einen eigenen Token. Dadurch muss kein gemeinsamer Admin-Schlüssel verteilt werden. OpenClaw unterstützt solche benutzerdefinierten OpenAI-kompatiblen Provider mit `baseUrl`, API-Key und `openai-completions`. citeturn0search0turn0search4

## Was AI3 kann

- OpenAI-kompatible `/v1` API für Chat, Models, Responses und Embeddings
- eigene `ai3_...` API-Tokens mit Scopes und Ablaufzeiten
- kurzlebige OAuth2-artige Access Tokens und rotierende Refresh Tokens
- OAuth-Clients mit eigenem Client-ID/Secret
- Revocation und Security-Event-Protokoll
- Benutzer, Agents und Services als eigene Identitäten
- Agent-Konfiguration mit Modell und Backend
- lokale Modelle über Ollama
- vorbereitete Backend-Abstraktion für Ollama, vLLM und llama.cpp
- **optionale kostenpflichtige externe Modelle** über einen OpenAI-kompatiblen Upstream
- API Playground in der Weboberfläche
- Usage-/Latenz-/Fehlerstatistik
- automatische Modellinitialisierung beim Docker-Start
- SQLite ohne externe Datenbank
- Admin-Datenbank-Backups
- Live-Limits und Quoten
- modernes responsives Command-Center-Design
- Copyright-/Rechtshinweise direkt in der Oberfläche
- optionales NVIDIA-GPU-Passthrough für Ollama

## One-Click-Installation

### Ubuntu / Debian mit Docker Engine

Der Installer richtet die benötigten Systemkomponenten ein, darunter Docker Engine, Docker Compose Plugin, Git, Python und die benötigten Werkzeuge. Wenn `nvidia-smi` verfügbar ist, richtet er zusätzlich das NVIDIA Container Toolkit ein und verwendet die GPU für Ollama, sofern Docker-GPU-Zugriff erfolgreich getestet werden kann. Die Docker- und NVIDIA-Schritte folgen den offiziellen Installationswegen. citeturn0search6turn1search0

```bash
chmod +x scripts/install-ubuntu.sh
./scripts/install-ubuntu.sh
```

Danach laufen AI3 und Ollama als Docker-Stack. Das lokale Modell aus `AI3_MODEL` wird automatisch geladen. Docker Compose ist genau für das gemeinsame Starten mehrerer Services und persistenter Volumes ausgelegt. citeturn0search4turn0search7

### Windows

Docker Desktop muss installiert und gestartet sein. Danach in PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install-windows.ps1
```

Der Windows-Installer erstellt `.env`, startet den Stack, wartet auf den Health-Endpunkt, erzeugt einen Agenten und schreibt die OpenClaw-Konfiguration.

### Ergebnis

Nach der Installation gibt es automatisch:

- AI3 Gateway unter `http://localhost:8080`
- Ollama mit persistentem Modell-Speicher
- sicheren Admin-Key und Admin-Passwort in `.env`
- einen initialen `assistant-01` Agenten
- einen AI3 Bearer-Token für den initialen Agenten
- `openclaw/ai3-provider.generated.json5`
- persistente Docker-Volumes für AI3-Daten und Modelle

**Geheimnisse niemals committen:** `.env` und die generierte OpenClaw-Datei bleiben per `.gitignore` außerhalb von Git.

Für einen öffentlichen Server sollten zusätzlich TLS/Reverse-Proxy, Firewall und ein strenges Rate-Limit eingerichtet werden. Ein kostenloses Let's-Encrypt-Zertifikat ist möglich.

## Lokale oder kostenpflichtige Modelle

AI3 ist nicht auf kostenlose lokale Modelle festgelegt. Wenn lokale Inferenz nicht ausreicht, kann der Betreiber einen **OpenAI-kompatiblen externen Anbieter** als Upstream konfigurieren, z. B. einen Dienst mit `/v1/models` und `/v1/chat/completions`. AI3 reicht die Anfrage über den konfigurierten Upstream weiter; der jeweilige Anbieter rechnet nach dessen Tarif ab.

Beispiel in `.env`:

```env
AI3_LLM_BASE_URL=https://DEIN-PROVIDER/v1
AI3_LLM_API_KEY=DEIN_PROVIDER_KEY
AI3_LLM_TIMEOUT=300
```

Der externe Provider-Key bleibt ausschließlich auf dem AI3-Server und wird nicht an Nutzer/Agents weitergegeben. OpenClaw kann AI3 anschließend als eigenen OpenAI-kompatiblen Provider verwenden. citeturn0search0turn0search3

## Limits und „unbegrenzt"

In **System → Limits & Kontingente** können die Laufzeitlimits eingestellt werden:

- Requests pro Minute
- Requests pro 24 Stunden

**`0 = unbegrenzt`.** Die Änderungen werden ohne Neustart für neue Requests übernommen. Mit **„Alles unbegrenzt“** werden die beiden aktiven Limits auf 0 gesetzt.

Für einen öffentlichen Server wird empfohlen, Limits zu aktivieren. Für einen privaten Server kann 0/unbegrenzt verwendet werden. Infrastrukturressourcen bleiben natürlich trotzdem begrenzt durch CPU, RAM, GPU, Speicher und Netzwerk.

## Branding und Rechtliches

AI3 trägt sichtbar die Kennzeichnung **„AI3 — BY XDARKIXX“** sowie **© 2026 xDarkixx — AI3**. Zusätzlich gibt es in der Weboberfläche eine Seite **„Rechtliches“** und im Repository `LEGAL.md`.

Die dortigen Hinweise sind keine Rechtsberatung. Für eine öffentliche Instanz müssen insbesondere Betreiberangaben/Impressum, Datenschutzerklärung, Aufbewahrungs- und Löschregeln sowie die Lizenzen verwendeter Modelle und Drittanbieter geprüft und an den konkreten Betreiber angepasst werden.

## Kosten

AI3 kann vollständig lokal mit Open-Source-Modellen betrieben werden, sodass kein bezahlter KI-API-Anbieter notwendig ist. Das ist **0 € für den KI-Provider**, nicht automatisch 0 € Gesamtbetriebskosten. Hardware, Strom, Internet, Hosting, Domain und gegebenenfalls Modell-/Softwarelizenzen können Kosten verursachen.

Bei einem externen kostenpflichtigen Upstream entstehen zusätzlich dessen normale Nutzungsgebühren. AI3 selbst benötigt dafür keinen separaten SaaS-Abrechnungsdienst.

## Manuelle Schnellstart-Alternative

```bash
chmod +x scripts/setup-local.sh
./scripts/setup-local.sh
```

Oder manuell:

```bash
cp .env.example .env
docker compose up -d --build
```

Standardmäßig wird `llama3.2:3b` geladen. Weboberfläche und API sind anschließend unter dem AI3-Host erreichbar.

## OpenAI-kompatible Endpunkte

- `GET /v1/models`
- `GET /v1/models/{id}`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/embeddings`

## OpenClaw

```json5
{
  models: {
    providers: {
      ai3: {
        baseUrl: "https://DEIN-AI3-HOST/v1",
        apiKey: "YOUR_AI3_TOKEN",
        api: "openai-completions",
        models: [{ id: "llama3.2:3b", name: "AI3 Local" }]
      }
    }
  }
}
```

OpenClaw verbindet sich damit direkt mit AI3; der Nutzer benötigt keinen eigenen externen KI-API-Key, solange AI3 lokal inferiert. citeturn0search0turn0search2
