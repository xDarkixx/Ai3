#!/usr/bin/env bash
set -euo pipefail

# Open the AI3 control center when the installer runs on a graphical Ubuntu session.
# On headless servers there is no browser to launch; in that case the URL is printed and
# the installer continues normally.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LAN_IP="$(grep '^AI3_LAN_IP=' .env 2>/dev/null | cut -d= -f2- || true)"
LAN_HOSTNAME="$(grep '^AI3_LAN_HOSTNAME=' .env 2>/dev/null | cut -d= -f2- || true)"
DOMAIN="$(grep '^AI3_DOMAIN=' .env 2>/dev/null | cut -d= -f2- || true)"
URL="https://${LAN_IP:-localhost}"

# Prefer the local LAN address because it works immediately after a fresh install.
if [ -z "$LAN_IP" ] || [ "$LAN_IP" = "127.0.0.1" ]; then
  URL="https://${LAN_HOSTNAME:-${DOMAIN:-localhost}}"
fi

export AI3_WEB_URL="$URL"
echo "AI3 Web UI: $URL"

if command -v xdg-open >/dev/null 2>&1 && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
  if [ -n "${SUDO_USER:-}" ] && id "$SUDO_USER" >/dev/null 2>&1; then
    runuser -u "$SUDO_USER" -- env \
      DISPLAY="${DISPLAY:-}" \
      WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-}" \
      XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u "$SUDO_USER")}" \
      xdg-open "$URL" >/dev/null 2>&1 || true
  else
    xdg-open "$URL" >/dev/null 2>&1 || true
  fi
elif command -v gio >/dev/null 2>&1 && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
  gio open "$URL" >/dev/null 2>&1 || true
else
  echo "Kein grafischer Browser verfügbar (Headless/SSH). Öffne die URL auf einem PC im Netzwerk."
fi
