#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="$ROOT_DIR/.env"
RUNTIME_DIR="$ROOT_DIR/runtime"
STATE_FILE="$RUNTIME_DIR/lan-info.env"
JSON_FILE="$RUNTIME_DIR/lan-info.json"
mkdir -p "$RUNTIME_DIR"

hostname_value="$(hostname -s 2>/dev/null || hostname 2>/dev/null || true)"
hostname_value="$(printf '%s' "${hostname_value:-ai3-server}" | tr -cd 'A-Za-z0-9.-' | cut -c1-63)"
hostname_value="${hostname_value:-ai3-server}"
interface="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '/dev/ {for(i=1;i<=NF;i++) if($i=="dev") {print $(i+1); exit}}')"
ip_value="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '/src/ {for(i=1;i<=NF;i++) if($i=="src") {print $(i+1); exit}}')"
if [ -z "$ip_value" ]; then
  ip_value="$(hostname -I 2>/dev/null | tr ' ' '\n' | awk '$1 ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ {print $1; exit}')"
fi
ip_value="${ip_value:-127.0.0.1}"
gateway="$(ip -4 route show default 2>/dev/null | awk 'NR==1 {print $3}')"
gateway="${gateway:-unknown}"
updated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Only change the two dynamic values. Secrets and all other user configuration stay untouched.
if [ -f "$ENV_FILE" ]; then
  python3 - "$ENV_FILE" "$hostname_value" "$ip_value" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
hostname = sys.argv[2]
ip = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines()
values = {"AI3_LAN_HOSTNAME": hostname, "AI3_LAN_IP": ip}
seen = set()
out = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in values:
        out.append(f"{key}={values[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, value in values.items():
    if key not in seen:
        out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
  chmod 600 "$ENV_FILE"
fi

old_ip=""
old_hostname=""
[ -f "$STATE_FILE" ] && old_ip="$(grep '^AI3_LAN_IP=' "$STATE_FILE" | cut -d= -f2- || true)"
[ -f "$STATE_FILE" ] && old_hostname="$(grep '^AI3_LAN_HOSTNAME=' "$STATE_FILE" | cut -d= -f2- || true)"

cat > "$STATE_FILE" <<EOF
AI3_LAN_HOSTNAME=$hostname_value
AI3_LAN_IP=$ip_value
AI3_LAN_INTERFACE=$interface
AI3_LAN_GATEWAY=$gateway
AI3_LAN_UPDATED_AT=$updated_at
EOF
chmod 600 "$STATE_FILE"

# This JSON is deliberately limited to non-secret network metadata and is mounted read-only into Caddy.
python3 - "$JSON_FILE" "$hostname_value" "$ip_value" "$interface" "$gateway" "$updated_at" <<'PY'
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
data = {
    "hostname": sys.argv[2],
    "ip": sys.argv[3],
    "interface": sys.argv[4] or "unknown",
    "gateway": sys.argv[5],
    "updated_at": sys.argv[6],
    "router_target": {"tcp": [80, 443]},
    "automatic_lan_refresh": True,
    "router_changes_automatic": False,
}
tmp = path.with_suffix(".json.tmp")
tmp.write_text(json.dumps(data, ensure_ascii=True, separators=(",", ":")) + "\n", encoding="utf-8")
tmp.replace(path)
PY
chmod 644 "$JSON_FILE"

changed=0
if [ "$old_ip" != "$ip_value" ] || [ "$old_hostname" != "$hostname_value" ]; then changed=1; fi

if [ "$changed" -eq 1 ]; then
  echo "[AI3-NETWORK] LAN-Adresse aktualisiert: ${old_ip:-unbekannt} -> $ip_value"
  echo "[AI3-NETWORK] PC-Name: $hostname_value"
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1 && docker compose config -q >/dev/null 2>&1; then
    # Recreate only Caddy so its site-address environment is refreshed. AI3/Ollama stay running.
    docker compose up -d --no-deps caddy >/dev/null 2>&1 || echo "[AI3-NETWORK] Caddy konnte noch nicht aktualisiert werden; nächster Lauf versucht es erneut."
  fi
fi

printf 'AI3 LAN: https://%s | Hostname: %s | Gateway: %s | Interface: %s\n' "$ip_value" "$hostname_value" "$gateway" "${interface:-unknown}"
