#!/usr/bin/env bash
# Install systemd timer for **periodic** ephemeral / short-lived RPT node cycles.
#
# Default installs a **dry-run** oneshot (safe). Live rebuild requires editing
# the service to set RPT_EPHEMERAL_CONFIRM=yes or re-running with LIVE=1.
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

echo "[rpt-ephemeral] periodic short-lived node timer (period=${PERIOD})"
echo "[rpt-ephemeral] honesty: does not erase provider backups/netflow"
echo "[rpt-ephemeral] honesty: re-ship public node pin if keys regenerate"

mkdir -p "${INSTALL_ROOT}/scripts" "${INSTALL_ROOT}/node"
cp -a "${SCRIPT_DIR}/ephemeral_node.py" "${INSTALL_ROOT}/scripts/" 2>/dev/null || \
  cp -a "${REPO_ROOT}/scripts/ephemeral_node.py" "${INSTALL_ROOT}/scripts/"
# Ensure pure helper module is available under install tree
if [[ -f "${REPO_ROOT}/node/ephemeral_node.py" ]]; then
  cp -a "${REPO_ROOT}/node/ephemeral_node.py" "${INSTALL_ROOT}/node/" 2>/dev/null || true
fi

export PYTHONPATH="${REPO_ROOT}:${INSTALL_ROOT}"
if [[ "$LIVE" == "1" ]]; then
  export RPT_EPHEMERAL_CONFIRM="${RPT_EPHEMERAL_CONFIRM:-yes}"
  "$PY" "${REPO_ROOT}/scripts/ephemeral_node.py" --live --print-service --period "$PERIOD" \
    >/etc/systemd/system/rpt-ephemeral-rebuild.service
else
  "$PY" "${REPO_ROOT}/scripts/ephemeral_node.py" --dry-run --print-service --period "$PERIOD" \
    >/etc/systemd/system/rpt-ephemeral-rebuild.service
fi

"$PY" "${REPO_ROOT}/scripts/ephemeral_node.py" --print-timer --period "$PERIOD" \
  >/etc/systemd/system/rpt-ephemeral-rebuild.timer

systemctl daemon-reload
systemctl enable --now rpt-ephemeral-rebuild.timer
systemctl status rpt-ephemeral-rebuild.timer --no-pager || true

echo "[rpt-ephemeral] installed timer (periodic). Dry-run default unless LIVE=1."
echo "[rpt-ephemeral] manual dry-run: python3 ${INSTALL_ROOT}/scripts/ephemeral_node.py --dry-run"
echo "[rpt-ephemeral] compose: selfhost_node.sh re-applies no-log + host privacy on rebuild step"
echo "[rpt-ephemeral] done"
