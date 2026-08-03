#!/usr/bin/env bash
# Install systemd timer on a **pull agent** host (operator machine or jump box
# with SSH to the residual timer node + git push to origin).
#
# Residual ``rpt-security-audit.timer`` writes AUDIT artifacts locally only.
# This agent pulls those artifacts after each period and **publishes** them so
# restoreprivacy.online ``last audit run`` and ``/AUDIT.md`` advance without a
# manual ``run_security_audit.py`` command on a laptop.
#
# Usage (root on the pull agent, monorepo or INSTALL_ROOT present)::
#
#   bash scripts/install_audit_public_refresh_timer.sh
#   PERIOD=1h bash scripts/install_audit_public_refresh_timer.sh
#
# Environment for the oneshot (set in unit or drop-in)::
#   RPT_SSH_HOST / RPT_SSH_USER / RPT_SSH_KEY  — residual timer host
#   git remote origin must be pushable as the unit user
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/opt/restore-privacy}"
PERIOD="${PERIOD:-1h}"
JITTER_SEC="${JITTER_SEC:-600}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PY="$(command -v python3 || command -v python)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "[rpt-audit-pub] run as root to install systemd units" >&2
  exit 1
fi

mkdir -p "${INSTALL_ROOT}/scripts" "${INSTALL_ROOT}/logs" "${INSTALL_ROOT}/var"
cp -a "${REPO_ROOT}/scripts/sync_audit_artifacts_from_node.py" \
  "${INSTALL_ROOT}/scripts/sync_audit_artifacts_from_node.py"
cp -a "${REPO_ROOT}/scripts/publish_timer_audit_to_status.py" \
  "${INSTALL_ROOT}/scripts/publish_timer_audit_to_status.py"
cp -a "${REPO_ROOT}/scripts/run_security_audit.py" \
  "${INSTALL_ROOT}/scripts/run_security_audit.py" 2>/dev/null || true

# Prefer monorepo as WorkingDirectory when present (git publish)
WORK_DIR="${REPO_ROOT}"
if [[ ! -d "${WORK_DIR}/.git" ]]; then
  WORK_DIR="${INSTALL_ROOT}"
fi

WRAPPER="${INSTALL_ROOT}/scripts/rpt_audit_public_refresh_oneshot.sh"
cat >"${WRAPPER}" <<WRAP
#!/usr/bin/env bash
set -euo pipefail
cd "${WORK_DIR}"
export PYTHONPATH="${WORK_DIR}:${WORK_DIR}/status_page:${INSTALL_ROOT}:${INSTALL_ROOT}/status_page"
# Residual timer host defaults (override in /etc/default/rpt-audit-public-refresh)
if [[ -r /etc/default/rpt-audit-public-refresh ]]; then
  # shellcheck disable=SC1091
  . /etc/default/rpt-audit-public-refresh
fi
export RPT_SSH_HOST="\${RPT_SSH_HOST:-82.221.101.241}"
export RPT_SSH_USER="\${RPT_SSH_USER:-raskul}"
rc=0
${PY} "${INSTALL_ROOT}/scripts/sync_audit_artifacts_from_node.py" --publish \\
  >>"${INSTALL_ROOT}/logs/audit_public_refresh.log" 2>&1 || rc=\$?
if [[ "\$rc" -eq 0 ]]; then
  echo "rpt-audit-public-refresh: OK published timer audit to status deploy"
else
  echo "rpt-audit-public-refresh: FAIL rc=\$rc (see ${INSTALL_ROOT}/logs/audit_public_refresh.log)"
fi
exit "\$rc"
WRAP
chmod 0755 "${WRAPPER}"

cat >/etc/systemd/system/rpt-audit-public-refresh.service <<EOF
[Unit]
Description=Pull residual security-audit timer artifacts and publish to status host
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${WORK_DIR}
ExecStart=${WRAPPER}
Nice=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=rpt-audit-public-refresh

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/rpt-audit-public-refresh.timer <<EOF
[Unit]
Description=Refresh public last audit run from residual timer host every ${PERIOD}

[Timer]
OnBootSec=15m
OnUnitActiveSec=${PERIOD}
RandomizedDelaySec=${JITTER_SEC}
AccuracySec=2m
Persistent=true
Unit=rpt-audit-public-refresh.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now rpt-audit-public-refresh.timer
systemctl start rpt-audit-public-refresh.service || true
systemctl status rpt-audit-public-refresh.timer --no-pager || true

echo "[rpt-audit-pub] installed pull+publish timer (period=${PERIOD})"
echo "[rpt-audit-pub] residual default RPT_SSH_HOST=82.221.101.241"
echo "[rpt-audit-pub] configure /etc/default/rpt-audit-public-refresh for keys"
echo "[rpt-audit-pub] done"
