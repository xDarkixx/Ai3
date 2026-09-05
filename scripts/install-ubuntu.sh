#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ "${EUID:-$(id -u)}" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi
command -v apt-get >/dev/null 2>&1 || { echo "Dieser Installer ist für Ubuntu/Debian mit apt gedacht."; exit 1; }

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
  . /etc/os-release
  $SUDO tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-${VERSION_CODENAME}}
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
  if getent group docker >/dev/null 2>&1; then $SUDO usermod -aG docker "$(id -un)" || true; fi
  echo "Docker ist nicht ohne sudo erreichbar. Bitte einmal neu anmelden und den Installer erneut starten."
  exit 1
fi

if command -v nvidia-smi >/dev/null 2>&1; then
  echo "[4/6] NVIDIA-GPU gefunden – richte NVIDIA Container Toolkit ein ..."
  if ! command -v nvidia-ctk >/dev/null 2>&1; then
    $SUDO mkdir -p /usr/share/keyrings
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | $SUDO gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | $SUDO tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null
    $SUDO apt-get update
    $SUDO apt-get install -y nvidia-container-toolkit
  fi
  $SUDO nvidia-ctk runtime configure --runtime=docker
  $SUDO systemctl restart docker
else
  echo "[4/6] Keine NVIDIA-GPU erkannt – CPU-Modus."
fi

echo "[5/6] Starte AI3 + Ollama + lokales Modell ..."
mkdir -p openclaw
chmod +x scripts/setup-local.sh
./scripts/setup-local.sh

echo "[6/6] Abschlussprüfung ..."
docker compose ps
curl -fsS http://localhost:8080/health >/dev/null

echo
echo "========================================"
echo " AI3 ONE-CLICK INSTALLATION FERTIG"
echo "========================================"
echo "AI3:     http://localhost:8080"
echo "OpenClaw: openclaw/ai3-provider.generated.json5"
echo "Daten:   Docker-Volumes ai3-data + ollama-data"
echo "========================================"
