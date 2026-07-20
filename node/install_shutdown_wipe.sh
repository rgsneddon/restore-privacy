#!/usr/bin/env bash
# Install systemd wiring for RPT node shutdown/stop auto-wipe.
#
# - ExecStop on rpt-node.service → runtime wipe (keeps admission keys)
# - rpt-node-shutdown-wipe.service → runs wipe on host halt/reboot
#
# Compose with:
#   - LUKS/dm-crypt (install_disk_encryption.sh) for data at rest
#   - install_host_privacy.sh + nolog for no connection/session/user-info logs
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/opt/restore-privacy}"
SERVICE_NAME="${SERVICE_NAME:-rpt-node}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WIPE_SRC="${SCRIPT_DIR}/rpt_shutdown_wipe.sh"
WIPE_DST="${INSTALL_ROOT}/node/rpt_shutdown_wipe.sh"
UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
SHUTDOWN_UNIT="/etc/systemd/system/rpt-node-shutdown-wipe.service"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "[rpt-wipe-install] run as root" >&2
  exit 1
fi

echo "[rpt-wipe-install] install wipe script"
mkdir -p "${INSTALL_ROOT}/node"
if [[ ! -f "$WIPE_SRC" ]]; then
  echo "[rpt-wipe-install] ERROR: missing ${WIPE_SRC}" >&2
  exit 1
fi
# Avoid "same file" failure when SCRIPT_DIR == INSTALL_ROOT/node (set -e)
src_real="$(readlink -f "$WIPE_SRC" 2>/dev/null || echo "$WIPE_SRC")"
dst_real="$(readlink -f "$WIPE_DST" 2>/dev/null || echo "$WIPE_DST")"
if [[ "$src_real" != "$dst_real" ]]; then
  cp -a "$WIPE_SRC" "$WIPE_DST"
else
  echo "[rpt-wipe-install] wipe script already at ${WIPE_DST}"
fi
chmod 755 "$WIPE_DST" 2>/dev/null || chmod 755 "$WIPE_SRC"

echo "[rpt-wipe-install] wire ExecStop on ${SERVICE_NAME}.service (if present)"
if [[ -f "$UNIT" ]]; then
  if ! grep -q 'rpt_shutdown_wipe.sh' "$UNIT" 2>/dev/null; then
    # Insert ExecStop before Restart= if possible
    if grep -q '^ExecStart=' "$UNIT"; then
      # Append ExecStop after ExecStart block
      tmp="$(mktemp)"
      awk -v wipe="$WIPE_DST" '
        { print }
        /^ExecStart=/ && !done {
          print "ExecStop=" wipe
          print "TimeoutStopSec=30"
          done=1
        }
      ' "$UNIT" >"$tmp"
      mv "$tmp" "$UNIT"
      echo "[rpt-wipe-install] added ExecStop=${WIPE_DST}"
    fi
  else
    echo "[rpt-wipe-install] ExecStop already references wipe script"
  fi
else
  echo "[rpt-wipe-install] WARN: ${UNIT} missing — create via node/install.sh then re-run" >&2
fi

echo "[rpt-wipe-install] host shutdown/reboot wipe unit"
cat >"$SHUTDOWN_UNIT" <<EOF
[Unit]
Description=Restore Privacy RPT best-effort wipe on host shutdown
DefaultDependencies=no
Before=shutdown.target reboot.target halt.target
Conflicts=reboot.target halt.target shutdown.target

[Service]
Type=oneshot
Environment=INSTALL_ROOT=${INSTALL_ROOT}
# Default: runtime only. Set RPT_WIPE_SECRETS_ON_SHUTDOWN=1 for aggressive secrets scrub.
Environment=RPT_WIPE_SECRETS_ON_SHUTDOWN=\${RPT_WIPE_SECRETS_ON_SHUTDOWN:-0}
ExecStart=${WIPE_DST}
TimeoutStartSec=60

[Install]
WantedBy=halt.target reboot.target shutdown.target
EOF

systemctl daemon-reload 2>/dev/null || true
# enable may warn on some hosts; unit files are still installed for halt/reboot
if systemctl enable rpt-node-shutdown-wipe.service 2>/dev/null; then
  echo "[rpt-wipe-install] enabled rpt-node-shutdown-wipe.service"
else
  echo "[rpt-wipe-install] WARN: could not enable shutdown wipe unit (files installed; enable later)" >&2
fi
# Reload node unit so ExecStop takes effect
systemctl daemon-reload 2>/dev/null || true
if systemctl cat rpt-node.service 2>/dev/null | grep -q rpt_shutdown_wipe; then
  echo "[rpt-wipe-install] ExecStop wipe wired on rpt-node.service"
else
  echo "[rpt-wipe-install] WARN: ExecStop wipe not detected on rpt-node.service" >&2
fi

echo "[rpt-wipe-install] honesty: wipe is best-effort local; not provider snapshots"
echo "[rpt-wipe-install] honesty: LUKS protects at rest; unlocked root can still read"
echo "[rpt-wipe-install] no-log: wipe does not enable connection_log/session_log"
echo "[rpt-wipe-install] done"
