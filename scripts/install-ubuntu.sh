#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ "${EUID:-$(id -u)}" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi

command -v apt-get >/dev/null 2>&1 || { echo "Dieser Installer ist für Ubuntu/Debian mit apt gedacht."; exit 1; }

if ! command -v docker >/dev/null 2>&1; then
  echo "[1/5] Installiere Docker Engine + Compose ..."
  $SUDO apt-get update
  $SUDO apt-get install -y ca-certificates curl git
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
fi

echo "[2/5] Prüfe Docker Compose ..."
docker compose version

echo "[3/5] Bereite AI3 vor ..."
mkdir -p openclaw
chmod +x scripts/setup-local.sh

# Prefer the invoking user for Docker after installing the daemon.
if [ -n "$SUDO" ] && getent group docker >/dev/null 2>&1; then
  $SUDO usermod -aG docker "$(id -un)" || true
  if ! docker info >/dev/null 2>&1; then
    echo "Docker ist installiert. Für den ersten Lauf bitte einmal neu anmelden oder 'newgrp docker' ausführen."
    echo "Danach erneut: ./scripts/install-ubuntu.sh"
    exit 0
  fi
fi

echo "[4/5] Starte den kompletten AI3-Stack ..."
./scripts/setup-local.sh

echo "[5/5] Installation abgeschlossen."
echo "AI3 läuft lokal auf http://localhost:8080"
echo "Der Stack enthält AI3 + Ollama + das konfigurierte lokale Modell."
echo "Für einen öffentlichen Server sollte anschließend TLS/Reverse-Proxy eingerichtet werden."
