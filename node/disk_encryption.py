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
    }
