"""LUKS/dm-crypt data-at-rest policy + shutdown wipe planning (pure helpers).

Full-disk or data-volume encryption for the RPT **node host** uses Linux
**LUKS** via **dm-crypt** (``cryptsetup``). These helpers never reintroduce
user-info logs; they compose with :mod:`node.nolog` and host-privacy install.

Honesty:
- LUKS protects **data at rest** when the volume is locked / powered off.
- An unlocked running node is readable by root — FDE is not live-RAM secrecy.
- Auto-wipe is **best-effort local** only; it does not erase VPS provider
  snapshots, off-box backups, or netflow.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional, Sequence

# Default install tree (matches node/install.sh)
DEFAULT_INSTALL_ROOT = "/opt/restore-privacy"

# Runtime artifacts safe to remove on every service stop (not admission keys).
RUNTIME_WIPE_RELATIVE: tuple[str, ...] = (
    "run/rpt-node.ready",  # may also live under /run absolute
)

RUNTIME_WIPE_ABSOLUTE: tuple[str, ...] = (
    "/run/rpt-node.ready",
    "/tmp/rpt-node.tmp",
    "/tmp/rpt-node-runtime",
    "/var/tmp/rpt-node.tmp",
)

# Only wiped when aggressive host-shutdown policy is enabled by the operator.
AGGRESSIVE_SECRETS_RELATIVE: tuple[str, ...] = (
    "secrets/node_elgamal.priv",
    "secrets/node_elgamal.priv.sealed",
    "secrets/.key_backend_wrap",
)

# Paths that must never be wiped by product scripts (safety filter).
FORBIDDEN_WIPE_PREFIXES: tuple[str, ...] = (
    "/",
    "/bin",
    "/boot",
    "/dev",
    "/etc",
    "/lib",
    "/lib64",
    "/proc",
    "/sys",
    "/usr",
    "/var/lib/dpkg",
    "/var/lib/apt",
)

HONESTY_AT_REST = (
    "LUKS/dm-crypt protects node disk data **at rest** when the volume is locked "
    "or the host is powered off. It does not protect secrets in RAM on a running, "
    "unlocked system against root."
)

HONESTY_WIPE = (
    "Shutdown auto-wipe is best-effort on this host only. It does **not** erase "
    "VPS provider snapshots, off-box backups, or network/netflow logs."
)

HONESTY_NOLOG = (
    "Disk encryption complements the product **no-logs** design: no-log defaults "
    "still avoid durable connection/session/traffic/user-info logs; FDE protects "
    "media if those files or secrets ever land on disk."
)

# --- zram + LUKS2 ram-only volume (node host only; never a client requirement) ---

HONESTY_ZRAM_LUKS = (
    "zram + LUKS2 provides an **encrypted RAM-backed volume on the node host** for "
    "operator-chosen node data (e.g. secrets/runtime under the mapped mount). It is "
    "**not** client device encryption, not residual tunnel crypto, and not full "
    "live-root secrecy against root on an unlocked host. Contents live in RAM "
    "(compressed zram) behind LUKS2; a power loss loses that volume unless the "
    "operator re-creates it. VPS provider netflow/snapshots of the root disk are "
    "out of scope."
)

HONESTY_NODE_ONLY = (
    "LUKS2 and zram are **node-only** install options. Windows/Linux/Android/iOS/"
    "macOS clients do **not** install LUKS/zram and keep residual Connect (HELLO + "
    "full tunnel) unchanged."
)

DEFAULT_ZRAM_SIZE_MIB = 512
DEFAULT_ZRAM_MAPPER = "rpt-zram-crypt"
DEFAULT_ZRAM_MOUNT = "/mnt/rpt-ram-data"
DEFAULT_ZRAM_DEVICE = "/dev/zram0"

# Devices that must never be passed to destructive format helpers by accident.
FORBIDDEN_FORMAT_DEVICES: tuple[str, ...] = (
    "/",
    "/dev",
    "/dev/sda",
    "/dev/sda1",
    "/dev/vda",
    "/dev/vda1",
    "/dev/nvme0n1",
    "/dev/nvme0n1p1",
    "/dev/mapper/root",
    "/dev/root",
)


def install_root_from_env(default: str = DEFAULT_INSTALL_ROOT) -> str:
    return os.environ.get("INSTALL_ROOT", default).strip() or default


def _posix_norm(path: str) -> str:
    """Normalize to forward-slash form for policy checks (CI may run on Windows)."""
    s = str(path).strip().replace("\\", "/")
    while "//" in s:
        s = s.replace("//", "/")
    if len(s) > 1 and s.endswith("/"):
        s = s.rstrip("/")
    return s


def is_safe_wipe_path(
    path: str | Path,
    *,
    install_root: str = DEFAULT_INSTALL_ROOT,
    allow_absolute_runtime: bool = True,
) -> bool:
    """True if product wipe scripts may target this path.

    Allows paths under ``install_root`` and a small absolute runtime allow-list.
    Rejects bare ``/`` and critical system prefixes outside the allow-list.
    """
    raw = str(path).strip()
    if not raw or raw == ".":
        return False
    # Build candidate without Path drive quirks: treat leading / as absolute posix
    if raw.startswith("/") or (len(raw) > 1 and raw[1] == ":"):
        resolved = _posix_norm(raw)
    else:
        resolved = _posix_norm(f"{install_root.rstrip('/')}/{raw}")

    if resolved in ("/", "", "."):
        return False

    root = _posix_norm(install_root) or DEFAULT_INSTALL_ROOT
    if resolved == root:
        return False
    if resolved.startswith(root + "/"):
        return True

    if allow_absolute_runtime and resolved in RUNTIME_WIPE_ABSOLUTE:
        return True

    # Explicit deny for critical trees (never use bare "/" as a prefix match)
    for prefix in FORBIDDEN_WIPE_PREFIXES:
        pref = _posix_norm(prefix)
        if pref in ("", "/"):
            continue
        if resolved == pref or resolved.startswith(pref + "/"):
            return False
    return False


def runtime_wipe_targets(
    *,
    install_root: str = DEFAULT_INSTALL_ROOT,
) -> list[str]:
    """Paths scrubbed on **service stop** (default policy — keep admission keys)."""
    root = install_root.rstrip("/") or DEFAULT_INSTALL_ROOT
    out: list[str] = []
    for rel in RUNTIME_WIPE_RELATIVE:
        candidate = f"{root}/{rel}" if not rel.startswith("/") else rel
        if is_safe_wipe_path(candidate, install_root=root):
            out.append(candidate)
    for abs_p in RUNTIME_WIPE_ABSOLUTE:
        if is_safe_wipe_path(abs_p, install_root=root) and abs_p not in out:
            out.append(abs_p)
    return out


def aggressive_secrets_wipe_targets(
    *,
    install_root: str = DEFAULT_INSTALL_ROOT,
) -> list[str]:
    """Optional host-shutdown targets (operator must opt in)."""
    root = install_root.rstrip("/") or DEFAULT_INSTALL_ROOT
    out: list[str] = []
    for rel in AGGRESSIVE_SECRETS_RELATIVE:
        candidate = f"{root}/{rel}"
        if is_safe_wipe_path(candidate, install_root=root):
            out.append(candidate)
    return out


def plan_wipe(
    *,
    install_root: str = DEFAULT_INSTALL_ROOT,
    aggressive_secrets: bool = False,
    drop_caches: bool = True,
) -> dict:
    """Pure wipe plan consumed by scripts/tests (no I/O)."""
    targets = list(runtime_wipe_targets(install_root=install_root))
    if aggressive_secrets:
        targets.extend(aggressive_secrets_wipe_targets(install_root=install_root))
    # Dedup preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for t in targets:
        if t not in seen and is_safe_wipe_path(t, install_root=install_root):
            seen.add(t)
            ordered.append(t)
    return {
        "install_root": install_root.rstrip("/") or DEFAULT_INSTALL_ROOT,
        "targets": ordered,
        "aggressive_secrets": bool(aggressive_secrets),
        "drop_caches": bool(drop_caches),
        "honesty_wipe": HONESTY_WIPE,
        "honesty_at_rest": HONESTY_AT_REST,
        "honesty_nolog": HONESTY_NOLOG,
    }


def filter_wipe_targets(
    candidates: Iterable[str | Path],
    *,
    install_root: str = DEFAULT_INSTALL_ROOT,
) -> list[str]:
    """Keep only safe wipe paths from an arbitrary candidate list."""
    out: list[str] = []
    for c in candidates:
        s = str(c)
        if is_safe_wipe_path(s, install_root=install_root):
            out.append(s)
    return out


def luks_cryptsetup_commands_dry_run(
    device: str,
    *,
    mapper_name: str = "rpt-crypt",
    mount_point: str = "/mnt/rpt-data",
) -> list[str]:
    """Documented cryptsetup LUKS/dm-crypt command sequence (never executed here).

    Operators run these only after backup and explicit confirmation. Product
    install scripts use the same command names in check/dry-run modes.
    """
    dev = str(device).strip()
    if not dev.startswith("/dev/"):
        raise ValueError("device must be a /dev/ path")
    mapper = "".join(ch for ch in mapper_name if ch.isalnum() or ch in "-_") or "rpt-crypt"
    return [
        f"# LUKS format (DESTRUCTIVE — requires RPT_LUKS_CONFIRM=yes on live script)",
        f"cryptsetup luksFormat --type luks2 {dev}",
        f"# Open LUKS volume → dm-crypt mapping",
        f"cryptsetup open {dev} {mapper}",
        f"# Filesystem on decrypted dm-crypt device",
        f"mkfs.ext4 /dev/mapper/{mapper}",
        f"mkdir -p {mount_point}",
        f"mount /dev/mapper/{mapper} {mount_point}",
        f"# Close when done (locks data at rest)",
        f"umount {mount_point}",
        f"cryptsetup close {mapper}",
    ]


def cryptsetup_check_commands() -> list[str]:
    """Non-destructive checks for LUKS/dm-crypt tooling presence."""
    return [
        "command -v cryptsetup",
        "cryptsetup --version",
        "lsmod | grep -E 'dm_crypt|dm-crypt' || true",
        "dmsetup version || true",
    ]


def fde_docs_markers() -> dict[str, str]:
    """Stable phrases for structural tests / operator docs."""
    return {
        "luks": "LUKS",
        "dm_crypt": "dm-crypt",
        "cryptsetup": "cryptsetup",
        "at_rest": HONESTY_AT_REST,
        "wipe": HONESTY_WIPE,
        "nolog": HONESTY_NOLOG,
        "zram": "zram",
        "luks2": "luks2",
        "node_only": HONESTY_NODE_ONLY,
        "zram_luks": HONESTY_ZRAM_LUKS,
    }


def is_safe_format_device(device: str, *, allow_zram: bool = True) -> bool:
    """True if *device* is an acceptable cryptsetup/zram target (policy only).

    Allows ``/dev/zramN`` when *allow_zram* is True. Rejects empty paths, bare
    ``/``, and common root-disk names unless the operator uses a non-listed
    dedicated partition (still requires RPT_LUKS_CONFIRM=yes on live format).
    """
    dev = str(device or "").strip()
    if not dev.startswith("/dev/"):
        return False
    if ".." in dev or "\x00" in dev:
        return False
    # Single path component under /dev (or /dev/mapper/name)
    parts = [p for p in dev.split("/") if p]
    if len(parts) < 2 or parts[0] != "dev":
        return False
    name = parts[-1]
    if not name or name in (".", ".."):
        return False
    if allow_zram and name.startswith("zram") and name[4:].isdigit():
        return True
    # Explicit deny list for common root disks (use dedicated partition names)
    if dev in FORBIDDEN_FORMAT_DEVICES or name in {
        "sda",
        "vda",
        "nvme0n1",
        "root",
    }:
        return False
    # Dedicated partition style: sdb1, vdb1, nvme0n1p2, loop0, etc.
    if any(ch.isdigit() for ch in name) or name.startswith("loop") or name.startswith(
        "mapper"
    ):
        return True
    return False


def zram_setup_commands_dry_run(
    *,
    size_mib: int = DEFAULT_ZRAM_SIZE_MIB,
    zram_device: str = DEFAULT_ZRAM_DEVICE,
) -> list[str]:
    """Non-executed sequence to create a zram block device (node host)."""
    size = max(64, min(8192, int(size_mib)))
    dev = str(zram_device).strip() or DEFAULT_ZRAM_DEVICE
    if not is_safe_format_device(dev, allow_zram=True):
        raise ValueError(f"unsafe or invalid zram device: {dev}")
    idx = dev.replace("/dev/zram", "")
    return [
        "# Load zram (RAM-compressed block device — node host only)",
        "modprobe zram num_devices=1 || true",
        f"echo {size}M > /sys/block/zram{idx}/disksize",
        f"# Block device ready: {dev}",
    ]


def zram_luks2_commands_dry_run(
    *,
    size_mib: int = DEFAULT_ZRAM_SIZE_MIB,
    zram_device: str = DEFAULT_ZRAM_DEVICE,
    mapper_name: str = DEFAULT_ZRAM_MAPPER,
    mount_point: str = DEFAULT_ZRAM_MOUNT,
) -> list[str]:
    """Documented zram → LUKS2 → mount sequence (never executed here).

    Live install script requires ``RPT_ZRAM_LUKS_CONFIRM=yes`` for format.
    """
    dev = str(zram_device).strip() or DEFAULT_ZRAM_DEVICE
    if not is_safe_format_device(dev, allow_zram=True):
        raise ValueError(f"unsafe or invalid zram device: {dev}")
    mapper = (
        "".join(ch for ch in mapper_name if ch.isalnum() or ch in "-_")
        or DEFAULT_ZRAM_MAPPER
    )
    mount = str(mount_point).strip() or DEFAULT_ZRAM_MOUNT
    steps = zram_setup_commands_dry_run(size_mib=size_mib, zram_device=dev)
    steps.extend(
        [
            f"# LUKS2 format on RAM-backed {dev} (DESTRUCTIVE for that zram volume)",
            f"cryptsetup luksFormat --type luks2 {dev}",
            f"cryptsetup open {dev} {mapper}",
            f"mkfs.ext4 /dev/mapper/{mapper}",
            f"mkdir -p {mount}",
            f"mount /dev/mapper/{mapper} {mount}",
            f"# Place node secrets/runtime under {mount} (operator choice)",
            f"# On shutdown: umount {mount}; cryptsetup close {mapper}; reset zram",
            f"umount {mount}",
            f"cryptsetup close {mapper}",
            f"echo 1 > /sys/block/{dev.split('/')[-1]}/reset || true",
        ]
    )
    return steps


def plan_zram_luks2_volume(
    *,
    size_mib: int = DEFAULT_ZRAM_SIZE_MIB,
    zram_device: str = DEFAULT_ZRAM_DEVICE,
    mapper_name: str = DEFAULT_ZRAM_MAPPER,
    mount_point: str = DEFAULT_ZRAM_MOUNT,
    confirm_env: str = "RPT_ZRAM_LUKS_CONFIRM",
) -> dict:
    """Pure plan for node ram-only encrypted volume (check/dry-run/status)."""
    size = max(64, min(8192, int(size_mib)))
    dev = str(zram_device).strip() or DEFAULT_ZRAM_DEVICE
    safe = is_safe_format_device(dev, allow_zram=True)
    cmds = (
        zram_luks2_commands_dry_run(
            size_mib=size,
            zram_device=dev,
            mapper_name=mapper_name,
            mount_point=mount_point,
        )
        if safe
        else []
    )
    return {
        "mode": "zram_luks2",
        "node_only": True,
        "client_encryption": False,
        "size_mib": size,
        "zram_device": dev,
        "mapper_name": mapper_name,
        "mount_point": mount_point,
        "luks_type": "luks2",
        "safe_device": safe,
        "confirm_env": confirm_env,
        "confirm_required": "yes",
        "commands_dry_run": cmds,
        "check_commands": cryptsetup_check_commands()
        + [
            "command -v modprobe",
            "lsmod | grep zram || true",
            "ls -la /dev/zram* 2>/dev/null || true",
        ],
        "honesty_zram_luks": HONESTY_ZRAM_LUKS,
        "honesty_node_only": HONESTY_NODE_ONLY,
        "honesty_at_rest": HONESTY_AT_REST,
        "honesty_wipe": HONESTY_WIPE,
        "honesty_nolog": HONESTY_NOLOG,
    }


def zram_luks_docs_markers() -> dict[str, str]:
    """Markers for structural tests of ram-only node encryption docs/scripts."""
    return {
        "zram": "zram",
        "luks2": "luks2",
        "cryptsetup": "cryptsetup",
        "node_only": "node-only",
        "not_client": "not client",
        "confirm": "RPT_ZRAM_LUKS_CONFIRM",
        "honesty": HONESTY_ZRAM_LUKS[:40],
    }
