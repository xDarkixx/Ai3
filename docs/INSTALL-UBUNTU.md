# AI3 — passendes Ubuntu-System

## Empfohlenes System

Für den AI3-One-Click-Installer ist **Ubuntu Server 24.04 LTS, 64-bit AMD64 (Noble Numbat)** vorgesehen.

Die aktuelle Ubuntu-24.04-Reihe stellt derzeit **Ubuntu 24.04.4** bereit. Das offizielle Server-Installationsimage heißt:

`ubuntu-24.04.4-live-server-amd64.iso`

Offizielle Download-Seite:

https://releases.ubuntu.com/24.04/

Auf der offiziellen Release-Seite sind Desktop und Server getrennt aufgeführt; für AI3 ist das AMD64-Server-Image die passende Wahl.

## Warum Server und nicht Desktop?

AI3 benötigt keine grafische Linux-Oberfläche. Ubuntu Server spart Ressourcen und ist für einen dauerhaft laufenden Docker-Host besser geeignet. Eine Desktop-Installation funktioniert für viele Setups ebenfalls, ist aber nicht das Zielprofil des One-Click-Installers.

## Hardware

Ubuntu selbst hat deutlich niedrigere Mindestanforderungen als ein KI-Server. Für AI3 ist deshalb vor allem das gewünschte Modell entscheidend.

Als praktische Ausgangsbasis:

- CPU: 64-bit x86 / AMD64
- RAM: mindestens 8 GB für einen kleinen lokalen KI-Stack; 16 GB+ sind für größere Modelle deutlich angenehmer
- Speicher: mindestens 25 GB für das Basissystem; für Ollama-Modelle zusätzlich großzügig planen
- GPU: optional; kompatible NVIDIA-GPU wird vom Installer automatisch erkannt
- Netzwerk: Ethernet wird für einen Server empfohlen

Mehr RAM/VRAM und SSD-Speicher werden benötigt, sobald größere Modelle installiert werden.

## Installation

Nach der Ubuntu-Installation:

```bash
cd /opt
sudo git clone https://github.com/xDarkixx/Ai3.git ai3
cd /opt/ai3
sudo chmod +x scripts/install-ubuntu.sh
sudo ./scripts/install-ubuntu.sh
```

Der Installer prüft Ubuntu 24.04, installiert die benötigten Docker-Komponenten, erkennt NVIDIA-GPUs, startet den AI3-Stack und aktiviert den LAN-Watcher.

## Netzwerk nach der Installation

Der AI3-PC darf seine DHCP-Adresse ändern. AI3 erkennt beim Boot und anschließend regelmäßig:

- PC-Name
- LAN-IPv4
- Netzwerkadapter
- Standard-Gateway

Bei einer IP-Änderung werden die LAN-Daten aktualisiert und Caddy neu geladen. Datenbank und Ollama müssen dafür nicht neu gestartet werden.

**Einmalig im Router:** TCP 80 und TCP 443 auf den AI3-PC weiterleiten. Der Router selbst wird von AI3 absichtlich nicht automatisch verändert.

Eine DHCP-Reservierung für den AI3-PC ist zusätzlich empfehlenswert.

## Kosten

Ubuntu Server ist kostenlos verfügbar. AI3 ist für lokale Inferenz ohne kostenpflichtigen KI-API-Anbieter ausgelegt. Eigene Hardware, Strom, Internet und eine optionale öffentliche Domain bleiben normale Infrastrukturkosten.
