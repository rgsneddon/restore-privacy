#!/usr/bin/env bash
# One-shot self-host recipe for Restore Privacy Tunnel (RPT) node.
#
# Privacy-preserving defaults:
#   - no user-info logs (node nolog + install)
#   - admit_unknown_devices free-product enrollment (device Ed25519)
#   - optional tunnel-only DNS (Unbound) + host privacy hardening
#
# Usage (as root on a fresh Debian/Ubuntu VPS):
#   curl -fsSL … | bash   # or:
#   sudo bash scripts/selfhost_node.sh
#
# Env overrides: INSTALL_ROOT, LISTEN_PORT, UI_PORT, SKIP_DNS=1, SKIP_HOST_PRIVACY=1,
#                SKIP_DISK_ENCRYPTION=1, SKIP_SHUTDOWN_WIPE=1
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
NODE_DIR="$REPO_ROOT/node"
INSTALL_ROOT="${INSTALL_ROOT:-/opt/restore-privacy}"
LISTEN_PORT="${LISTEN_PORT:-44044}"
UI_PORT="${UI_PORT:-8080}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "selfhost_node: run as root (sudo)" >&2
  exit 1
fi

echo "=== Restore Privacy self-host ==="
echo "repo:    $REPO_ROOT"
echo "install: $INSTALL_ROOT"
echo "UDP:     $LISTEN_PORT  UI: $UI_PORT"
echo

# 1) Core node install (keys, venv, systemd, no-log)
export INSTALL_ROOT LISTEN_PORT UI_PORT
bash "$NODE_DIR/install.sh"

# 2) Tunnel-only DNS (Unbound on 10.88.0.1) — clients use this as full-tunnel DNS
if [[ "${SKIP_DNS:-0}" != "1" ]]; then
  if [[ -f "$NODE_DIR/install_dns.sh" ]]; then
    echo "[selfhost] tunnel DNS (install_dns.sh)"
    bash "$NODE_DIR/install_dns.sh" || echo "[selfhost] install_dns.sh warning (non-fatal)" >&2
  fi
else
  echo "[selfhost] SKIP_DNS=1 — not installing Unbound tunnel DNS"
fi

# 3) Host privacy hardening (journal, banners, etc. as shipped)
if [[ "${SKIP_HOST_PRIVACY:-0}" != "1" ]]; then
  if [[ -f "$NODE_DIR/install_host_privacy.sh" ]]; then
    echo "[selfhost] host privacy (install_host_privacy.sh)"
    bash "$NODE_DIR/install_host_privacy.sh" || echo "[selfhost] install_host_privacy.sh warning (non-fatal)" >&2
  fi
else
  echo "[selfhost] SKIP_HOST_PRIVACY=1"
fi

echo
echo "=== Self-host complete ==="
echo "Public node key (ship to clients / product/node_elgamal.pub):"
echo "  $INSTALL_ROOT/secrets/node_elgamal.pub"
echo "NEVER distribute: $INSTALL_ROOT/secrets/node_elgamal.priv"
echo
echo "Listen: UDP $LISTEN_PORT  Status UI: TCP $UI_PORT"
echo "Check:  ss -ulnp | grep $LISTEN_PORT"
echo "        curl -s http://127.0.0.1:$UI_PORT/status"
echo
echo "Privacy limits: the VPS provider may still see IP-level metadata (privacy policy §4)."
echo "Data at rest (optional strong fallback): LUKS/dm-crypt — node/install_disk_encryption.sh check"
echo "  Full-disk format is operator-driven (RPT_LUKS_CONFIRM=yes); often needs reimage + console unlock."
echo "Shutdown wipe: install_shutdown_wipe.sh (runtime scrub; not provider snapshots)."
echo "Optional multi-hop, padding, cover traffic: client-side / future hop config — see README."
