# AI3 — eigener universeller KI-, Agent- und API-Gateway

AI3 ist ein selbst gehosteter Gateway für lokale KI-Modelle, KI-Agenten und OpenAI-kompatible Anwendungen. **Branding: xDarkixx. Copyright © 2026 xDarkixx.** Der Standardstack benötigt keinen kostenpflichtigen KI-API-Anbieter.

## Empfohlenes Zielsystem

AI3 wird als **einheitliches System für Ubuntu Server 24.04 LTS amd64** gepflegt. Ubuntu 24.04 LTS erhält reguläre Sicherheitswartung bis 2029; die genaue Lebensdauer ist in der Ubuntu-Release-Übersicht dokumentiert. citeturn0search1turn0search8

Der Installer unterstützt auf diesem einen System automatisch beide Hardwarevarianten:

- **NVIDIA vorhanden und Docker-GPU-Test erfolgreich → GPU-Modus**
- **keine NVIDIA-GPU oder GPU-Test fehlgeschlagen → CPU-Modus**
- kein separater AI3-Codezweig nötig
- gleiche Daten, API und OpenClaw-Anbindung in beiden Modi

Siehe die ausführliche Hardwareplanung in [`HARDWARE.md`](HARDWARE.md).

## Hardware-Empfehlung

| Einsatz | CPU | RAM | GPU/VRAM | Speicher |
|---|---:|---:|---:|---:|
| Test / 1 Benutzer | 4 Kerne | 8 GB | keine | 50 GB SSD |
| Privater AI3-Server | 6–8 Kerne | 16 GB | optional 8 GB VRAM | 100 GB NVMe |
| Mehrere Agents | 8–16 Kerne | 32 GB | 12–16 GB VRAM | 250 GB NVMe |
| Große lokale Modelle | 12–24 Kerne | 64 GB+ | 24 GB+ VRAM | 500 GB+ NVMe |

Das sind AI3-Praxisempfehlungen und keine offiziellen Mindestanforderungen für KI-Inferenz. Der konkrete Bedarf hängt von Modell, Quantisierung, Kontext und Parallelität ab. Ubuntu selbst nennt wesentlich niedrigere Server-Minima; ein AI3-Server mit lokaler KI braucht entsprechend mehr Reserven. citeturn0search1

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

Jeder Nutzer/Agent/Service bekommt eine eigene Identität und einen eigenen Token. Dadurch muss kein gemeinsamer Admin-Schlüssel verteilt werden.

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
- optionale kostenpflichtige externe Modelle über einen OpenAI-kompatiblen Upstream
- API Playground in der Weboberfläche
- Usage-/Latenz-/Fehlerstatistik
- automatische Modellinitialisierung beim Docker-Start
- SQLite ohne externe Datenbank
- Admin-Datenbank-Backups
- Live-Limits und Quoten
- modernes responsives Command-Center-Design
- Copyright-/Rechtshinweise direkt in der Oberfläche
- automatisches NVIDIA-GPU-Passthrough oder CPU-Fallback

## One-Click-Installation

### Ubuntu Server 24.04 LTS

```bash
chmod +x scripts/install-ubuntu.sh
./scripts/install-ubuntu.sh
```

Der Installer prüft das Betriebssystem, installiert Docker Engine und Compose, erkennt NVIDIA, richtet bei Bedarf das NVIDIA Container Toolkit ein und testet den GPU-Zugriff. Bei einem fehlgeschlagenen GPU-Test läuft die Installation automatisch im CPU-Modus. Danach werden AI3, Ollama und das konfigurierte lokale Modell gestartet. citeturn0search1

Nach erfolgreicher Installation wird zusätzlich `scripts/doctor.sh` ausgeführt. Damit werden Docker, Compose, CPU-/GPU-Compose-Dateien, AI3 Health, Ollama und grundlegende Sicherheitsdateien geprüft.

## Ergebnis

Nach der Installation gibt es automatisch:

- AI3 Gateway unter `http://localhost:8080`
- Ollama mit persistentem Modell-Speicher
- sicheren Admin-Key und Admin-Passwort in `.env`
- einen initialen `assistant-01` Agenten
- einen AI3 Bearer-Token für den initialen Agenten
- `openclaw/ai3-provider.generated.json5`
- persistente Docker-Volumes für AI3-Daten und Modelle

**Geheimnisse niemals committen:** `.env` und die generierte OpenClaw-Datei bleiben per `.gitignore` außerhalb von Git.

Für einen öffentlichen Server sollten zusätzlich TLS/Reverse-Proxy, Firewall und ein strenges Rate-Limit eingerichtet werden.

## Diagnose

```bash
./scripts/doctor.sh
```

Bei Problemen:

```bash
docker compose logs --tail=150
```

## Lokale oder kostenpflichtige Modelle

AI3 kann vollständig lokal laufen. Alternativ kann der Betreiber einen OpenAI-kompatiblen externen Anbieter als Upstream konfigurieren. Der Provider-Key bleibt auf dem AI3-Server.

```env
AI3_LLM_BASE_URL=https://DEIN-PROVIDER/v1
AI3_LLM_API_KEY=DEIN_PROVIDER_KEY
AI3_LLM_TIMEOUT=300
```

## Limits und „unbegrenzt"

In **System → Limits & Kontingente** können Laufzeitlimits eingestellt werden:

- Requests pro Minute
- Requests pro 24 Stunden

**`0 = unbegrenzt`.** Infrastruktur bleibt natürlich durch CPU, RAM, GPU, Speicher und Netzwerk begrenzt.

## Kosten

AI3 kann vollständig lokal mit Open-Source-Modellen betrieben werden, sodass kein bezahlter KI-API-Anbieter notwendig ist. Das bedeutet nicht automatisch 0 € Gesamtbetriebskosten: Hardware, Strom, Internet, Hosting, Domain und gegebenenfalls Modell-/Softwarelizenzen können Kosten verursachen.

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

OpenClaw verbindet sich damit direkt mit AI3; ein externer KI-API-Key ist bei lokaler Inferenz nicht nötig.

## Branding und Rechtliches

AI3 trägt sichtbar die Kennzeichnung **„AI3 — BY XDARKIXX“** sowie **© 2026 xDarkixx — AI3**. Zusätzlich gibt es `LEGAL.md` und die entsprechende Weboberfläche.

Die rechtlichen Hinweise sind keine Rechtsberatung. Für eine öffentliche Instanz müssen insbesondere Betreiberangaben, Datenschutz, Aufbewahrung/Löschung sowie Modell- und Drittanbieter-Lizenzen an den konkreten Betrieb angepasst werden.
