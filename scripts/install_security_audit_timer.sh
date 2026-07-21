#!/usr/bin/env bash
# Install systemd timer: run security audit ~every 4 hours on the node.
#
# Privacy section A (audit run must not become a leak):
#   - Probes localhost only (RPT_NODE_HOST=127.0.0.1 + RPT_AUDIT_REQUIRE_LOCALHOST)
#   - Does NOT git-push / HTTP-upload AUDIT.md (local write only)
#   - PrivateTmp + dedicated scratch wipe in the runner
#   - Journal: oneshot summary only (StandardOutput=journal short line from ExecStart)
#   - LimitCORE=0, ProtectHome/System, ReadWritePaths limited to install root
#   - Optional non-root User=rpt-audit when useradd succeeds
#   - No outbound live fetches (RPT_AUDIT_NO_OUTBOUND / host statements offline)
#   - Schedule jitter via RandomizedDelaySec (15–30m class)
#
# Writes ${INSTALL_ROOT}/AUDIT.md and status_page copies when present.
# VPN APP Shop can serve local AUDIT.md at /AUDIT.md and /audit.md.
#
# Usage (root on production node):
#   bash scripts/install_security_audit_timer.sh
#   PERIOD=4h bash scripts/install_security_audit_timer.sh
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/opt/restore-privacy}"
PERIOD="${PERIOD:-4h}"
# Jitter window so fire times are not a fixed fingerprint (±15–30 min class)
JITTER_SEC="${JITTER_SEC:-1800}"
AUDIT_USER="${AUDIT_USER:-rpt-audit}"
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

echo "[rpt-audit] security audit timer (period=${PERIOD}, jitter<=${JITTER_SEC}s)"
mkdir -p \
  "${INSTALL_ROOT}/scripts" \
  "${INSTALL_ROOT}/status_page/static" \
  "${INSTALL_ROOT}/status_page/public" \
  "${INSTALL_ROOT}/logs" \
  "${INSTALL_ROOT}/var/audit-scratch"

cp -a "${REPO_ROOT}/scripts/run_security_audit.py" "${INSTALL_ROOT}/scripts/"
# Section B privacy probes (imported by the runner)
if [[ -f "${REPO_ROOT}/scripts/audit_privacy_probes.py" ]]; then
  cp -a "${REPO_ROOT}/scripts/audit_privacy_probes.py" "${INSTALL_ROOT}/scripts/"
fi
# Seed current audit document
if [[ -f "${REPO_ROOT}/AUDIT.md" ]]; then
  cp -a "${REPO_ROOT}/AUDIT.md" "${INSTALL_ROOT}/AUDIT.md"
fi

# Dedicated low-privilege identity (fallback: root oneshot with Protect* still applied)
SERVICE_USER_LINE=""
SERVICE_GROUP_LINE=""
if id -u "${AUDIT_USER}" >/dev/null 2>&1; then
  echo "[rpt-audit] using existing user ${AUDIT_USER}"
else
  if command -v useradd >/dev/null 2>&1; then
    useradd --system --home-dir /nonexistent --shell /usr/sbin/nologin \
      --comment "Restore Privacy security audit" "${AUDIT_USER}" 2>/dev/null \
      || useradd --system --home-dir /nonexistent --shell /bin/false "${AUDIT_USER}" 2>/dev/null \
      || true
  fi
fi
if id -u "${AUDIT_USER}" >/dev/null 2>&1; then
  chown -R "${AUDIT_USER}:${AUDIT_USER}" \
    "${INSTALL_ROOT}/AUDIT.md" \
    "${INSTALL_ROOT}/status_page" \
    "${INSTALL_ROOT}/logs" \
    "${INSTALL_ROOT}/var" \
    2>/dev/null || true
  # scripts readable; secrets never in ReadWritePaths
  chown root:root "${INSTALL_ROOT}/scripts/run_security_audit.py" 2>/dev/null || true
  chmod 0755 "${INSTALL_ROOT}/scripts/run_security_audit.py" 2>/dev/null || true
  # Ensure audit user can read tree for probes (status) but not secrets
  SERVICE_USER_LINE="User=${AUDIT_USER}"
  SERVICE_GROUP_LINE="Group=${AUDIT_USER}"
  echo "[rpt-audit] service will run as ${AUDIT_USER}"
else
  echo "[rpt-audit] WARN: could not create ${AUDIT_USER}; running as root with Protect* floor" >&2
fi

# Wrapper: one-line journal result; never pipes suite dumps to journal
WRAPPER="${INSTALL_ROOT}/scripts/rpt_security_audit_oneshot.sh"
cat >"${WRAPPER}" <<WRAP
#!/usr/bin/env bash
# Local-only audit oneshot — no network exfil of AUDIT.md.
set -euo pipefail
export PYTHONPATH="${INSTALL_ROOT}"
export RPT_INSTALL_ROOT="${INSTALL_ROOT}"
export RPT_AUDIT_PATH="${INSTALL_ROOT}/AUDIT.md"
export RPT_NODE_HOST=127.0.0.1
export RPT_AUDIT_REQUIRE_LOCALHOST=1
export RPT_AUDIT_NO_OUTBOUND=1
export RPT_HOST_STATEMENTS_OFFLINE=1
export TMPDIR="${INSTALL_ROOT}/var/audit-scratch"
mkdir -p "\${TMPDIR}"
# Never git push / curl upload from this job
unset GIT_ASKPASS SSH_ASKPASS
rc=0
"${PY}" "${INSTALL_ROOT}/scripts/run_security_audit.py" --node-only --write --out "${INSTALL_ROOT}/AUDIT.md" \\
  >/dev/null 2>"\${TMPDIR}/audit.err" || rc=\$?
# Wipe ephemeral capture
rm -f "\${TMPDIR}/audit.err" 2>/dev/null || true
find "\${TMPDIR}" -mindepth 1 -delete 2>/dev/null || true
if [[ "\$rc" -eq 0 ]]; then
  echo "rpt-security-audit: OK wrote ${INSTALL_ROOT}/AUDIT.md"
else
  echo "rpt-security-audit: FAIL rc=\$rc (details redacted; see AUDIT.md overall status)"
fi
exit "\$rc"
WRAP
chmod 0755 "${WRAPPER}"
if id -u "${AUDIT_USER}" >/dev/null 2>&1; then
  chown root:root "${WRAPPER}" || true
fi

cat >/etc/systemd/system/rpt-security-audit.service <<EOF
[Unit]
Description=Restore Privacy security audit (AUDIT.md refresh, privacy-hardened)
After=network-online.target
Wants=network-online.target
# No dependency on git remote / outbound publish

[Service]
Type=oneshot
WorkingDirectory=${INSTALL_ROOT}
${SERVICE_USER_LINE}
${SERVICE_GROUP_LINE}
Environment=PYTHONPATH=${INSTALL_ROOT}
Environment=RPT_INSTALL_ROOT=${INSTALL_ROOT}
Environment=RPT_AUDIT_PATH=${INSTALL_ROOT}/AUDIT.md
Environment=RPT_NODE_HOST=127.0.0.1
Environment=RPT_AUDIT_REQUIRE_LOCALHOST=1
Environment=RPT_AUDIT_NO_OUTBOUND=1
Environment=RPT_HOST_STATEMENTS_OFFLINE=1
Environment=TMPDIR=${INSTALL_ROOT}/var/audit-scratch
# Local write only — do not add ExecStartPost git push / curl upload
ExecStart=${WRAPPER}
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
# --- Section A: process / filesystem privacy ---
PrivateTmp=true
NoNewPrivileges=true
LimitCORE=0
LockPersonality=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectControlGroups=true
ProtectKernelModules=true
RestrictSUIDSGID=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
# MDWE omitted: can break CPython on some distros
ReadWritePaths=${INSTALL_ROOT}/AUDIT.md ${INSTALL_ROOT}/status_page ${INSTALL_ROOT}/logs ${INSTALL_ROOT}/var
# Do not grant access to secrets/ for the audit job
InaccessiblePaths=-${INSTALL_ROOT}/secrets
StandardOutput=journal
StandardError=journal
SyslogIdentifier=rpt-security-audit

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/rpt-security-audit.timer <<EOF
[Unit]
Description=Run Restore Privacy security audit every ${PERIOD} (with jitter)

[Timer]
OnBootSec=10m
OnUnitActiveSec=${PERIOD}
# RandomizedDelaySec: ± window so cadence is not a fixed wire fingerprint
RandomizedDelaySec=${JITTER_SEC}
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

echo "[rpt-audit] installed (section A privacy floor)."
echo "[rpt-audit] local probes only: RPT_NODE_HOST=127.0.0.1"
echo "[rpt-audit] no network exfil: unit has no git push / upload"
echo "[rpt-audit] PrivateTmp=true LimitCORE=0 ProtectHome/System + ReadWritePaths"
echo "[rpt-audit] jitter: RandomizedDelaySec=${JITTER_SEC}"
echo "[rpt-audit] outbound: RPT_AUDIT_NO_OUTBOUND=1 (fixtures only)"
echo "[rpt-audit] logs: journalctl -u rpt-security-audit.service (one-line summary)"
echo "[rpt-audit] document: ${INSTALL_ROOT}/AUDIT.md"
echo "[rpt-audit] done"
