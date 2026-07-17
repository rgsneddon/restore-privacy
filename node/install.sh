#!/usr/bin/env bash
# Install RPT custom VPN node (not WireGuard / not OpenVPN).
# Admission: authorized RP client keys only (ElGamal+Pedersen handshake).
# No user-info logs.
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/opt/restore-privacy}"
SERVICE_NAME="rpt-node"
LISTEN_PORT="${LISTEN_PORT:-44044}"
UI_PORT="${UI_PORT:-8080}"
TUN_IFACE="${TUN_IFACE:-rpt0}"
CLIENT_NET="${CLIENT_NET:-10.88.0.0/24}"

export DEBIAN_FRONTEND=noninteractive

echo "[rpt-install] packages"
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y python3 python3-pip python3-venv iptables iproute2 procps
else
  echo "unsupported package manager" >&2
  exit 1
fi

echo "[rpt-install] tree"
mkdir -p "$INSTALL_ROOT/node" "$INSTALL_ROOT/secrets"
chmod 700 "$INSTALL_ROOT/secrets"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -a "$SCRIPT_DIR"/*.py "$INSTALL_ROOT/node/" 2>/dev/null || true
touch "$INSTALL_ROOT/node/__init__.py"

echo "[rpt-install] venv + cryptography"
VENV="$INSTALL_ROOT/venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install 'cryptography>=41' -q

echo "[rpt-install] config (no log sinks, no public open admission)"
PYTHONPATH="$INSTALL_ROOT" "$VENV/bin/python" - <<'PY'
import json, sys
sys.path.insert(0, "/opt/restore-privacy")
from node.config import build_node_config, render_node_config_text, validate_node_config
cfg = build_node_config()
v = validate_node_config(cfg)
if v:
    raise SystemExit("config invalid: " + "; ".join(v))
open("/opt/restore-privacy/rpt-node.json", "w", encoding="utf-8").write(json.dumps(cfg, indent=2) + "\n")
open("/opt/restore-privacy/rpt-node.conf", "w", encoding="utf-8").write(render_node_config_text(cfg))
print("config ok")
PY

echo "[rpt-install] generate admission keys if missing"
PYTHONPATH="$INSTALL_ROOT" "$VENV/bin/python" - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "/opt/restore-privacy")
from node.server import ensure_secrets
ensure_secrets(Path("/opt/restore-privacy/secrets"))
print("secrets ok")
PY

echo "[rpt-install] sysctl forward"
cat >/etc/sysctl.d/99-rpt-node.conf <<'EOF'
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=1
EOF
sysctl -w net.ipv4.ip_forward=1 >/dev/null
sysctl -w net.ipv6.conf.all.forwarding=1 >/dev/null || true

echo "[rpt-install] NAT / firewall"
ip link del "$TUN_IFACE" 2>/dev/null || true
WAN="$(ip -4 route show default | awk '{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}')"
WAN="${WAN:-eth0}"
iptables -t nat -C POSTROUTING -s "$CLIENT_NET" -o "$WAN" -j MASQUERADE 2>/dev/null \
  || iptables -t nat -A POSTROUTING -s "$CLIENT_NET" -o "$WAN" -j MASQUERADE
iptables -C FORWARD -i "$TUN_IFACE" -o "$WAN" -j ACCEPT 2>/dev/null \
  || iptables -I FORWARD 1 -i "$TUN_IFACE" -o "$WAN" -j ACCEPT
iptables -C FORWARD -i "$WAN" -o "$TUN_IFACE" -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null \
  || iptables -I FORWARD 1 -i "$WAN" -o "$TUN_IFACE" -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -C INPUT -p udp --dport "$LISTEN_PORT" -j ACCEPT 2>/dev/null \
  || iptables -I INPUT 1 -p udp --dport "$LISTEN_PORT" -j ACCEPT
iptables -C INPUT -p tcp --dport "$UI_PORT" -j ACCEPT 2>/dev/null \
  || iptables -I INPUT 1 -p tcp --dport "$UI_PORT" -j ACCEPT
if command -v ufw >/dev/null 2>&1; then
  ufw allow "${LISTEN_PORT}/udp" comment "rpt-node" >/dev/null 2>&1 || true
  ufw allow "${UI_PORT}/tcp" comment "rpt-ui" >/dev/null 2>&1 || true
  ufw route allow in on "$TUN_IFACE" out on "$WAN" >/dev/null 2>&1 || true
  ufw route allow in on "$WAN" out on "$TUN_IFACE" >/dev/null 2>&1 || true
fi

echo "[rpt-install] systemd (no journal session logs)"
cat >/etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=Restore Privacy RPT custom VPN node
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/restore-privacy
Environment=PYTHONPATH=/opt/restore-privacy
Environment=RPT_NO_LOG=1
StandardOutput=null
StandardError=null
SyslogIdentifier=
LogLevelMax=emerg
ExecStart=/opt/restore-privacy/venv/bin/python -m node.server --config-json /opt/restore-privacy/rpt-node.json --listen-port ${LISTEN_PORT} --ui-port ${UI_PORT} --secrets-dir /opt/restore-privacy/secrets
Restart=on-failure
RestartSec=2
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_RAW
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_RAW

[Install]
WantedBy=multi-user.target
EOF

rm -rf /var/log/rpt-node /var/log/restore-privacy 2>/dev/null || true
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
systemctl restart "${SERVICE_NAME}.service"
sleep 2
systemctl --no-pager --full status "${SERVICE_NAME}.service" || true
echo "[rpt-install] done port=${LISTEN_PORT} ui=${UI_PORT} wan=${WAN}"
