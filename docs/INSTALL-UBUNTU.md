# AI3 — Ubuntu-Installation

## 1. Unterstützte Systeme

AI3 ist für **Ubuntu 24.04 und neuere unterstützte Ubuntu-Releases, 64-bit AMD64** ausgelegt.

Der Installer ist nicht auf exakt Ubuntu 24.04 festgelegt. Er prüft, ob eine unterstützte Ubuntu-Version ab 24.04 vorhanden ist, und installiert die benötigten Pakete über die Paketquellen des jeweiligen Systems.

Ubuntu Desktop ist nicht erforderlich. Die AI3-Control-Center-Oberfläche läuft über einen normalen Browser auf einem anderen PC im LAN. So bleiben die Ressourcen des Servers für Docker, Ollama und die KI-Modelle verfügbar.

## 2. Frische Installation mit nur einer Datei

Auf einem aktuellen Ubuntu 24.04+ brauchst du nur `AI3-Install.run` als Startdatei.

```bash
chmod +x AI3-Install.run
sudo ./AI3-Install.run
```

Der Bootstrap installiert zunächst nur die notwendigen Werkzeuge (`ca-certificates`, `curl`, `git`, `tar`). Danach lädt er automatisch den aktuellen `main`-Stand von:

`https://github.com/xDarkixx/Ai3`

und installiert ihn unter:

`/opt/ai3`

Anschließend wird automatisch der vollständige AI3-Installer ausgeführt.

### Was automatisch eingerichtet wird

- Ubuntu-Version ab 24.04 prüfen
- Docker Engine und Docker Compose
- fehlende Host-Abhängigkeiten
- NVIDIA-Erkennung und Container-Unterstützung, sofern kompatibel
- CPU/RAM-Fallback ohne GPU
- Ollama und lokale KI
- AI3-Docker-Stack
- Caddy/HTTPS
- Mailserver, sofern in der Installation aktiviert
- Secrets und Runtime-Konfiguration
- eigene PKI
- LAN-/DHCP-Erkennung
- systemd-Dienste und Timer
- Healthchecks
- automatischer GitHub-Updater

Du musst das komplette Repository vorher **nicht** manuell klonen.

## 3. Nach der Installation

AI3 startet seine Dienste automatisch. Die Weboberfläche ist über die vom Server angezeigte LAN-Adresse erreichbar.

Die aktuelle Netzwerkidentität wird automatisch erkannt:

- PC-Name
- LAN-IPv4
- Netzwerkadapter
- Standard-Gateway

Eine DHCP-Adresse muss nicht fest in AI3 eingetragen werden.

## 4. Automatische Updates

Nach der Erstinstallation prüft der AI3-Updater regelmäßig GitHub auf einen neuen Commit des konfigurierten Branches.

Bei einem neuen Stand:

1. Repository-Stand wird aktualisiert.
2. lokale Runtime-/Konfigurationsdaten bleiben erhalten.
3. fehlende Host-Abhängigkeiten werden bei Bedarf nachinstalliert.
4. Docker Compose wird validiert.
5. der Stack wird neu gebaut/gestartet.
6. AI3 führt Healthchecks durch.
7. bei Fehler und aktiviertem Rollback wird der vorherige Stand wiederhergestellt.

Damit müssen zukünftige AI3-Updates nicht manuell auf jedem Server eingespielt werden.

## 5. Erneuter Start des Ein-Datei-Installers

Wenn AI3 bereits unter `/opt/ai3` vorhanden ist, darf `AI3-Install.run` erneut gestartet werden. Die vorhandene Installation wird nicht absichtlich gelöscht. Der Installer versucht zunächst einen sicheren Fast-Forward-Updatepfad.

Bei lokalen Änderungen am Git-Arbeitsbaum wird nicht blind überschrieben.

## 6. Hardware

Praktische Ausgangsbasis:

- CPU: AMD64/x86-64
- RAM: mindestens 16 GB empfohlen
- SSD: mindestens 50 GB; für mehrere KI-Modelle deutlich mehr einplanen
- GPU: optional
- NVIDIA-GPU: automatische Erkennung, sofern kompatibel
- Netzwerk: Ethernet empfohlen

Für größere lokale Modelle sind vor allem **VRAM, RAM und SSD-Speicher** entscheidend.

## 7. Netzwerk

AI3 überwacht die LAN-Adresse automatisch. Bei einer DHCP-Änderung werden die Runtime-Netzwerkdaten aktualisiert und Caddy bei Bedarf neu geladen.

**Router-Einstellungen werden nicht automatisch verändert.** Falls AI3 aus dem Internet erreichbar sein soll, müssen die gewünschten Ports am Router einmalig auf den AI3-PC weitergeleitet werden.

Für öffentliches HTTPS müssen zusätzlich DNS und Domain korrekt eingerichtet sein.

## 8. Öffentliche Mailzustellung

Der integrierte Mailserver kann lokal betrieben werden. Für echte Internet-Mailzustellung werden unter anderem eine öffentliche IP, PTR/rDNS, korrekte DNS-Einträge und gegebenenfalls freigeschalteter Port 25 benötigt.

## 9. Fehlerdiagnose

Nach der Installation zuerst den AI3-Status und die Healthchecks verwenden. Für den Installations-/Updatepfad sind insbesondere diese Dateien relevant:

```text
AI3-Install.run
scripts/install-ubuntu.sh
scripts/ensure-host-deps.sh
scripts/setup-local.sh
scripts/update-ai3.sh
scripts/network-refresh.sh
```

Wenn die Weboberfläche nicht erreichbar ist, zuerst die aktuelle LAN-IP des Servers prüfen. AI3 verwendet absichtlich keine fest eingebaute DHCP-Adresse.

## 10. Manuelle Installation für Entwickler

Wer das Repository bereits lokal hat, kann weiterhin direkt den vollständigen Installer starten:

```bash
cd /opt/ai3
sudo chmod +x scripts/*.sh
sudo ./scripts/install-ubuntu.sh
```

Der empfohlene Weg für neue Systeme bleibt jedoch **`AI3-Install.run`**.
