# AI3 — eigener universeller KI-, Agent- und API-Gateway

AI3 ist ein selbst gehostetes Gateway für lokale KI-Modelle, KI-Agenten, Benutzer und OpenAI-kompatible Anwendungen. **Branding: xDarkixx. Copyright © 2026 xDarkixx.** Der Standardstack benötigt keinen kostenpflichtigen KI-API-Anbieter.

![AI3 Architecture](docs/ai3-architecture.svg)

## 🚀 Ein-Datei-Installation

Der einfachste Weg auf einem **aktuellen Ubuntu 24.04+ AMD64-System** ist die einzelne Datei `AI3-Install.run`.

Der Installer ist absichtlich **nicht auf Ubuntu 24.04 fest verdrahtet**. Er akzeptiert unterstützte Ubuntu-Releases ab 24.04 und verwendet die Paketquellen und Host-Abhängigkeiten der erkannten Ubuntu-Version.

```bash
chmod +x AI3-Install.run
sudo ./AI3-Install.run
```

Die Datei ist ein Bootstrap: Sie installiert die minimal benötigten Werkzeuge, lädt automatisch den **aktuellen AI3-Stand von GitHub** und startet anschließend die vollständige Installation. Du musst vorher nicht das komplette Repository klonen.

Der Installer erledigt danach automatisch:

1. Ubuntu-Version prüfen.
2. notwendige Host-Abhängigkeiten installieren.
3. aktuellen `main`-Stand von GitHub laden.
4. AI3 nach `/opt/ai3` installieren bzw. eine vorhandene Installation sicher aktualisieren.
5. Docker und Docker Compose einrichten.
6. NVIDIA-GPU automatisch erkennen und, wenn möglich, GPU-Unterstützung aktivieren.
7. CPU/RAM als Fallback verwenden, wenn keine nutzbare GPU vorhanden ist.
8. Ollama und den lokalen KI-Stack einrichten.
9. Secrets, Datenverzeichnisse und Konfiguration erzeugen.
10. AI3, Caddy, Mail und die übrigen Dienste starten.
11. LAN-Adresse automatisch erkennen und überwachen.
12. Healthchecks durchführen.
13. den automatischen GitHub-Updater aktivieren.

**Die einzelne Datei ist der Startpunkt; der eigentliche AI3-Quellstand bleibt im Repository.** Dadurch lädt eine neue Installation immer den aktuellen Stand statt eine veraltete Kopie zu installieren.

### Unterstützte Ubuntu-Versionen

Der Installer unterstützt **Ubuntu 24.04 und neuere unterstützte Ubuntu-Releases**. Die Installer-Prüfung lässt aktuelle Ubuntu-Versionen ab 24.04 zu, statt nur `24.04` zu akzeptieren.

Ubuntu Desktop ist nicht erforderlich. Die AI3-Weboberfläche läuft über den Browser; dadurch bleiben CPU, RAM und GPU für AI3 verfügbar.

### Erneute Installation / vorhandenes AI3

Wenn `/opt/ai3` bereits existiert, versucht `AI3-Install.run` die bestehende Git-Installation per Fast-Forward zu aktualisieren, sofern keine lokalen Änderungen vorhanden sind. Persistente Runtime-Daten werden dabei nicht absichtlich gelöscht.

### Automatische Updates nach der Installation

Nach der Erstinstallation überwacht AI3 automatisch den konfigurierten GitHub-Branch. Neue Commits werden regelmäßig geprüft. Bei einem Update werden Abhängigkeiten, Compose-Konfiguration und Container berücksichtigt; anschließend erfolgt ein Healthcheck. Wenn ein Update fehlschlägt und Rollback aktiviert ist, wird auf den vorherigen funktionierenden Stand zurückgegangen.

## Passendes Betriebssystem

Der One-Click-Installer ist für **Ubuntu 24.04+ 64-bit AMD64** ausgelegt.

- Detaillierte Anleitung: [`docs/INSTALL-UBUNTU.md`](docs/INSTALL-UBUNTU.md)
- Optionaler Ubuntu-Download + SHA256-Prüfung: `scripts/download-ubuntu.sh`

## 🔄 Automatische Netzwerk-Selbstheilung

AI3 benötigt keine fest eingetragene LAN-IP. `scripts/network-refresh.sh` erkennt automatisch PC-Name, aktuelle IPv4, Netzwerkinterface und Gateway. Ein systemd-Dienst aktualisiert die Identität beim Boot; ein Timer prüft sie anschließend regelmäßig.

Zusätzlich stellt AI3 der Weboberfläche ausschließlich harmlose Netzwerk-Metadaten über `/__ai3/network-info.json` bereit. Geheimnisse, Admin-Schlüssel und `.env` werden niemals über diese Route veröffentlicht.

Wenn der Router beispielsweise DHCP neu vergibt, aktualisiert AI3 automatisch die gespeicherte LAN-IP und bei Bedarf nur Caddy. Ollama, Datenbank und die übrigen AI3-Dienste müssen dafür nicht neu gestartet werden.

**Router-Portfreigaben werden absichtlich nicht automatisch verändert.** Du wählst im Router einmal den AI3-PC als Zielgerät und leitest die benötigten Ports weiter.

## 🔐 Automatisches HTTPS

Caddy übernimmt HTTPS und die automatische Zertifikatsverwaltung. Bei einem öffentlichen Domainnamen werden ACME-Zertifikate automatisch bezogen und erneuert; für interne Namen kann Caddy eine lokale CA verwenden. Für öffentliches HTTPS müssen DNS sowie Ports 80 und 443 auf den Server zeigen.

## ✉️ Eigener Mailserver

AI3 kann einen eigenen Mailserver ohne SMTP-Relay-Anbieter betreiben. Für echte öffentliche E-Mail-Zustellung sind zusätzlich eine öffentliche IP, korrektes PTR/rDNS und vollständige DNS-Verwaltung der Domain erforderlich.

## 🤖 Lokale KI

Ollama läuft lokal und AI3 benötigt für die Inferenz keinen externen KI-API-Anbieter. Modelle werden beim Setup automatisch geladen. CPU und kompatible NVIDIA-GPUs werden unterstützt.

## 🔌 API

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/embeddings`

Damit können Apps, Bots und Agenten AI3 als eigenen OpenAI-kompatiblen Provider verwenden.

## 🖥️ Weboberfläche

Das Control Center bündelt unter anderem AI3-Systemstatus, KI-/Ollama-Status, Token- und Benutzerverwaltung, Agentenverwaltung, PKI, Mailserver, HTTPS, Backups, Sicherheitsstatus, Live-System- und Netzwerkstatus sowie Diagnose/Healthchecks.

## 💾 Daten & Backups

Persistente Docker-Volumes sorgen dafür, dass Daten Neustarts und Container-Neuerstellungen überleben. Backups werden lokal vorgesehen, ohne einen Cloud-Anbieter vorauszusetzen.

## 💰 Kostenmodell

Der Standardbetrieb ist auf **0 € für externe KI-, KYC-, SMTP- und Zertifikatsanbieter** ausgelegt. Es bleiben Infrastrukturkosten wie eigene Hardware, Strom, Internet und gegebenenfalls eine eigene Domain.

## 🛡️ Sicherheitsmodell

Enthalten sind unter anderem Token-Scopes, Ablaufzeiten, Admin-Sessions, Verschlüsselung, Rate-Limits, IP-/Concurrency-Schutz, HTTP-Sicherheitsheader, eigene PKI, Zertifikatswiderruf und lokale Backups.

## 📦 Neustartverhalten

Nach erfolgreicher Erstinstallation ist kein manueller Start der Container notwendig. Docker wird beim Boot aktiviert und die AI3-Dienste besitzen automatische Restart-Regeln. Der LAN-Watcher und der GitHub-Updater starten ebenfalls automatisch.

## ⚠️ Was nicht vollständig automatisierbar ist

AI3 kann lokale Software, Zertifikate, Mailserver, Datenbanken, Modelle, Firewall-Regeln und Container automatisieren. Es kann jedoch nicht ohne passende Router-/Provider-Schnittstelle einen Domainnamen besitzen, fremdes DNS ändern, Router-Portweiterleitungen setzen oder eine ISP-Sperre für Port 25 aufheben.

Die LAN-IP des AI3-PCs wird dagegen automatisch erkannt und aktualisiert.
