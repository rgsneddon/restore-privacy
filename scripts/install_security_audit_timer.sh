#!/usr/bin/env bash
# Install systemd timer: run security audit every 4 hours on the node.
#
# Writes /opt/restore-privacy/AUDIT.md (and status_page copy when present).
# Does not auto-push to GitHub (node may lack credentials); status page can
# serve the local AUDIT.md at /AUDIT.md and /audit.md.
#
# Usage (root on production node):
#   bash scripts/install_security_audit_timer.sh
#   PERIOD=4h bash scripts/install_security_audit_timer.sh
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/opt/restore-privacy}"
PERIOD="${PERIOD:-4h}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PY="${INSTALL_ROOT}/venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3 || command -v python)"
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "[rpt-audit] run as root to install systemd units" >&2
  exit 1
fi

echo "[rpt-audit] security audit timer (period=${PERIOD})"
mkdir -p "${INSTALL_ROOT}/scripts" "${INSTALL_ROOT}/status_page/static" "${INSTALL_ROOT}/logs"
cp -a "${REPO_ROOT}/scripts/run_security_audit.py" "${INSTALL_ROOT}/scripts/"
# Seed current audit document
if [[ -f "${REPO_ROOT}/AUDIT.md" ]]; then
  cp -a "${REPO_ROOT}/AUDIT.md" "${INSTALL_ROOT}/AUDIT.md"
fi

cat >/etc/systemd/system/rpt-security-audit.service <<EOF
[Unit]
Description=Restore Privacy security audit (AUDIT.md refresh)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${INSTALL_ROOT}
Environment=PYTHONPATH=${INSTALL_ROOT}
Environment=RPT_INSTALL_ROOT=${INSTALL_ROOT}
Environment=RPT_AUDIT_PATH=${INSTALL_ROOT}/AUDIT.md
Environment=RPT_NODE_HOST=127.0.0.1
ExecStart=${PY} ${INSTALL_ROOT}/scripts/run_security_audit.py --node-only --write --out ${INSTALL_ROOT}/AUDIT.md
# If full tree with tests/ is installed, prefer full suite:
# ExecStart=${PY} ${INSTALL_ROOT}/scripts/run_security_audit.py --write --out ${INSTALL_ROOT}/AUDIT.md
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/rpt-security-audit.timer <<EOF
[Unit]
Description=Run Restore Privacy security audit every ${PERIOD}

[Timer]
OnBootSec=10m
OnUnitActiveSec=${PERIOD}
AccuracySec=5m
Persistent=true
Unit=rpt-security-audit.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now rpt-security-audit.timer
# Kick one run now
systemctl start rpt-security-audit.service || true
systemctl status rpt-security-audit.timer --no-pager || true

echo "[rpt-audit] installed. Logs: journalctl -u rpt-security-audit.service"
echo "[rpt-audit] document: ${INSTALL_ROOT}/AUDIT.md"
echo "[rpt-audit] status page should serve /AUDIT.md and /audit.md from install root"
echo "[rpt-audit] done"
