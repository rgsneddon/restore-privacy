#!/usr/bin/env bash
# Operator helper: LUKS + dm-crypt full-disk / data-volume encryption for RPT node.
#
# Protects **data at rest** when the volume is locked or the host is powered off.
# Combines with product **no-logs** (node/nolog.py, install_host_privacy.sh) and
# shutdown auto-wipe (install_shutdown_wipe.sh). Does NOT reintroduce connection,
# session, or user-info logging sinks.
#
# Usage (as root on Linux node):
#   bash node/install_disk_encryption.sh check          # non-destructive
#   bash node/install_disk_encryption.sh dry-run /dev/sdX
#   RPT_LUKS_CONFIRM=yes bash node/install_disk_encryption.sh format /dev/sdX
#   bash node/install_disk_encryption.sh open /dev/sdX
#   bash node/install_disk_encryption.sh status
#
# Honesty:
#   - LUKS/dm-crypt does not protect a live unlocked volume against root.
#   - Does not erase VPS provider snapshots/netflow.
#   - Never runs luksFormat without RPT_LUKS_CONFIRM=yes and an explicit device.
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-/opt/restore-privacy}"
MAPPER_NAME="${RPT_LUKS_MAPPER:-rpt-crypt}"
MOUNT_POINT="${RPT_LUKS_MOUNT:-/mnt/rpt-data}"
ACTION="${1:-check}"
DEVICE="${2:-}"

log() { echo "[rpt-luks] $*"; }
warn() { echo "[rpt-luks] WARN: $*" >&2; }
die() { echo "[rpt-luks] ERROR: $*" >&2; exit 1; }

echo "[rpt-luks] LUKS / dm-crypt data-at-rest helper (cryptsetup)"
echo "[rpt-luks] Complements no-logs design (nolog + host privacy) + shutdown wipe"
echo "[rpt-luks] Honesty: encryption protects at rest only; unlocked volumes are readable by root"
echo "[rpt-luks] Honesty: auto-wipe / FDE do not erase VPS provider backups or netflow"

need_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    die "run as root (sudo) for ${ACTION}"
  fi
}

cmd_check() {
  log "check mode (non-destructive)"
  if command -v cryptsetup >/dev/null 2>&1; then
    log "cryptsetup: $(command -v cryptsetup)"
    cryptsetup --version 2>/dev/null | head -n1 || true
  else
    warn "cryptsetup not installed — apt-get install -y cryptsetup cryptsetup-bin"
    if command -v apt-get >/dev/null 2>&1; then
      log "hint: apt-get install -y cryptsetup cryptsetup-bin"
    fi
  fi
  if lsmod 2>/dev/null | grep -qE 'dm_crypt|dm-crypt'; then
    log "dm-crypt kernel module appears loaded"
  else
    warn "dm-crypt module not listed (may load on first open)"
  fi
  if command -v dmsetup >/dev/null 2>&1; then
    log "dmsetup: $(dmsetup version 2>/dev/null | head -n1 || echo present)"
  fi
  log "install_root=${INSTALL_ROOT}"
  log "no-log: keep StandardOutput=null on rpt-node; do not enable connection/session logs"
  log "next: dry-run DEVICE, or format only with RPT_LUKS_CONFIRM=yes"
  log "check ok"
}

cmd_dry_run() {
  [[ -n "$DEVICE" ]] || die "usage: $0 dry-run /dev/DISK_OR_PARTITION"
  log "dry-run LUKS/dm-crypt sequence for device=${DEVICE} (NOT executed)"
  cat <<EOF
# --- dry-run only — no changes ---
# 1) LUKS format (DESTRUCTIVE)
cryptsetup luksFormat --type luks2 ${DEVICE}
# 2) Open → dm-crypt mapper
cryptsetup open ${DEVICE} ${MAPPER_NAME}
# 3) Filesystem on decrypted device
mkfs.ext4 /dev/mapper/${MAPPER_NAME}
mkdir -p ${MOUNT_POINT}
mount /dev/mapper/${MAPPER_NAME} ${MOUNT_POINT}
# 4) Place secrets/runtime on encrypted mount (operator moves INSTALL_ROOT data)
# 5) Close locks data at rest
umount ${MOUNT_POINT}
cryptsetup close ${MAPPER_NAME}
# Compose with: install_host_privacy.sh (no-log journals) + install_shutdown_wipe.sh
EOF
  log "dry-run complete — no cryptsetup format was run"
}

cmd_format() {
  need_root
  [[ -n "$DEVICE" ]] || die "usage: RPT_LUKS_CONFIRM=yes $0 format /dev/DISK_OR_PARTITION"
  [[ -b "$DEVICE" ]] || die "not a block device: $DEVICE"
  if [[ "${RPT_LUKS_CONFIRM:-}" != "yes" ]]; then
    die "refusing luksFormat without RPT_LUKS_CONFIRM=yes (data loss)"
  fi
  command -v cryptsetup >/dev/null 2>&1 || die "install cryptsetup first (apt-get install -y cryptsetup)"
  log "DESTRUCTIVE: cryptsetup luksFormat --type luks2 ${DEVICE}"
  cryptsetup luksFormat --type luks2 "$DEVICE"
  log "open mapper ${MAPPER_NAME}"
  cryptsetup open "$DEVICE" "$MAPPER_NAME"
  log "mkfs.ext4 /dev/mapper/${MAPPER_NAME}"
  mkfs.ext4 -F "/dev/mapper/${MAPPER_NAME}"
  mkdir -p "$MOUNT_POINT"
  mount "/dev/mapper/${MAPPER_NAME}" "$MOUNT_POINT"
  log "mounted ${MOUNT_POINT} — move secrets/data here, then update fstab/crypttab as needed"
  log "format+open+mount complete"
  log "reminder: product no-log defaults still apply; FDE is at-rest protection only"
}

cmd_open() {
  need_root
  [[ -n "$DEVICE" ]] || die "usage: $0 open /dev/LUKS_DEVICE"
  command -v cryptsetup >/dev/null 2>&1 || die "cryptsetup missing"
  cryptsetup open "$DEVICE" "$MAPPER_NAME"
  mkdir -p "$MOUNT_POINT"
  mount "/dev/mapper/${MAPPER_NAME}" "$MOUNT_POINT"
  log "opened and mounted ${MOUNT_POINT}"
}

cmd_close() {
  need_root
  umount "$MOUNT_POINT" 2>/dev/null || true
  cryptsetup close "$MAPPER_NAME" 2>/dev/null || true
  log "closed ${MAPPER_NAME} (data at rest locked if no other opens)"
}

cmd_status() {
  log "status"
  if command -v cryptsetup >/dev/null 2>&1; then
    cryptsetup status "$MAPPER_NAME" 2>/dev/null || log "mapper ${MAPPER_NAME} not active"
  else
    warn "cryptsetup not installed"
  fi
  lsblk -o NAME,FSTYPE,TYPE,MOUNTPOINT 2>/dev/null | head -n 40 || true
}

case "$ACTION" in
  check|status) cmd_"${ACTION}" ;;
  dry-run|dryrun) cmd_dry_run ;;
  format) cmd_format ;;
  open) cmd_open ;;
  close) cmd_close ;;
  *)
    echo "usage: $0 {check|dry-run|format|open|close|status} [/dev/device]" >&2
    exit 2
    ;;
esac
