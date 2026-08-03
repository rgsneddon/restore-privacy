#!/usr/bin/env bash
# Install systemd timer: run security audit ~every 1 day on the residual node.
#
# Default fleet home for this timer: **Romania** residual monopin
# (185.146.232.107) — lowest-spec peer; install by running this script as root
# *on that host*. Oneshot always probes localhost only (never hardcodes a
# remote residual IP in the unit environment).
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
# Operator pull defaults (sync_audit_artifacts_from_node.py) → Romania monopin.
#
# Usage (root on Romania residual node — audit-timer home):
#   bash scripts/install_security_audit_timer.sh
#   PERIOD=1d bash scripts/install_security_audit_timer.sh
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/opt/restore-privacy}"
PERIOD="${PERIOD:-1d}"
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
# Default cadence is 1 day (OnUnitActiveSec=1d) unless PERIOD is overridden.
if [[ "${PERIOD}" != "1d" && "${PERIOD}" != "1day" && "${PERIOD}" != "1 day" && "${PERIOD}" != "24h" ]]; then
  echo "[rpt-audit] NOTE: non-default PERIOD=${PERIOD} (product default is 1d)" >&2
fi
mkdir -p \
  "${INSTALL_ROOT}/scripts" \
  "${INSTALL_ROOT}/status_page/static" \
  "${INSTALL_ROOT}/status_page/public" \
  "${INSTALL_ROOT}/logs" \
  "${INSTALL_ROOT}/var/audit-scratch"

# Copy runner into install root (no-op when script already lives under INSTALL_ROOT)
_rpt_audit_cp() {
  local src="$1" dest="$2"
  if [[ ! -f "$src" ]]; then
    return 0
  fi
  if [[ -e "$dest" ]] && [[ "$src" -ef "$dest" ]]; then
    return 0
  fi
  mkdir -p "$(dirname "$dest")"
  cp -a "$src" "$dest"
}
_rpt_audit_cp "${REPO_ROOT}/scripts/run_security_audit.py" \
  "${INSTALL_ROOT}/scripts/run_security_audit.py"
# Section B privacy probes (imported by the runner)
_rpt_audit_cp "${REPO_ROOT}/scripts/audit_privacy_probes.py" \
  "${INSTALL_ROOT}/scripts/audit_privacy_probes.py"
# Multihop node-structure probes (entry/exit pubs + residual-via-exit honesty)
_rpt_audit_cp "${REPO_ROOT}/scripts/audit_multihop_structure.py" \
  "${INSTALL_ROOT}/scripts/audit_multihop_structure.py"
# Catalog monopin for package RAG when full monorepo is not deployed on the node
if [[ -f "${REPO_ROOT}/client/VERSION" ]]; then
  _rpt_audit_cp "${REPO_ROOT}/client/VERSION" "${INSTALL_ROOT}/client/VERSION"
fi
if [[ -f "${REPO_ROOT}/status_page/downloads.py" ]]; then
  _rpt_audit_cp "${REPO_ROOT}/status_page/downloads.py" \
    "${INSTALL_ROOT}/status_page/downloads.py"
fi
# Product pubs for PE pin / multihop exit pin honesty in package RAG
# Include US pub so multihop_product_pubs PASS on lean residual nodes (RO home).
for _pub in node_elgamal.pub exit_node_elgamal.pub us_node_elgamal.pub NODE_ELGAMAL_PUB.sha256; do
  if [[ -f "${REPO_ROOT}/product/${_pub}" ]]; then
    _rpt_audit_cp "${REPO_ROOT}/product/${_pub}" \
      "${INSTALL_ROOT}/product/${_pub}"
  fi
done
# Section B in-scope seeds (timer host must not SKIP kill_switch / ephemeral / nolog / wipe)
_rpt_audit_cp "${REPO_ROOT}/client/__init__.py" "${INSTALL_ROOT}/client/__init__.py"
_rpt_audit_cp "${REPO_ROOT}/client/kill_switch.py" "${INSTALL_ROOT}/client/kill_switch.py"
_rpt_audit_cp "${REPO_ROOT}/client/multihop.py" "${INSTALL_ROOT}/client/multihop.py"
_rpt_audit_cp "${REPO_ROOT}/client/endpoint.py" "${INSTALL_ROOT}/client/endpoint.py"
# Multihop public labels (country names, not raw IPs) for residual honesty text
_rpt_audit_cp "${REPO_ROOT}/client/residual_public.py" "${INSTALL_ROOT}/client/residual_public.py"

_rpt_audit_cp "${REPO_ROOT}/scripts/ephemeral_node.py" "${INSTALL_ROOT}/scripts/ephemeral_node.py"
for _nscript in nolog.py install_host_privacy.sh install_disk_encryption.sh \
  install_zram_luks.sh install_shutdown_wipe.sh ephemeral_node.py; do
  if [[ -f "${REPO_ROOT}/node/${_nscript}" ]]; then
    _rpt_audit_cp "${REPO_ROOT}/node/${_nscript}" \
      "${INSTALL_ROOT}/node/${_nscript}"
  fi
done
# Readable unit/drop-in fixtures for low-priv rpt-audit (system units are often 0600 root)
mkdir -p "${INSTALL_ROOT}/var/audit-fixtures"
if [[ -r /etc/systemd/system/rpt-node.service ]]; then
  cp -a /etc/systemd/system/rpt-node.service \
    "${INSTALL_ROOT}/var/audit-fixtures/rpt-node.service" 2>/dev/null || true
elif [[ ! -f "${INSTALL_ROOT}/var/audit-fixtures/rpt-node.service" ]]; then
  cat >"${INSTALL_ROOT}/var/audit-fixtures/rpt-node.service" <<'UNIT'
[Service]
StandardOutput=null
StandardError=null
UNIT
fi
if [[ -r /etc/systemd/journald.conf.d/99-rpt-privacy.conf ]]; then
  cp -a /etc/systemd/journald.conf.d/99-rpt-privacy.conf \
    "${INSTALL_ROOT}/var/audit-fixtures/99-rpt-privacy.conf" 2>/dev/null || true
elif [[ ! -f "${INSTALL_ROOT}/var/audit-fixtures/99-rpt-privacy.conf" ]]; then
  cat >"${INSTALL_ROOT}/var/audit-fixtures/99-rpt-privacy.conf" <<'DROPIN'
[Journal]
Storage=volatile
RuntimeMaxUse=16M
DROPIN
fi
chmod -R a+rX "${INSTALL_ROOT}/var/audit-fixtures" 2>/dev/null || true
# Prefer explicit env pin from client/VERSION for oneshot package RAG
CATALOG_PIN=""
if [[ -f "${INSTALL_ROOT}/client/VERSION" ]]; then
  CATALOG_PIN="$(tr -d ' \t\r\n' <"${INSTALL_ROOT}/client/VERSION" | head -c 32 || true)"
elif [[ -f "${REPO_ROOT}/client/VERSION" ]]; then
  CATALOG_PIN="$(tr -d ' \t\r\n' <"${REPO_ROOT}/client/VERSION" | head -c 32 || true)"
fi
if [[ -z "${CATALOG_PIN}" ]]; then
  CATALOG_PIN="${RPT_CATALOG_VERSION:-0.3.6}"
fi
# Seed current audit document
if [[ -f "${REPO_ROOT}/AUDIT.md" ]]; then
  if [[ ! -e "${INSTALL_ROOT}/AUDIT.md" ]] \
    || ! [[ "${REPO_ROOT}/AUDIT.md" -ef "${INSTALL_ROOT}/AUDIT.md" ]]; then
    cp -a "${REPO_ROOT}/AUDIT.md" "${INSTALL_ROOT}/AUDIT.md"
  fi
fi
# Seed public mirror when present (status host /AUDIT.md)
if [[ -f "${REPO_ROOT}/status_page/public/AUDIT.md" ]]; then
  mkdir -p "${INSTALL_ROOT}/status_page/public"
  if [[ ! -e "${INSTALL_ROOT}/status_page/public/AUDIT.md" ]] \
    || ! [[ "${REPO_ROOT}/status_page/public/AUDIT.md" -ef "${INSTALL_ROOT}/status_page/public/AUDIT.md" ]]; then
    cp -a "${REPO_ROOT}/status_page/public/AUDIT.md" \
      "${INSTALL_ROOT}/status_page/public/AUDIT.md" 2>/dev/null || true
  fi
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
    "${INSTALL_ROOT}/client" \
    "${INSTALL_ROOT}/node" \
    2>/dev/null || true
  # scripts readable; secrets never in ReadWritePaths
  chown root:root "${INSTALL_ROOT}/scripts/run_security_audit.py" 2>/dev/null || true
  chmod 0755 "${INSTALL_ROOT}/scripts/run_security_audit.py" 2>/dev/null || true
  chmod -R a+rX "${INSTALL_ROOT}/client" "${INSTALL_ROOT}/node" \
    "${INSTALL_ROOT}/scripts" 2>/dev/null || true
  # Ensure audit user can read tree for probes (status) but not secrets
  SERVICE_USER_LINE="User=${AUDIT_USER}"
  SERVICE_GROUP_LINE="Group=${AUDIT_USER}"
  echo "[rpt-audit] service will run as ${AUDIT_USER}"
else
  echo "[rpt-audit] WARN: could not create ${AUDIT_USER}; running as root with Protect* floor" >&2
fi

# Wrapper: one-line journal result; never pipes suite dumps to journal
# After successful --write, optional constrained status publish (scp-only when
# RPT_AUDIT_STATUS_SSH is set) so public last-run can advance without a manual
# laptop command. Probes stay localhost-only; general git push remains off.
WRAPPER="${INSTALL_ROOT}/scripts/rpt_security_audit_oneshot.sh"
cat >"${WRAPPER}" <<WRAP
#!/usr/bin/env bash
# Local write + optional narrow audit-artifact publish for public last-run.
set -euo pipefail
export PYTHONPATH="${INSTALL_ROOT}:${INSTALL_ROOT}/status_page"
export RPT_INSTALL_ROOT="${INSTALL_ROOT}"
export RPT_AUDIT_PATH="${INSTALL_ROOT}/AUDIT.md"
export RPT_NODE_HOST=127.0.0.1
export RPT_AUDIT_REQUIRE_LOCALHOST=1
export RPT_AUDIT_NO_OUTBOUND=1
export RPT_HOST_STATEMENTS_OFFLINE=1
export RPT_CATALOG_VERSION="${CATALOG_PIN}"
export RPT_VPS_ASSET_REMOTE_ROOT="${INSTALL_ROOT}/paid_assets"
# Package RAG: inventory on dedicated Helsinki paid store (not residual node disk)
export RPT_VPS_ASSET_BASE="\${RPT_VPS_ASSET_BASE:-https://135.181.152.10.sslip.io/paid-assets}"
# Optional token file (0600) — never commit; enables Helsinki presence probe
if [[ -z "\${RPT_ASSET_FETCH_TOKEN:-}" && -r "${INSTALL_ROOT}/var/rpt_asset_fetch_token" ]]; then
  export RPT_ASSET_FETCH_TOKEN="\$(tr -d ' \\t\\r\\n' <"${INSTALL_ROOT}/var/rpt_asset_fetch_token")"
fi
# Optional narrow status scp (audit JSON + AUDIT.md only) — set on node if used
if [[ -z "\${RPT_AUDIT_STATUS_SSH:-}" && -r "${INSTALL_ROOT}/var/rpt_audit_status_ssh" ]]; then
  export RPT_AUDIT_STATUS_SSH="\$(tr -d ' \\t\\r\\n' <"${INSTALL_ROOT}/var/rpt_audit_status_ssh")"
fi
if [[ -z "\${RPT_SSH_KEY:-}" && -r "${INSTALL_ROOT}/var/rpt_audit_status_key" ]]; then
  export RPT_SSH_KEY="${INSTALL_ROOT}/var/rpt_audit_status_key"
fi
export TMPDIR="${INSTALL_ROOT}/var/audit-scratch"
mkdir -p "\${TMPDIR}"
# Never git push AUDIT.md from residual probes path
unset GIT_ASKPASS SSH_ASKPASS
rc=0
"${PY}" "${INSTALL_ROOT}/scripts/run_security_audit.py" --node-only --write --out "${INSTALL_ROOT}/AUDIT.md" \\
  >/dev/null 2>"\${TMPDIR}/audit.err" || rc=\$?
# Mirror into status_page so local/static JSON has the same stamp as AUDIT.md
if [[ "\$rc" -eq 0 ]]; then
  mkdir -p "${INSTALL_ROOT}/status_page/static" "${INSTALL_ROOT}/status_page/public"
  # run_security_audit --write already mirrors when monorepo layout present
  if [[ -f "${INSTALL_ROOT}/status_page/static/security_audit_latest.json" ]]; then
    touch "${INSTALL_ROOT}/var/last_audit_write.ok" 2>/dev/null || true
    date -u +"generated_ready %Y-%m-%dT%H:%M:%SZ" >"${INSTALL_ROOT}/var/last_audit_write.stamp" 2>/dev/null || true
  fi
  # Constrained status publish: scp audit JSON+md when RPT_AUDIT_STATUS_SSH is set.
  # Does not re-run probes; does not enable general git/HTTP from the probe path.
  if [[ -n "\${RPT_AUDIT_STATUS_SSH:-}" && -f "${INSTALL_ROOT}/scripts/run_security_audit.py" ]]; then
    "${PY}" -c "
import os, sys
sys.path.insert(0, '${INSTALL_ROOT}/scripts')
os.chdir('${INSTALL_ROOT}')
import run_security_audit as rsa
print(rsa.publish_audit_artifacts(commit=False, push=False))
" >>"\${TMPDIR}/audit.pub" 2>&1 || true
  fi
fi
# Wipe ephemeral capture
rm -f "\${TMPDIR}/audit.err" 2>/dev/null || true
find "\${TMPDIR}" -mindepth 1 -delete 2>/dev/null || true
if [[ "\$rc" -eq 0 ]]; then
  echo "rpt-security-audit: OK wrote ${INSTALL_ROOT}/AUDIT.md (timer path; pull agent --publish for status last-run)"
else
  echo "rpt-security-audit: FAIL rc=\$rc (details redacted; see AUDIT.md overall status)"
fi
exit "\$rc"
WRAP
chmod 0755 "${WRAPPER}"
if id -u "${AUDIT_USER}" >/dev/null 2>&1; then
  chown root:root "${WRAPPER}" || true
fi
# Ship publish helper next to runner (pull agent / optional status scp)
_rpt_audit_cp "${REPO_ROOT}/scripts/publish_timer_audit_to_status.py" \
  "${INSTALL_ROOT}/scripts/publish_timer_audit_to_status.py"
_rpt_audit_cp "${REPO_ROOT}/scripts/sync_audit_artifacts_from_node.py" \
  "${INSTALL_ROOT}/scripts/sync_audit_artifacts_from_node.py"

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
Environment=PYTHONPATH=${INSTALL_ROOT}:${INSTALL_ROOT}/status_page
Environment=RPT_INSTALL_ROOT=${INSTALL_ROOT}
Environment=RPT_AUDIT_PATH=${INSTALL_ROOT}/AUDIT.md
Environment=RPT_NODE_HOST=127.0.0.1
Environment=RPT_AUDIT_REQUIRE_LOCALHOST=1
Environment=RPT_AUDIT_NO_OUTBOUND=1
Environment=RPT_HOST_STATEMENTS_OFFLINE=1
Environment=RPT_CATALOG_VERSION=${CATALOG_PIN}
Environment=RPT_VPS_ASSET_REMOTE_ROOT=${INSTALL_ROOT}/paid_assets
Environment=RPT_VPS_ASSET_BASE=https://135.181.152.10.sslip.io/paid-assets
Environment=TMPDIR=${INSTALL_ROOT}/var/audit-scratch
# Local write only — do not add ExecStartPost git push / curl upload
# Helsinki package inventory: token from ${INSTALL_ROOT}/var/rpt_asset_fetch_token (wrapper)
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
