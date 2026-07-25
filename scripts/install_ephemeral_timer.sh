#!/usr/bin/env bash
# Install systemd timer for **weekly sequential fleet** wipe/rebuild (exclusive lock).
#
# Default installs a **dry-run** oneshot (safe). Live rebuild requires editing
# the service to set RPT_EPHEMERAL_CONFIRM=yes or re-running with LIVE=1.
#
# NEVER two node instances at once. Order: Iceland first, then Romania only after
# IS is fully rebuilt, then any new catalog peers (node.fleet_wipe).
# Peer residual must be healthy before drain so clients auto residual-failover.
#
# Usage (root):
#   bash scripts/install_ephemeral_timer.sh
#   PERIOD=7d bash scripts/install_ephemeral_timer.sh
#   LIVE=1 RPT_EPHEMERAL_CONFIRM=yes bash scripts/install_ephemeral_timer.sh
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/opt/restore-privacy}"
PERIOD="${PERIOD:-7d}"
LIVE="${LIVE:-0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PY="${INSTALL_ROOT}/venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3 || command -v python)"
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "[rpt-ephemeral] run as root to install systemd units" >&2
  exit 1
fi

echo "[rpt-ephemeral] weekly sequential fleet wipe/rebuild timer (period=${PERIOD})"
echo "[rpt-ephemeral] exclusive lock: never two node wipe instances at once"
echo "[rpt-ephemeral] order: IS → RO → new catalog peers (after prior complete)"
echo "[rpt-ephemeral] failover: preferred entry drain → healthy catalog peer residual"
echo "[rpt-ephemeral] honesty: does not erase provider backups/netflow"
echo "[rpt-ephemeral] honesty: re-ship public node pin if keys regenerate"

mkdir -p "${INSTALL_ROOT}/scripts" "${INSTALL_ROOT}/node" "${INSTALL_ROOT}/var" "${INSTALL_ROOT}/client"
# Copy only when source ≠ dest (in-place install under INSTALL_ROOT is a no-op)
_rpt_cp() {
  local src="$1" dst="$2"
  if [[ -f "$src" ]]; then
    if [[ "$(readlink -f "$src" 2>/dev/null || realpath "$src" 2>/dev/null || echo "$src")" != \
          "$(readlink -f "$dst" 2>/dev/null || realpath "$dst" 2>/dev/null || echo "$dst")" ]]; then
      cp -a "$src" "$dst"
    fi
  fi
}
_rpt_cp "${SCRIPT_DIR}/ephemeral_node.py" "${INSTALL_ROOT}/scripts/ephemeral_node.py"
_rpt_cp "${REPO_ROOT}/scripts/ephemeral_node.py" "${INSTALL_ROOT}/scripts/ephemeral_node.py"
_rpt_cp "${SCRIPT_DIR}/weekly_entry_rebuild.py" "${INSTALL_ROOT}/scripts/weekly_entry_rebuild.py"
_rpt_cp "${REPO_ROOT}/scripts/weekly_entry_rebuild.py" "${INSTALL_ROOT}/scripts/weekly_entry_rebuild.py"
for mod in ephemeral_node.py rebuild_lock.py wipe_preflight.py fleet_wipe.py; do
  _rpt_cp "${REPO_ROOT}/node/${mod}" "${INSTALL_ROOT}/node/${mod}"
done
# Multihop catalog used by fleet_wipe (shared country peers)
_rpt_cp "${REPO_ROOT}/client/multihop.py" "${INSTALL_ROOT}/client/multihop.py"
_rpt_cp "${REPO_ROOT}/client/endpoint.py" "${INSTALL_ROOT}/client/endpoint.py"
_rpt_cp "${REPO_ROOT}/client/__init__.py" "${INSTALL_ROOT}/client/__init__.py"

export PYTHONPATH="${REPO_ROOT}:${INSTALL_ROOT}"
WEEKLY_SCRIPT="${REPO_ROOT}/scripts/weekly_entry_rebuild.py"
if [[ ! -f "$WEEKLY_SCRIPT" ]]; then
  WEEKLY_SCRIPT="${INSTALL_ROOT}/scripts/weekly_entry_rebuild.py"
fi

if [[ "$LIVE" == "1" ]]; then
  export RPT_EPHEMERAL_CONFIRM="${RPT_EPHEMERAL_CONFIRM:-yes}"
  "$PY" "$WEEKLY_SCRIPT" --live --print-service --period "$PERIOD" \
    >/etc/systemd/system/rpt-ephemeral-rebuild.service
else
  "$PY" "$WEEKLY_SCRIPT" --dry-run --print-service --period "$PERIOD" \
    >/etc/systemd/system/rpt-ephemeral-rebuild.service
fi

"$PY" "$WEEKLY_SCRIPT" --print-timer --period "$PERIOD" \
  >/etc/systemd/system/rpt-ephemeral-rebuild.timer

systemctl daemon-reload
systemctl enable --now rpt-ephemeral-rebuild.timer
systemctl status rpt-ephemeral-rebuild.timer --no-pager || true

echo "[rpt-ephemeral] installed weekly sequential fleet timer. Dry-run default unless LIVE=1."
echo "[rpt-ephemeral] manual dry-run: python3 ${INSTALL_ROOT}/scripts/weekly_entry_rebuild.py --dry-run"
echo "[rpt-ephemeral] never concurrent multi-node wipe; exclusive lock fails closed on second start"
echo "[rpt-ephemeral] after IS complete, next timer fire targets RO (then new peers)"
echo "[rpt-ephemeral] compose: selfhost_node.sh re-applies no-log + host privacy on rebuild step"
echo "[rpt-ephemeral] done"
