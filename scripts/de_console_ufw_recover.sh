#!/usr/bin/env bash
# Germany residual (167.233.224.5) — paste into Hetzner Cloud Console when SSH is
# filtered after ufw --force enable without OpenSSH allow.
#
# Opens SSH + residual product ports. Does NOT print or embed passwords.
# After recovery: ssh root@167.233.224.5 (key or password).
set -euo pipefail

echo "[de-recover] hostname=$(hostname -f 2>/dev/null || hostname)"
echo "[de-recover] fixing ufw before re-enable..."

if command -v ufw >/dev/null 2>&1; then
  # Order matters: allow before enable
  ufw allow OpenSSH || true
  ufw allow 22/tcp || true
  ufw allow 44044/udp comment 'RPT residual UDP' || true
  ufw allow 8080/tcp comment 'RPT status UI' || true
  # Optional: status host / metrics if used on this box
  ufw --force enable || true
  ufw status verbose || true
else
  echo "[de-recover] ufw not installed; ensuring iptables allows 22 and 44044/udp"
  iptables -I INPUT -p tcp --dport 22 -j ACCEPT || true
  iptables -I INPUT -p udp --dport 44044 -j ACCEPT || true
  iptables -I INPUT -p tcp --dport 8080 -j ACCEPT || true
fi

systemctl enable --now ssh 2>/dev/null || systemctl enable --now sshd 2>/dev/null || true
systemctl is-active ssh 2>/dev/null || systemctl is-active sshd 2>/dev/null || true

# Residual node if installed
if [[ -d /opt/restore-privacy ]]; then
  systemctl list-units --type=service --all 2>/dev/null | grep -i rpt || true
  ss -ulnp 2>/dev/null | grep 44044 || netstat -ulnp 2>/dev/null | grep 44044 || true
fi

echo "[de-recover] done — from laptop: ssh root@167.233.224.5"
echo "[de-recover] then deploy: bash scripts/install_ephemeral_timer.sh only on IS orchestrator;"
echo "[de-recover] DE peer: sync node modules + ensure UDP 44044 + de_node_elgamal.pub"
