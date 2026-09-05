# AI3 — eigener universeller KI-, Agent- und API-Gateway

AI3 ist ein selbst gehostetes Gateway für lokale KI-Modelle, KI-Agenten, Benutzer und OpenAI-kompatible Anwendungen. **Branding: xDarkixx. Copyright © 2026 xDarkixx.** Der Standardstack benötigt keinen kostenpflichtigen KI-API-Anbieter.

![AI3 Architecture](docs/ai3-architecture.svg)

## 🚀 Ziel: One-Click-Betrieb

Auf Ubuntu 24.04 LTS ist der Zielablauf:

1. Repository bereitstellen.
2. `scripts/install-ubuntu.sh` ausführen.
3. Router/Firewall-Portweiterleitungen setzen.
4. AI3 startet selbstständig und bleibt nach Neustarts aktiv.

Der Installer installiert Docker/Compose, erkennt NVIDIA-GPUs, richtet Ollama und das lokale Modell ein, erzeugt Secrets, startet AI3/Caddy/Mail, prüft die Dienste und erzeugt die OpenClaw-Konfiguration. Docker Compose verwendet Abhängigkeiten und Healthchecks, damit Dienste in der richtigen Reihenfolge starten. citeturn0search0turn0search3

```bash
chmod +x scripts/install-ubuntu.sh
./scripts/install-ubuntu.sh
```

Alle produktiven Container verwenden `restart: unless-stopped`, damit sie nach einem Docker-/Host-Neustart automatisch wieder anlaufen.

## 🔐 Automatisches HTTPS

Caddy übernimmt HTTPS und die automatische Zertifikatsverwaltung. Bei einem öffentlichen Domainnamen werden ACME-Zertifikate automatisch bezogen und erneuert; für `localhost`/interne Namen kann Caddy eine lokale CA verwenden. Für öffentliches HTTPS müssen DNS sowie Ports 80 und 443 auf den Server zeigen. citeturn0search1turn0search2

## ✉️ Eigener Mailserver

AI3 startet einen eigenen Mailserver ohne SMTP-Relay-Anbieter. Maildienste laufen im Host-Netzwerk, damit die echten Client-IP-Adressen für Spam-/Relay-Schutz erhalten bleiben. Der Webzugriff wird über Caddy bereitgestellt.

Ports:

- SMTP: `25`
- SMTPS: `465`
- Submission: `587`
- IMAP: `143` / `993`
- POP3: `110` / `995`
- Sieve: `4190`

Für echte öffentliche E-Mail-Zustellung sind zusätzlich eine öffentliche IP, korrektes PTR/rDNS und vollständige DNS-Verwaltung der Domain erforderlich. Port 25 kann der Router/Firewall weiterleiten, aber eine Sperre des Internetproviders kann AI3 nicht softwareseitig aufheben. citeturn1search0turn1search3

## 🪪 Eigene Verifizierung

Die Identitätsprüfung bleibt vollständig bei AI3. Es wird kein eID-, EUDI- oder kommerzieller KYC-Anbieter benötigt. AI3 kann verschlüsselte Nachweise verwalten und Prüfungen als `pending`, `verified` oder `rejected` führen.

Eine eigene Host-Prüfung ist **keine staatliche Identitätsbestätigung**.

## 🤖 Lokale KI

Ollama läuft lokal und AI3 benötigt für die Inferenz keinen externen KI-API-Anbieter. Modelle werden beim Setup automatisch geladen. CPU und kompatible NVIDIA-GPUs werden unterstützt.

## 🔌 API

- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/embeddings`

Damit können Apps, Bots und Agenten AI3 als eigenen OpenAI-kompatiblen Provider verwenden.

## 🖥️ Weboberfläche

Das Control Center bündelt:

- AI3-Systemstatus
- KI-/Ollama-Status
- Token- und Benutzerverwaltung
- Agentenverwaltung
- PKI und Zertifikate
- Own Verification
- Mailserver
- HTTPS
- Backups
- Sicherheitsstatus
- Diagnose/Healthchecks

## 🔏 Eigene PKI

AI3 erzeugt seine eigene Root-CA und kann interne Server-, Client- und Agent-Zertifikate ausstellen und widerrufen. Die CA ist eine private Vertrauensdomäne und ersetzt nicht das öffentlich vertrauenswürdige HTTPS von Caddy.

## 💾 Daten & Backups

Daten, Chats und Profile können verschlüsselt gespeichert werden. Persistente Docker-Volumes sorgen dafür, dass Daten Neustarts und Container-Neuerstellungen überleben. Backups werden lokal vorgesehen, ohne einen Cloud-Anbieter vorauszusetzen.

## 💰 Kostenmodell

Der Standardbetrieb ist auf **0 € für externe KI-, KYC-, SMTP- und Zertifikatsanbieter** ausgelegt. Es bleiben nur Infrastrukturkosten wie eigene Hardware, Strom, Internet und gegebenenfalls eine eigene Domain. Eine öffentliche Domain und deren DNS können nicht von einer lokalen Software kostenlos erfunden werden.

## 🛡️ Sicherheitsmodell

Enthalten sind unter anderem Token-Scopes, Ablaufzeiten, Admin-Sessions, Verschlüsselung, Rate-Limits, IP-/Concurrency-Schutz, HTTP-Sicherheitsheader, eigene PKI, Zertifikatswiderruf und lokale Backups.

Für einen öffentlichen Server muss die Firewall weiterhin restriktiv betrieben werden. Ein Router kann die benötigten Ports auf den AI3-Server weiterleiten.

## 📦 Neustartverhalten

Nach erfolgreicher Erstinstallation ist kein manueller Start der Container notwendig. Docker wird beim Boot aktiviert und die AI3-Dienste besitzen automatische Restart-Regeln. Compose kann zusätzlich auf Healthchecks und Abhängigkeiten warten, bevor abhängige Dienste gestartet werden. citeturn0search0turn0search8

## ⚠️ Was nicht automatisierbar ist

AI3 kann lokale Software, Zertifikate, Mailserver, Datenbanken, Modelle, Firewall-Regeln und Container automatisieren. Es kann jedoch nicht selbst:

- einen Domainnamen besitzen,
- DNS beim Domainanbieter ohne dessen API-Zugang ändern,
- eine Router-Portweiterleitung außerhalb des Servers setzen,
- eine ISP-Sperre für Port 25 aufheben,
- eine öffentliche IP vom Internetanbieter bereitstellen.

Das sind Netzwerk-/Infrastrukturvoraussetzungen und keine AI3-Softwareaufgaben.
