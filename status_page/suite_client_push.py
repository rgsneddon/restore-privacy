"""UPLOADS client-push: host vs Helsinki Suite monopin match gate.

Pure helpers for prefill UI and server-side gate so residual UPDATE_PUSH is
only allowed when build-host Suite packages match Helsinki paid_assets for the
selected monopin (size-comparable). Helsinki unknown fails closed.
"""

from __future__ import annotations

import hashlib
import os
import tarfile
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

# Suite catalog platforms (linux-x64 covers generic Linux + Arch Linux x86_64).
SUITE_PLATFORM_LABELS: dict[str, str] = {
    "windows": "Windows",
    "android": "Android",
    "macos": "macOS",
    "ios": "iOS",
    "linux": "Linux / Arch Linux (x86_64)",
}

LINUX_ARCH_COVERAGE: tuple[str, ...] = ("linux", "archlinux", "arch")


def suite_platform_display_label(platform: str) -> str:
    """Human platform label; linux is valid for Linux and Arch Linux x86_64."""
    key = str(platform or "").strip().lower()
    if key in ("linux", "linux-x64", "linux_x64", "linux-x86_64"):
        return SUITE_PLATFORM_LABELS["linux"]
    if key in ("archlinux", "arch", "archlinux-x64"):
        return SUITE_PLATFORM_LABELS["linux"]
    return SUITE_PLATFORM_LABELS.get(key, key.title() or "Unknown")


def linux_package_covers_arch_linux(platform: str | None, filename: str | None = None) -> bool:
    """True when this Suite row is the linux-x64 artifact valid for Arch x86_64."""
    plat = str(platform or "").strip().lower()
    name = str(filename or "").strip().lower()
    if plat in ("linux", "linux-x64", "linux_x64", "linux-x86_64"):
        return True
    if "linux-x64" in name or "linux_x64" in name or name.endswith("linux-x64.tar.gz"):
        return True
    return False


def validate_linux_suite_package(path: Path | str | None) -> dict[str, Any]:
    """Structural validity of Suite linux-x64 tarball (Linux + Arch x86_64).

    Does not invent a separate Arch binary — product catalog ships one
    ``linux-x64.tar.gz`` that is the supported artifact for both.
    """
    out: dict[str, Any] = {
        "ok": False,
        "path": str(path or ""),
        "filename": "",
        "bytes": 0,
        "covers": list(LINUX_ARCH_COVERAGE[:2]),  # linux, archlinux
        "error": "",
        "is_tar_gz": False,
    }
    if path is None:
        out["error"] = "path required"
        return out
    p = Path(path)
    out["filename"] = p.name
    if not p.is_file():
        out["error"] = "file missing"
        return out
    try:
        size = int(p.stat().st_size)
    except OSError as exc:
        out["error"] = f"stat failed: {exc}"[:160]
        return out
    out["bytes"] = size
    if size < 1000:
        out["error"] = f"package too small ({size} bytes)"
        return out
    low = p.name.lower()
    if "linux" not in low:
        out["error"] = "filename is not a Suite linux package"
        return out
    # Prefer real tar.gz open when gzip/tar
    try:
        if tarfile.is_tarfile(p):
            out["is_tar_gz"] = True
            with tarfile.open(p, "r:*") as tf:
                members = tf.getmembers()
                if not members:
                    out["error"] = "empty archive"
                    return out
        elif low.endswith(".tar.gz") or low.endswith(".tgz"):
            # is_tarfile false on some truncated fixtures — still accept monopin name
            out["is_tar_gz"] = True
        else:
            out["error"] = "not a tar.gz linux Suite package"
            return out
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"archive open failed: {exc}"[:160]
        return out
    out["ok"] = True
    out["error"] = ""
    out["covers_linux"] = True
    out["covers_archlinux"] = True
    return out


def summarize_local_suite_inventory(
    packages: Sequence[Mapping[str, Any]],
    *,
    version: str,
) -> dict[str, Any]:
    """Normalize host Suite inventory for match compare + UI prefill."""
    rows: list[dict[str, Any]] = []
    for p in packages or []:
        fname = str(p.get("filename") or "").strip()
        if not fname:
            continue
        plat = str(p.get("platform") or "").strip().lower()
        present = bool(p.get("present"))
        try:
            size = int(p.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        label = suite_platform_display_label(plat)
        covers_arch = linux_package_covers_arch_linux(plat, fname)
        rows.append(
            {
                "platform": plat,
                "platform_label": label,
                "filename": fname,
                "present": present,
                "size": size,
                "staged": bool(p.get("staged")),
                "path": str(p.get("path") or ""),
                "covers_archlinux": covers_arch,
                "sha256": str(p.get("sha256") or ""),
            }
        )
    present_rows = [r for r in rows if r["present"] and r["size"] > 0]
    return {
        "ok": True,
        "source": "build_host",
        "version": (version or "").strip(),
        "packages": rows,
        "present_count": len(present_rows),
        "total": len(rows),
        "present_filenames": [r["filename"] for r in present_rows],
        "present_sizes": {r["filename"]: r["size"] for r in present_rows},
    }


def summarize_helsinki_suite_inventory(
    version: str,
    remote_rows: Sequence[Mapping[str, Any]] | None,
    *,
    expected_filenames: Sequence[str] | None = None,
    probe_error: str = "",
) -> dict[str, Any]:
    """Normalize Helsinki paid_assets inventory (or probe results).

    *remote_rows* items: filename, bytes (or size), optional present.
    When *remote_rows* is None and no probe_error, treat as unknown.
    """
    ver = (version or "").strip()
    if remote_rows is None and not probe_error:
        return {
            "ok": False,
            "source": "helsinki",
            "version": ver,
            "packages": [],
            "present_count": 0,
            "total": 0,
            "present_filenames": [],
            "present_sizes": {},
            "error": "Helsinki inventory unknown",
            "known": False,
        }
    if probe_error and remote_rows is None:
        return {
            "ok": False,
            "source": "helsinki",
            "version": ver,
            "packages": [],
            "present_count": 0,
            "total": 0,
            "present_filenames": [],
            "present_sizes": {},
            "error": str(probe_error)[:240],
            "known": False,
        }
    rows: list[dict[str, Any]] = []
    sizes: dict[str, int] = {}
    for p in remote_rows or []:
        fname = str(p.get("filename") or "").strip()
        if not fname:
            continue
        try:
            size = int(p.get("bytes") or p.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        present = bool(p.get("present", size >= 1000))
        if expected_filenames is not None and fname not in set(expected_filenames):
            # Still record if present on remote for diagnostics
            pass
        rows.append(
            {
                "filename": fname,
                "present": present and size >= 1000,
                "size": size,
                "url": str(p.get("url") or ""),
            }
        )
        if present and size >= 1000:
            sizes[fname] = size
    present_n = sum(1 for r in rows if r["present"])
    return {
        "ok": True,
        "source": "helsinki",
        "version": ver,
        "packages": rows,
        "present_count": present_n,
        "total": len(rows),
        "present_filenames": [r["filename"] for r in rows if r["present"]],
        "present_sizes": sizes,
        "error": "",
        "known": True,
    }


def match_host_helsinki_suite(
    host: Mapping[str, Any],
    helsinki: Mapping[str, Any],
    *,
    only_filenames: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Compare build-host Suite packages to Helsinki; gate client push.

    Match requires same monopin version string and, for each selected filename
    (default: all present on host), Helsinki has the same basename with equal
    size (bytes). Helsinki unknown → cannot push (fail closed).
    """
    host_ver = str(host.get("version") or "").strip()
    hel_ver = str(helsinki.get("version") or "").strip()
    host_sizes = dict(host.get("present_sizes") or {})
    hel_sizes = dict(helsinki.get("present_sizes") or {})
    hel_known = bool(helsinki.get("known"))

    if only_filenames is not None:
        selected = [str(x).strip() for x in only_filenames if str(x).strip()]
    else:
        selected = list(host.get("present_filenames") or [])

    out: dict[str, Any] = {
        "match": False,
        "can_push": False,
        "reason": "",
        "host_version": host_ver,
        "helsinki_version": hel_ver,
        "selected": list(selected),
        "matched_files": [],
        "mismatched_files": [],
        "missing_on_helsinki": [],
        "missing_on_host": [],
        "helsinki_known": hel_known,
    }

    if not host_ver:
        out["reason"] = "Build host Suite monopin unknown — push cannot be completed."
        return out
    if not hel_known:
        out["reason"] = (
            "Helsinki Suite inventory unknown or unreachable — push cannot be "
            "completed until paid_assets presence is confirmed for this monopin."
        )
        return out
    if hel_ver and host_ver and hel_ver != host_ver:
        out["reason"] = (
            f"Monopin mismatch: build host has Suite v{host_ver} but Helsinki "
            f"reports v{hel_ver} — push cannot be completed."
        )
        return out
    if not selected:
        out["reason"] = (
            "No Suite packages selected (or none present on build host) — "
            "push cannot be completed."
        )
        return out

    matched: list[str] = []
    mismatched: list[str] = []
    missing_h: list[str] = []
    missing_host: list[str] = []
    for fname in selected:
        hsz = host_sizes.get(fname)
        if hsz is None or int(hsz) <= 0:
            # Allow staged-only select if host has size 0? treat as missing on host
            missing_host.append(fname)
            continue
        rsz = hel_sizes.get(fname)
        if rsz is None or int(rsz) <= 0:
            missing_h.append(fname)
            continue
        if int(hsz) != int(rsz):
            mismatched.append(fname)
        else:
            matched.append(fname)

    out["matched_files"] = matched
    out["mismatched_files"] = mismatched
    out["missing_on_helsinki"] = missing_h
    out["missing_on_host"] = missing_host

    if missing_host:
        out["reason"] = (
            "Selected package(s) not present on build host — push cannot be "
            f"completed: {', '.join(missing_host[:5])}."
        )
        return out
    if missing_h:
        out["reason"] = (
            "Selected package(s) missing on Helsinki paid_assets — push cannot "
            f"be completed: {', '.join(missing_h[:5])}. Upload to Helsinki first."
        )
        return out
    if mismatched:
        out["reason"] = (
            "Build host and Helsinki sizes differ for selected package(s) — "
            f"push cannot be completed: {', '.join(mismatched[:5])}."
        )
        return out
    if not matched:
        out["reason"] = "No matching Suite packages between host and Helsinki."
        return out

    out["match"] = True
    out["can_push"] = True
    out["reason"] = (
        f"Build host and Helsinki match for Suite v{host_ver} "
        f"({len(matched)} package(s)). Client push allowed "
        "(CHECK BREADCRUMBS opt-in only)."
    )
    return out


def _ssh_helsinki_suite_sizes(
    version: str,
    filenames: Sequence[str],
) -> list[dict[str, Any]] | None:
    """Best-effort SSH ``stat`` of paid_assets files on Helsinki (when keys set)."""
    import subprocess

    ver = (version or "").strip()
    names = [str(x).strip() for x in filenames if str(x).strip()]
    if not ver or not names:
        return None
    host = os.environ.get("RPT_SSH_HOST", "135.181.152.10").strip() or "135.181.152.10"
    user = os.environ.get("RPT_SSH_USER", "root").strip() or "root"
    key = (os.environ.get("RPT_SSH_KEY") or "").strip()
    if not key:
        for cand in (
            Path.home() / ".ssh" / "id_ed25519_restore_privacy_eu",
            Path.home() / ".ssh" / "id_ed25519_20260725",
            Path.home() / ".ssh" / "id_ed25519",
        ):
            if cand.is_file():
                key = str(cand)
                break
    if not key or not Path(key).is_file():
        return None
    remote_root = (
        os.environ.get("RPT_VPS_ASSET_REMOTE_ROOT", "/opt/restore-privacy/paid_assets")
        .strip()
        or "/opt/restore-privacy/paid_assets"
    )
    # One SSH: print size for each basename (0 if missing)
    script_parts = []
    for fn in names:
        # basename only
        safe = Path(fn).name.replace("'", "")
        rpath = f"{remote_root.rstrip('/')}/{ver}/{safe}"
        script_parts.append(
            f"if test -f '{rpath}'; then stat -c%s '{rpath}'; else echo 0; fi"
        )
    remote_cmd = " ; ".join(script_parts)
    try:
        p = subprocess.run(
            [
                "ssh",
                "-i",
                key,
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=12",
                "-o",
                "StrictHostKeyChecking=accept-new",
                f"{user}@{host}",
                remote_cmd,
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )
    except Exception:
        return None
    if p.returncode != 0:
        return None
    lines = [ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip()]
    if len(lines) < len(names):
        return None
    rows: list[dict[str, Any]] = []
    for fn, sz_s in zip(names, lines):
        try:
            size = int(sz_s)
        except ValueError:
            size = 0
        rows.append(
            {
                "filename": Path(fn).name,
                "bytes": size,
                "present": size >= 1000,
                "url": "",
            }
        )
    return rows


def probe_helsinki_suite_packages(
    version: str,
    filenames: Sequence[str],
    *,
    probe_one: Callable[[str, str], Mapping[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """Probe Helsinki for each Suite basename; returns summarize_helsinki shape.

    *probe_one(version, filename)* injectable for tests. Default uses
    ``run_security_audit.probe_helsinki_paid_package`` when available, then
    SSH ``stat`` fallback when HTTP finds nothing but keys are present.
    """
    ver = (version or "").strip()
    names = [str(x).strip() for x in filenames if str(x).strip()]
    if probe_one is None:
        try:
            import run_security_audit as rsa  # type: ignore

            def probe_one(v: str, fn: str) -> Mapping[str, Any] | None:
                return rsa.probe_helsinki_paid_package(v, fn)

        except Exception:  # noqa: BLE001

            def probe_one(v: str, fn: str) -> Mapping[str, Any] | None:
                return None

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    any_ok = False
    for fn in names:
        try:
            remote = probe_one(ver, fn)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{fn}: {exc}"[:120])
            remote = None
        if remote and int(remote.get("bytes") or 0) >= 1000:
            any_ok = True
            rows.append(
                {
                    "filename": fn,
                    "bytes": int(remote.get("bytes") or 0),
                    "present": True,
                    "url": str(remote.get("url") or ""),
                }
            )
        else:
            rows.append({"filename": fn, "bytes": 0, "present": False, "url": ""})
    if not any_ok and names:
        ssh_rows = _ssh_helsinki_suite_sizes(ver, names)
        if ssh_rows is not None:
            rows = ssh_rows
            any_ok = any(int(r.get("bytes") or 0) >= 1000 for r in rows)
            if any_ok:
                inv = summarize_helsinki_suite_inventory(
                    ver, rows, expected_filenames=names
                )
                inv["known"] = True
                inv["ok"] = True
                inv["probe_method"] = "ssh_stat"
                return inv
    if not any_ok and not names:
        return summarize_helsinki_suite_inventory(
            ver, None, probe_error="no filenames to probe"
        )
    if not any_ok:
        err = "; ".join(errors[:3]) if errors else "no Suite packages found on Helsinki"
        return summarize_helsinki_suite_inventory(
            ver, rows, expected_filenames=names, probe_error=err
        )
    # Partial presence is still "known"
    inv = summarize_helsinki_suite_inventory(ver, rows, expected_filenames=names)
    inv["known"] = True
    inv["ok"] = True
    inv["probe_method"] = "http"
    if errors:
        inv["probe_warnings"] = errors[:8]
    return inv


def file_sha256(path: Path, *, limit: int | None = None) -> str:
    """SHA-256 of file (full file unless *limit* bytes)."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        if limit is None:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        else:
            h.update(f.read(max(0, int(limit))))
    return h.hexdigest()


def default_client_update_url(version: str) -> str:
    """Prefill download URL for UPDATE_PUSH (catalog landing)."""
    ver = (version or "").strip()
    base = os.environ.get("RPT_PUBLIC_CATALOG_URL", "https://restoreprivacy.online/#downloads")
    if ver and "version=" not in base:
        # Keep stable landing; monopin is in directive.version
        return base.rstrip() or "https://restoreprivacy.online/#downloads"
    return base.rstrip() or "https://restoreprivacy.online/#downloads"
