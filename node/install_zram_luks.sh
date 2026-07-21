#!/usr/bin/env bash
# Node-only: zram (RAM-backed block) + LUKS2 encrypted volume for RPT node data.
#
# Encrypts data **on the node host only** — clients never install LUKS/zram and
# residual Connect is unchanged. Complements product no-logs + host privacy.
#
# Usage (as root on Linux node):
#   bash node/install_zram_luks.sh check
#   bash node/install_zram_luks.sh dry-run
#   bash node/install_zram_luks.sh status
#   RPT_ZRAM_LUKS_CONFIRM=yes bash node/install_zram_luks.sh format
#   bash node/install_zram_luks.sh open    # after reboot if zram recreated
#   bash node/install_zram_luks.sh close
#
# Env:
#   RPT_ZRAM_SIZE_MIB   default 512
#   RPT_ZRAM_DEVICE     default /dev/zram0
#   RPT_ZRAM_MAPPER     default rpt-zram-crypt
#   RPT_ZRAM_MOUNT      default /mnt/rpt-ram-data
#   RPT_ZRAM_LUKS_CONFIRM=yes  required for format
#
# Honesty:
#   - RAM volume is lost on power-off unless recreated; not whole VPS root FDE.
#   - Unlocked mapper is readable by root; not live secrecy against compromise.
#   - Does not erase provider snapshots/netflow of the root disk.
#   - Never runs luksFormat without RPT_ZRAM_LUKS_CONFIRM=yes.
set -euo pipefail

SIZE_MIB="${RPT_ZRAM_SIZE_MIB:-512}"
ZRAM_DEV="${RPT_ZRAM_DEVICE:-/dev/zram0}"
MAPPER_NAME="${RPT_ZRAM_MAPPER:-rpt-zram-crypt}"
MOUNT_POINT="${RPT_ZRAM_MOUNT:-/mnt/rpt-ram-data}"
ACTION="${1:-check}"

log() { echo "[rpt-zram-luks] $*"; }
warn() { echo "[rpt-zram-luks] WARN: $*" >&2; }
die() { echo "[rpt-zram-luks] ERROR: $*" >&2; exit 1; }

echo "[rpt-zram-luks] zram + LUKS2 ram-only volume helper (node host only)"
echo "[rpt-zram-luks] Clients do NOT use LUKS/zram — residual Connect unchanged"
echo "[rpt-zram-luks] Honesty: RAM-backed encrypted volume; not full live-root secrecy"
echo "[rpt-zram-luks] Honesty: does not erase VPS provider snapshots or netflow"

need_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    die "run as root (sudo) for ${ACTION}"
  fi
}

zram_index() {
  basename "$ZRAM_DEV" | sed 's/^zram//'
}

cmd_check() {
  log "check mode (non-destructive)"
  if command -v cryptsetup >/dev/null 2>&1; then
    log "cryptsetup: $(command -v cryptsetup)"
    cryptsetup --version 2>/dev/null | head -n1 || true
  else
    warn "cryptsetup not installed — apt-get install -y cryptsetup cryptsetup-bin"
  fi
  if command -v modprobe >/dev/null 2>&1; then
    log "modprobe: present"
  else
    warn "modprobe missing"
  fi
  if lsmod 2>/dev/null | grep -q '^zram'; then
    log "zram module appears loaded"
  else
    log "zram module not listed (modprobe zram on format/open)"
  fi
  if lsmod 2>/dev/null | grep -qE 'dm_crypt|dm-crypt'; then
    log "dm-crypt module appears loaded"
  else
    warn "dm-crypt not listed (loads on first open)"
  fi
  log "planned size_mib=${SIZE_MIB} device=${ZRAM_DEV} mapper=${MAPPER_NAME} mount=${MOUNT_POINT}"
  log "confirm gate for format: RPT_ZRAM_LUKS_CONFIRM=yes"
  log "check ok"
}

cmd_dry_run() {
  log "dry-run zram + LUKS2 sequence (NOT executed)"
  IDX="$(zram_index)"
  cat <<EOF
# --- dry-run only — no changes ---
# 1) zram (RAM-compressed block)
modprobe zram num_devices=1 || true
echo ${SIZE_MIB}M > /sys/block/zram${IDX}/disksize
# 2) LUKS2 on ${ZRAM_DEV} (requires RPT_ZRAM_LUKS_CONFIRM=yes for live format)
cryptsetup luksFormat --type luks2 ${ZRAM_DEV}
cryptsetup open ${ZRAM_DEV} ${MAPPER_NAME}
mkfs.ext4 /dev/mapper/${MAPPER_NAME}
mkdir -p ${MOUNT_POINT}
mount /dev/mapper/${MAPPER_NAME} ${MOUNT_POINT}
# 3) Operator may place node secrets/runtime under ${MOUNT_POINT}
# 4) Teardown locks / discards RAM volume
umount ${MOUNT_POINT}
cryptsetup close ${MAPPER_NAME}
echo 1 > /sys/block/zram${IDX}/reset || true
# Node-only: clients never run this path
EOF
  log "dry-run complete — no zram/LUKS format was run"
}

cmd_format() {
  need_root
  if [[ "${RPT_ZRAM_LUKS_CONFIRM:-}" != "yes" ]]; then
    die "refusing format without RPT_ZRAM_LUKS_CONFIRM=yes"
  fi
  command -v cryptsetup >/dev/null 2>&1 || die "install cryptsetup first"
  command -v modprobe >/dev/null 2>&1 || die "modprobe missing"
  IDX="$(zram_index)"
  log "modprobe zram"
  modprobe zram num_devices=1 || true
  if [[ ! -b "$ZRAM_DEV" ]]; then
    die "zram device missing: $ZRAM_DEV"
  fi
  log "set zram disksize ${SIZE_MIB}M"
  echo "${SIZE_MIB}M" > "/sys/block/zram${IDX}/disksize"
  log "DESTRUCTIVE: cryptsetup luksFormat --type luks2 ${ZRAM_DEV}"
  cryptsetup luksFormat --type luks2 "$ZRAM_DEV"
  cryptsetup open "$ZRAM_DEV" "$MAPPER_NAME"
  mkfs.ext4 -F "/dev/mapper/${MAPPER_NAME}"
  mkdir -p "$MOUNT_POINT"
  mount "/dev/mapper/${MAPPER_NAME}" "$MOUNT_POINT"
  log "mounted ${MOUNT_POINT} — node data only; clients unchanged"
  log "format complete (RAM-backed LUKS2)"
}

cmd_open() {
  need_root
  command -v cryptsetup >/dev/null 2>&1 || die "cryptsetup missing"
  IDX="$(zram_index)"
  modprobe zram num_devices=1 || true
  if [[ ! -b "$ZRAM_DEV" ]]; then
    die "zram device missing after modprobe: $ZRAM_DEV (re-format after reboot)"
  fi
  # disksize may need reset after reboot
  if [[ ! -s "/sys/block/zram${IDX}/disksize" ]] || [[ "$(cat /sys/block/zram${IDX}/disksize 2>/dev/null || echo 0)" == "0" ]]; then
    echo "${SIZE_MIB}M" > "/sys/block/zram${IDX}/disksize" || true
  fi
  cryptsetup open "$ZRAM_DEV" "$MAPPER_NAME" || die "open failed (zram LUKS is ephemeral — re-run format after reboot)"
  mkdir -p "$MOUNT_POINT"
  mount "/dev/mapper/${MAPPER_NAME}" "$MOUNT_POINT"
  log "opened and mounted ${MOUNT_POINT}"
}

cmd_close() {
  need_root
  umount "$MOUNT_POINT" 2>/dev/null || true
  cryptsetup close "$MAPPER_NAME" 2>/dev/null || true
  IDX="$(zram_index)"
  echo 1 > "/sys/block/zram${IDX}/reset" 2>/dev/null || true
  log "closed ${MAPPER_NAME} and reset zram (RAM volume discarded)"
}

cmd_status() {
  log "status"
  if command -v cryptsetup >/dev/null 2>&1; then
    cryptsetup status "$MAPPER_NAME" 2>/dev/null || log "mapper ${MAPPER_NAME} not active"
  else
    warn "cryptsetup not installed"
  fi
  ls -la /dev/zram* 2>/dev/null || log "no /dev/zram* present"
  lsblk -o NAME,FSTYPE,TYPE,MOUNTPOINT,SIZE 2>/dev/null | head -n 40 || true
  if mountpoint -q "$MOUNT_POINT" 2>/dev/null; then
    log "mount active: ${MOUNT_POINT}"
  else
    log "mount not active: ${MOUNT_POINT}"
  fi
}

case "$ACTION" in
  check|status) cmd_"${ACTION}" ;;
  dry-run|dryrun) cmd_dry_run ;;
  format) cmd_format ;;
  open) cmd_open ;;
  close) cmd_close ;;
  *)
    echo "usage: $0 {check|dry-run|format|open|close|status}" >&2
    exit 2
    ;;
esac
