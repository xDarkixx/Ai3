#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ "${EUID:-$(id -u)}" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi

if [ ! -r /etc/os-release ]; then
  echo "Kann das Betriebssystem nicht erkennen."
  exit 1
fi
. /etc/os-release
if [ "${ID:-}" != "ubuntu" ] || [ "${VERSION_ID:-}" != "24.04" ]; then
  echo "AI3 One-Click benötigt Ubuntu 24.04 LTS. Erkannt: ${PRETTY_NAME:-unbekannt}"
  exit 1
fi
command -v apt-get >/dev/null 2>&1 || { echo "apt-get fehlt."; exit 1; }

echo "[1/7] Installiere Basis-Komponenten ..."
$SUDO apt-get update
$SUDO apt-get install -y ca-certificates curl git python3 gnupg2

if ! command -v docker >/dev/null 2>&1; then
  echo "[2/7] Installiere Docker Engine + Compose ..."
  $SUDO install -m 0755 -d /etc/apt/keyrings
  if [ ! -f /etc/apt/keyrings/docker.asc ]; then
    $SUDO curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    $SUDO chmod a+r /etc/apt/keyrings/docker.asc
  fi
  $SUDO tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  $SUDO apt-get update
  $SUDO apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
$SUDO systemctl enable --now docker

echo "[3/7] Prüfe Docker + Compose ..."
docker compose version
docker info >/dev/null 2>&1 || {
  if getent group docker >/dev/null 2>&1; then $SUDO usermod -aG docker "$(id -un)" || true; fi
  echo "Docker ist für diesen Benutzer noch nicht erreichbar. Nach erneuter Anmeldung Installer erneut starten."
  exit 1
}

GPU_COMPOSE_READY=0
if command -v nvidia-smi >/dev/null 2>&1; then
  echo "[4/7] NVIDIA-GPU erkannt – prüfe Container-Runtime ..."
  GPU_SETUP_OK=1
  if ! command -v nvidia-ctk >/dev/null 2>&1; then
    if ! {
      $SUDO mkdir -p /usr/share/keyrings
      curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | $SUDO gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
      curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#' | $SUDO tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
      $SUDO apt-get update
      $SUDO apt-get install -y nvidia-container-toolkit
    }; then GPU_SETUP_OK=0; fi
  fi
  if [ "$GPU_SETUP_OK" -eq 1 ] && ! $SUDO nvidia-ctk runtime configure --runtime=docker; then GPU_SETUP_OK=0; fi
  if [ "$GPU_SETUP_OK" -eq 1 ] && ! $SUDO systemctl restart docker; then GPU_SETUP_OK=0; fi
  if [ "$GPU_SETUP_OK" -eq 1 ] && docker run --rm --gpus all nvidia/cuda:12.6.2-base-ubuntu24.04 nvidia-smi >/dev/null 2>&1; then
    GPU_COMPOSE_READY=1
    echo "NVIDIA-Docker-GPU-Test erfolgreich."
  else
    echo "GPU vorhanden, GPU-Container-Test fehlgeschlagen – CPU-Modus."
  fi
else
  echo "[4/7] Keine NVIDIA-GPU erkannt – CPU-Modus."
fi

export AI3_USE_GPU="$GPU_COMPOSE_READY"

echo "[5/7] Installiere und starte den kompletten AI3-Stack ..."
mkdir -p openclaw
chmod +x scripts/setup-local.sh scripts/setup-mail.sh scripts/doctor.sh scripts/mail-check.sh 2>/dev/null || true
./scripts/setup-local.sh

# Nur eine bereits aktivierte UFW-Firewall wird verändert; UFW wird nicht ungefragt aktiviert,
# damit eine bestehende SSH-Verbindung nicht versehentlich ausgesperrt wird.
if command -v ufw >/dev/null 2>&1 && $SUDO ufw status | grep -q "Status: active"; then
  for p in 80 443 25 465 587 110 143 993 995 4190; do $SUDO ufw allow "$p/tcp" >/dev/null || true; done
fi

echo "[6/7] Starte Mailserver und führe Abschlussdiagnose aus ..."
./scripts/setup-mail.sh
./scripts/doctor.sh

echo "[7/7] Verifiziere persistentes Restart-Verhalten ..."
docker compose ps

echo
echo "========================================"
echo " AI3 ONE-CLICK INSTALLATION FERTIG"
echo "========================================"
if [ "$GPU_COMPOSE_READY" -eq 1 ]; then echo "Modus:   NVIDIA GPU"; else echo "Modus:   CPU"; fi
DOMAIN="$(grep '^AI3_DOMAIN=' .env | cut -d= -f2-)"
echo "AI3:     https://$DOMAIN"
echo "Mail:    https://mail.$DOMAIN"
echo "OpenClaw: openclaw/ai3-provider.generated.json5"
echo "Neustart: automatisch über Docker restart=unless-stopped"
echo "Router:  nur notwendige Portweiterleitungen 80/443 + Mailports"
echo "========================================"
