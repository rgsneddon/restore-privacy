#!/usr/bin/env bash
# Quiet host logging + privacy-oriented host defaults for an RPT node VPS.
# Offline-prep / re-runnable. Does NOT require interactive SSH from the developer machine.
#
# Apply on the node host as root (after or with node/install.sh):
#   bash /opt/restore-privacy/node/install_host_privacy.sh
#
# Complements:
#   - node/nolog.py + systemd StandardOutput=null on rpt-node
#   - node/install_dns.sh (tunnel-only Unbound; no public recursive DNS)
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-rpt-node}"

echo "[rpt-host-privacy] drop leftover app log dirs"
rm -rf /var/log/rpt-node /var/log/restore-privacy 2>/dev/null || true

echo "[rpt-host-privacy] journald: limit retention (best-effort; distro may override)"
mkdir -p /etc/systemd/journald.conf.d
cat >/etc/systemd/journald.conf.d/99-rpt-privacy.conf <<'EOF'
# Restore Privacy operator default: keep journals short; node unit itself uses
# StandardOutput=null / LogLevelMax=emerg (see node/install.sh).
[Journal]
Storage=volatile
RuntimeMaxUse=32M
SystemMaxUse=64M
MaxRetentionSec=1day
EOF
if command -v systemctl >/dev/null 2>&1; then
  systemctl restart systemd-journald 2>/dev/null || true
fi

echo "[rpt-host-privacy] ensure rpt-node unit still has no-log sinks if present"
UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
if [[ -f "$UNIT" ]]; then
  # Do not rewrite whole unit; only warn if logging sinks reappear
  if grep -qE '^StandardOutput=(journal|syslog|kmsg)' "$UNIT" 2>/dev/null; then
    echo "[rpt-host-privacy] WARN: ${UNIT} has StandardOutput to journal — prefer null (re-run node/install.sh)" >&2
  fi
  if grep -qE '^StandardError=(journal|syslog|kmsg)' "$UNIT" 2>/dev/null; then
    echo "[rpt-host-privacy] WARN: ${UNIT} has StandardError to journal — prefer null" >&2
  fi
fi

echo "[rpt-host-privacy] remind: do not enable verbose rsyslog/ulogd peer connection logs for RPT"
echo "[rpt-host-privacy] remind: VPS provider may still log IP-level metadata under their policy"

# Optional: LUKS/dm-crypt data-at-rest + shutdown wipe (strong fallback; non-fatal)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${SKIP_DISK_ENCRYPTION:-0}" != "1" ]] && [[ -f "${SCRIPT_DIR}/install_disk_encryption.sh" ]]; then
  echo "[rpt-host-privacy] disk encryption check (LUKS/dm-crypt; non-destructive)"
  bash "${SCRIPT_DIR}/install_disk_encryption.sh" check || true
fi
if [[ "${SKIP_SHUTDOWN_WIPE:-0}" != "1" ]] && [[ -f "${SCRIPT_DIR}/install_shutdown_wipe.sh" ]]; then
  if [[ "$(id -u)" -eq 0 ]]; then
    echo "[rpt-host-privacy] install shutdown/stop auto-wipe (best-effort runtime scrub)"
    bash "${SCRIPT_DIR}/install_shutdown_wipe.sh" || {
      echo "[rpt-host-privacy] WARN: install_shutdown_wipe.sh failed (non-fatal)" >&2
    }
  else
    echo "[rpt-host-privacy] skip wipe install (not root)"
  fi
fi
echo "[rpt-host-privacy] compose: no-logs + optional LUKS at-rest + wipe on stop/shutdown"
echo "[rpt-host-privacy] done"
