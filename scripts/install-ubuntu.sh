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
if [ "${ID:-}" != "ubuntu" ]; then
  echo "AI3 ist für dieses One-Click-System auf Ubuntu 24.04 LTS ausgelegt."
  echo "Erkannt: ${PRETTY_NAME:-unbekannt}"
  exit 1
fi
if [ "${VERSION_ID:-}" != "24.04" ]; then
  echo "Bitte Ubuntu 24.04 LTS verwenden."
  echo "Erkannt: ${PRETTY_NAME:-unbekannt}"
  exit 1
fi

command -v apt-get >/dev/null 2>&1 || { echo "apt-get fehlt."; exit 1; }

echo "[1/6] Installiere Basis-Komponenten ..."
$SUDO apt-get update
$SUDO apt-get install -y ca-certificates curl git python3 gnupg2

if ! command -v docker >/dev/null 2>&1; then
  echo "[2/6] Installiere Docker Engine + Compose ..."
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
  $SUDO systemctl enable --now docker
else
  echo "[2/6] Docker ist bereits installiert."
fi

echo "[3/6] Prüfe Docker + Compose ..."
docker compose version
if ! docker info >/dev/null 2>&1; then
  if getent group docker >/dev/null 2>&1; then
    $SUDO usermod -aG docker "$(id -un)" || true
  fi
  echo "Docker ist für diesen Benutzer nicht erreichbar. Bitte einmal ab- und wieder anmelden und den Installer erneut starten."
  exit 1
fi

GPU_COMPOSE_READY=0
if command -v nvidia-smi >/dev/null 2>&1; then
  echo "[4/6] NVIDIA-GPU gefunden – richte NVIDIA Container Toolkit ein ..."
  GPU_SETUP_OK=1
  if ! command -v nvidia-ctk >/dev/null 2>&1; then
    if ! {
      $SUDO mkdir -p /usr/share/keyrings
      curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | $SUDO gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
      curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | $SUDO tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
      $SUDO apt-get update
      $SUDO apt-get install -y nvidia-container-toolkit
    }; then
      GPU_SETUP_OK=0
    fi
  fi
  if [ "$GPU_SETUP_OK" -eq 1 ] && ! $SUDO nvidia-ctk runtime configure --runtime=docker; then
    GPU_SETUP_OK=0
  fi
  if [ "$GPU_SETUP_OK" -eq 1 ] && ! $SUDO systemctl restart docker; then
    GPU_SETUP_OK=0
  fi
  if [ "$GPU_SETUP_OK" -eq 1 ] && docker run --rm --gpus all nvidia/cuda:12.6.2-base-ubuntu24.04 nvidia-smi >/dev/null 2>&1; then
    GPU_COMPOSE_READY=1
    echo "NVIDIA-Docker-GPU-Test erfolgreich."
  else
    echo "NVIDIA-GPU vorhanden, aber GPU-Container-Test fehlgeschlagen – fahre sicher im CPU-Modus fort."
  fi
else
  echo "[4/6] Keine NVIDIA-GPU erkannt – CPU-Modus."
fi

if [ "$GPU_COMPOSE_READY" -eq 1 ]; then
  export AI3_USE_GPU=1
else
  export AI3_USE_GPU=0
fi

echo "[5/6] Starte AI3 + Ollama + lokales Modell ..."
mkdir -p openclaw
chmod +x scripts/setup-local.sh scripts/doctor.sh
./scripts/setup-local.sh

echo "[6/6] Abschlussprüfung ..."
./scripts/doctor.sh

echo
echo "========================================"
echo " AI3 ONE-CLICK INSTALLATION FERTIG"
echo "========================================"
echo "OS:      Ubuntu 24.04 LTS"
if [ "$GPU_COMPOSE_READY" -eq 1 ]; then echo "Modus:   NVIDIA GPU"; else echo "Modus:   CPU"; fi
echo "AI3:     http://localhost:8080"
echo "OpenClaw: openclaw/ai3-provider.generated.json5"
echo "Daten:   Docker-Volumes ai3-data + ollama-data"
echo "========================================"
