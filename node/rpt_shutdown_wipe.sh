#!/usr/bin/env bash
# Best-effort wipe of RPT node runtime (and optional secrets) on stop/shutdown.
#
# Invoked by systemd ExecStop / shutdown unit (see install_shutdown_wipe.sh).
# Default: scrub runtime paths only — does NOT delete admission keys on every
# service restart (that would break Restart=always).
#
# Aggressive secrets wipe (host poweroff / seize prep only):
#   RPT_WIPE_SECRETS_ON_SHUTDOWN=1
#
# Honesty: local host only; does not erase VPS provider snapshots or netflow.
# Complements LUKS/dm-crypt at-rest + product no-logs (no connection/session logs).
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/opt/restore-privacy}"
AGGRESSIVE="${RPT_WIPE_SECRETS_ON_SHUTDOWN:-0}"
PYTHON="${INSTALL_ROOT}/venv/bin/python"
export INSTALL_ROOT

log() { echo "[rpt-wipe] $*"; }

log "start (install_root=${INSTALL_ROOT} aggressive_secrets=${AGGRESSIVE})"
log "honesty: best-effort local wipe; not provider backups/netflow"
log "honesty: complements no-logs — does not enable connection/session logs"

# Prefer pure plan from Python when venv exists
if [[ -x "$PYTHON" ]] && [[ -d "${INSTALL_ROOT}/node" || -d "$(dirname "$0")" ]]; then
  ROOT_FOR_PY="${INSTALL_ROOT}"
  if [[ ! -d "${INSTALL_ROOT}/node" ]]; then
    ROOT_FOR_PY="$(cd "$(dirname "$0")/.." && pwd)"
  fi
  TARGETS="$(
    PYTHONPATH="${ROOT_FOR_PY}:${INSTALL_ROOT}" "$PYTHON" - <<'PY' 2>/dev/null || true
import os
from node.disk_encryption import plan_wipe, filter_wipe_targets
root = os.environ.get("INSTALL_ROOT", "/opt/restore-privacy")
agg = os.environ.get("RPT_WIPE_SECRETS_ON_SHUTDOWN", "0").strip() in ("1", "true", "yes")
plan = plan_wipe(install_root=root, aggressive_secrets=agg)
for t in plan["targets"]:
    print(t)
PY
  )"
else
  TARGETS=""
fi

if [[ -z "${TARGETS}" ]]; then
  # Fallback static list (safe runtime only)
  TARGETS="/run/rpt-node.ready
/tmp/rpt-node.tmp
/tmp/rpt-node-runtime
/var/tmp/rpt-node.tmp"
  if [[ "$AGGRESSIVE" == "1" ]]; then
    TARGETS="${TARGETS}
${INSTALL_ROOT}/secrets/node_elgamal.priv
${INSTALL_ROOT}/secrets/node_elgamal.priv.sealed
${INSTALL_ROOT}/secrets/.key_backend_wrap"
  fi
fi

while IFS= read -r target; do
  [[ -z "$target" ]] && continue
  # Safety: never wipe bare /
  if [[ "$target" == "/" ]]; then
    log "skip forbidden path /"
    continue
  fi
  if [[ -e "$target" || -L "$target" ]]; then
    if command -v shred >/dev/null 2>&1 && [[ -f "$target" ]]; then
      shred -u -n 1 "$target" 2>/dev/null || rm -f "$target" 2>/dev/null || true
      log "shredded ${target}"
    else
      rm -rf "$target" 2>/dev/null || true
      log "removed ${target}"
    fi
  fi
done <<< "$TARGETS"

# Drop page cache best-effort (requires root; ignore failures)
if [[ "$(id -u)" -eq 0 ]] && [[ -w /proc/sys/vm/drop_caches ]]; then
  sync 2>/dev/null || true
  echo 3 >/proc/sys/vm/drop_caches 2>/dev/null || true
  log "drop_caches attempted"
fi

# Remove leftover app log dirs if any reappeared (no-log hygiene)
rm -rf /var/log/rpt-node /var/log/restore-privacy 2>/dev/null || true

log "done"
