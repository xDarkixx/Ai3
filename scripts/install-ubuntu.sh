#!/usr/bin/env bash
set -euo pipefail

# Re-exec as root so a fresh Ubuntu installation does not stop because Docker
# group membership has not been refreshed yet.
if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || { echo "sudo fehlt. Bitte als root ausführen."; exit 1; }
  exec sudo -E bash "$0" "$@"
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
SUDO=""

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
apt-get update
apt-get install -y ca-certificates curl git python3 gnupg2 iproute2

if ! command -v docker >/dev/null 2>&1; then
  echo "[2/7] Installiere Docker Engine + Compose ..."
  install -m 0755 -d /etc/apt/keyrings
  if [ ! -f /etc/apt/keyrings/docker.asc ]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
  fi
  tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker

echo "[3/7] Prüfe Docker + Compose ..."
docker compose version
docker info >/dev/null

GPU_COMPOSE_READY=0
if command -v nvidia-smi >/dev/null 2>&1; then
  echo "[4/7] NVIDIA-GPU erkannt – prüfe Container-Runtime ..."
  GPU_SETUP_OK=1
  if ! command -v nvidia-ctk >/dev/null 2>&1; then
    if ! {
      mkdir -p /usr/share/keyrings
      curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
      curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#' | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
      apt-get update
      apt-get install -y nvidia-container-toolkit
    }; then GPU_SETUP_OK=0; fi
  fi
  if [ "$GPU_SETUP_OK" -eq 1 ] && ! nvidia-ctk runtime configure --runtime=docker; then GPU_SETUP_OK=0; fi
  if [ "$GPU_SETUP_OK" -eq 1 ] && ! systemctl restart docker; then GPU_SETUP_OK=0; fi
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

# Nur eine bereits aktivierte UFW-Firewall wird verändert; UFW wird nicht ungefragt aktiviert.
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  for p in 80 443 25 465 587 110 143 993 995 4190; do ufw allow "$p/tcp" >/dev/null || true; done
fi

echo "[6/7] Starte Mailserver und führe Abschlussdiagnose aus ..."
./scripts/setup-mail.sh
./scripts/doctor.sh

echo "[7/7] Verifiziere persistentes Restart-Verhalten ..."
docker compose ps

LAN_HOSTNAME="$(grep '^AI3_LAN_HOSTNAME=' .env | cut -d= -f2- || true)"
LAN_IP="$(grep '^AI3_LAN_IP=' .env | cut -d= -f2- || true)"
DOMAIN="$(grep '^AI3_DOMAIN=' .env | cut -d= -f2-)"

echo
echo "========================================"
echo " AI3 ONE-CLICK INSTALLATION FERTIG"
echo "========================================"
if [ "$GPU_COMPOSE_READY" -eq 1 ]; then echo "Modus:      NVIDIA GPU"; else echo "Modus:      CPU"; fi
echo "PC-Name:    $LAN_HOSTNAME"
echo "LAN-IP:     $LAN_IP"
echo "AI3 LAN:    https://$LAN_IP"
echo "AI3 Name:   https://$LAN_HOSTNAME"
echo "AI3 Public: https://$DOMAIN"
echo "Mail:       https://mail.$DOMAIN"
echo "OpenClaw:   openclaw/ai3-provider.generated.json5"
echo "Neustart:   automatisch über Docker restart=unless-stopped"
echo
echo "ROUTER-PORTFREIGABE:"
echo "  TCP 80  -> $LAN_IP:80"
echo "  TCP 443 -> $LAN_IP:443"
echo "  Mail nur bei öffentlicher Mailzustellung: 25,465,587,110,143,993,995,4190 -> $LAN_IP"
echo "========================================"
