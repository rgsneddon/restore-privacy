#!/usr/bin/env python3
"""Package **Rx Privacy Browser** + browser-extension for all product platforms.

Produces **valid, expandable** archives (ZIP / tar.gz) under
``releases/{suite_version}/`` for:

  macOS · Windows · Linux x86_64 · Linux aarch64 (Arch/Debian/… relatives)
  iOS · Android · generic Chromium MV3

Honesty: these are **Suite companion** packages (MV3 extension + platform install
docs), **not** a full Chromium browser rebuild for each OS.

Also emits the legacy aliases:

  restore-privacy-rx-browser-{ver}.zip
  restore-privacy-browser-extension-{ver}.zip

macOS Archive Utility requires a real ZIP (PK\\x03\\x04). A 404 body saved as
``.zip`` causes “unsupported format” — packaging validates ZIP magic + unzip -t
before writing completes.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXT_SRC = ROOT / "browser_extension"

# Desktop + mobile product slots for Rx companion packages.
RX_PLATFORMS: tuple[str, ...] = (
    "macos",
    "windows",
    "linux-x86_64",
    "linux-aarch64",
    "ios",
    "android",
    "chromium",  # generic MV3 load-unpacked
)


def suite_version() -> str:
    try:
        sys.path.insert(0, str(ROOT / "status_page"))
        from downloads import RELEASE_VERSION

        return str(RELEASE_VERSION).strip() or "1.0.6"
    except Exception:
        return "1.0.6"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def platform_package_matrix(version: str | None = None) -> list[dict[str, Any]]:
    """Pure inventory of Rx multi-platform package slots (no I/O)."""
    ver = (version or suite_version()).strip() or suite_version()
    rows: list[dict[str, Any]] = []

    # Canonical extension zip (Chromium load unpacked)
    rows.append(
        {
            "kind": "browser_extension",
            "product": "Browser Extension (MV3)",
            "platform": "chromium",
            "filename": f"restore-privacy-browser-extension-{ver}.zip",
            "relative_path": f"{ver}/restore-privacy-browser-extension-{ver}.zip",
            "version": ver,
            "format": "zip",
            "installable": True,
            "honesty": (
                "Chromium MV3 extension tree — load unpacked in Chrome/Edge/Brave "
                "(desktop). Not a full browser binary."
            ),
        }
    )

    # Default Rx alias (same payload as chromium + install README) — device-agnostic URL
    rows.append(
        {
            "kind": "rx_browser",
            "product": "Rx Privacy Browser",
            "platform": "default",
            "filename": f"restore-privacy-rx-browser-{ver}.zip",
            "relative_path": f"{ver}/restore-privacy-rx-browser-{ver}.zip",
            "version": ver,
            "format": "zip",
            "installable": True,
            "default_download": True,
            "honesty": (
                "Default Rx companion package (MV3 extension + INSTALL.md). "
                "Use platform-specific packages when you need OS install notes."
            ),
        }
    )

    specs = (
        ("macos", "zip", f"restore-privacy-rx-browser-{ver}-macos.zip", "macOS"),
        ("windows", "zip", f"restore-privacy-rx-browser-{ver}-windows.zip", "Windows"),
        (
            "linux-x86_64",
            "tar.gz",
            f"restore-privacy-rx-browser-{ver}-linux-x86_64.tar.gz",
            "Linux x86_64 (Ubuntu, Debian, Fedora, Arch, …)",
        ),
        (
            "linux-aarch64",
            "tar.gz",
            f"restore-privacy-rx-browser-{ver}-linux-aarch64.tar.gz",
            "Linux aarch64 (ARM servers, Pi OS 64-bit, …)",
        ),
        # Also ship Linux zip for users who prefer Archive Utility / Explorer
        (
            "linux-x86_64-zip",
            "zip",
            f"restore-privacy-rx-browser-{ver}-linux-x86_64.zip",
            "Linux x86_64 zip alternate",
        ),
        ("ios", "zip", f"restore-privacy-rx-browser-{ver}-ios.zip", "iOS"),
        ("android", "zip", f"restore-privacy-rx-browser-{ver}-android.zip", "Android"),
    )
    for plat, fmt, fname, label in specs:
        rows.append(
            {
                "kind": "rx_browser",
                "product": "Rx Privacy Browser",
                "platform": plat,
                "filename": fname,
                "relative_path": f"{ver}/{fname}",
                "version": ver,
                "format": fmt,
                "installable": True,
                "label": label,
                "honesty": (
                    f"Rx companion for {label}: MV3 extension payload + platform "
                    "INSTALL.md. Not a full Chromium/Safari/WebView rebuild."
                ),
            }
        )
    return rows


def inventory(version: str | None = None) -> list[dict[str, Any]]:
    """Back-compat name used by callers."""
    return platform_package_matrix(version)


def _install_md(platform: str, version: str) -> str:
    common = (
        f"# Rx Privacy Browser — Suite {version}\n\n"
        "**What this is:** Restore Privacy **Rx** companion package "
        "(Chromium **MV3 extension** + install notes).\n\n"
        "**What this is not:** A full browser engine rebuild (not Chromium from source).\n\n"
    )
    if platform in ("macos", "default", "chromium"):
        return common + (
            "## macOS / desktop Chromium\n\n"
            "1. Double-click this `.zip` in **Finder** (Archive Utility) — it must expand "
            "to a folder (if you see “unsupported format”, re-download; a 404 HTML/text "
            "body saved as `.zip` is not a real archive).\n"
            "2. Open Chrome, Edge, Brave, or Chromium → "
            "`chrome://extensions` → enable **Developer mode**.\n"
            "3. **Load unpacked** → select the expanded folder containing `manifest.json`.\n"
            "4. Pin the Rx extension; residual Suite Connect still needs a KEYGEN.\n"
        )
    if platform == "windows":
        return common + (
            "## Windows\n\n"
            "1. Right-click → **Extract All** (Explorer) — archive must expand to a folder.\n"
            "2. Open Chrome/Edge → `edge://extensions` or `chrome://extensions` → "
            "Developer mode → **Load unpacked** → select the folder with `manifest.json`.\n"
            "3. Residual Suite Connect still needs a KEYGEN.\n"
        )
    if platform.startswith("linux"):
        return common + (
            "## Linux (Ubuntu, Debian, Fedora, Arch, …)\n\n"
            "```bash\n"
            "# zip\n"
            "unzip restore-privacy-rx-browser-*-linux-*.zip -d rx-browser\n"
            "# or tar.gz\n"
            "tar -xzf restore-privacy-rx-browser-*-linux-*.tar.gz\n"
            "```\n"
            "Load unpacked in Chromium/Chrome from the folder that contains `manifest.json`.\n"
        )
    if platform == "ios":
        return common + (
            "## iOS (honest limits)\n\n"
            "This package is the **desktop MV3 companion** for documentation and side-load "
            "workflows. **App Store Safari extensions are not shipped in this zip.** "
            "Use the desktop Chromium path for full Rx load-unpacked; iOS residual Suite "
            "client remains a separate Suite installer.\n"
        )
    if platform == "android":
        return common + (
            "## Android (honest limits)\n\n"
            "This package is the **desktop MV3 companion** (extension tree). "
            "Kiwi/Yandex-style Chromium forks may load unpacked extensions where the OS "
            "allows; this is **not** a Play Store APK browser rebuild. Suite residual "
            "Android client is a separate free Suite installer + KEYGEN.\n"
        )
    return common


def _collect_extension_files(src: Path) -> list[tuple[Path, str]]:
    """Return (absolute_path, archive_relative) pairs for the extension tree."""
    out: list[tuple[Path, str]] = []
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.name.startswith("."):
            continue
        out.append((path, path.relative_to(src).as_posix()))
    return out


def write_compatible_zip(
    dest: Path,
    files: list[tuple[Path | bytes, str]],
    *,
    comment: bytes = b"Rx Privacy Browser - Restore Privacy Suite companion",
) -> None:
    """Write a standard PKZIP archive that macOS Archive Utility can expand.

    Uses ZipInfo with create_system=3 (Unix) and compress_type=ZIP_DEFLATED,
    force ZIP64 off for small packages, and validates magic + test after write.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=False) as zf:
        zf.comment = comment[:65535]
        for src, arcname in files:
            info = zipfile.ZipInfo(filename=arcname.replace("\\", "/"))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # Unix — good cross-platform expand
            info.external_attr = 0o644 << 16
            if isinstance(src, (bytes, bytearray)):
                data = bytes(src)
            else:
                data = Path(src).read_bytes()
            zf.writestr(info, data)
    validate_archive(dest)


def write_tar_gz(
    dest: Path,
    files: list[tuple[Path | bytes, str]],
    top: str = "",
) -> None:
    """Write tar.gz. *arcname* paths are used as-is (already include top folder).

    *top* is optional and only applied when arcnames are not already prefixed
    (avoids double-nest ``top/top/...`` when callers pass top-prefixed paths).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    top_s = (top or "").strip().strip("/")
    with tarfile.open(dest, "w:gz") as tf:
        for src, arcname in files:
            arc = str(arcname).replace("\\", "/").lstrip("/")
            if top_s and not (arc == top_s or arc.startswith(top_s + "/")):
                name = f"{top_s}/{arc}"
            else:
                name = arc
            if isinstance(src, (bytes, bytearray)):
                data = bytes(src)
                ti = tarfile.TarInfo(name=name)
                ti.size = len(data)
                tf.addfile(ti, io.BytesIO(data))
            else:
                tf.add(str(src), arcname=name)
    # basic integrity: reopen + single primary top folder for extension tree
    with tarfile.open(dest, "r:gz") as tf:
        names = tf.getnames()
    if not names:
        raise RuntimeError(f"empty tar.gz: {dest}")
    if dest.stat().st_size < 100:
        raise RuntimeError(f"tar.gz too small: {dest}")
    # Fail closed on double-nest: .../linux-x86_64/linux-x86_64/manifest.json
    for n in names:
        parts = n.split("/")
        if len(parts) >= 3 and parts[0] == parts[1] and parts[0].startswith(
            "restore-privacy-rx-browser-"
        ):
            raise RuntimeError(f"double-nested tar path {n!r} in {dest}")


def validate_archive(path: Path) -> None:
    """Fail closed if archive is not a real expandable ZIP (or tar.gz)."""
    raw = path.read_bytes()[:4]
    if path.suffixes[-2:] == [".tar", ".gz"] or path.name.endswith(".tar.gz"):
        if path.stat().st_size < 50:
            raise RuntimeError(f"tar.gz too small: {path}")
        with tarfile.open(path, "r:gz") as tf:
            names = tf.getnames()
        if not names:
            raise RuntimeError(f"empty tar.gz: {path}")
        return
    if raw[:2] != b"PK":
        raise RuntimeError(
            f"not a ZIP (bad magic {raw!r}) — would fail macOS Archive Utility: {path}"
        )
    # Standard library test
    with zipfile.ZipFile(path, "r") as zf:
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f"corrupt zip member {bad}: {path}")
        if not zf.namelist():
            raise RuntimeError(f"empty zip: {path}")
    # Prefer system unzip -t when available (closest to user expand)
    unzip = None
    for cand in ("unzip", "/usr/bin/unzip"):
        if Path(cand).is_file() or cand == "unzip":
            try:
                proc = subprocess.run(
                    ["unzip", "-t", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                unzip = proc
                break
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
    if unzip is not None and unzip.returncode != 0:
        raise RuntimeError(
            f"unzip -t failed for {path}: {unzip.stdout}\n{unzip.stderr}"
        )


def _payload_files(platform: str, version: str) -> list[tuple[Path | bytes, str]]:
    """Extension files + platform INSTALL.md under a single top folder for clean expand."""
    top = f"restore-privacy-rx-browser-{version}-{platform}"
    if platform in ("default", "chromium"):
        top = f"restore-privacy-rx-browser-{version}"
    files: list[tuple[Path | bytes, str]] = []
    for abs_p, rel in _collect_extension_files(EXT_SRC):
        files.append((abs_p, f"{top}/{rel}"))
    install = _install_md(platform, version).encode("utf-8")
    files.append((install, f"{top}/INSTALL.md"))
    # Root-level INSTALL.md also (some users open zip listing at root)
    files.append((install, "INSTALL.md"))
    files.append(
        (
            (
                f"Rx Privacy Browser package for {platform}\n"
                f"Suite monopin {version}\n"
                "Companion MV3 extension — see INSTALL.md\n"
            ).encode("utf-8"),
            f"{top}/CAPABILITY.txt",
        )
    )
    return files


def package_one(
    slot: dict[str, Any],
    *,
    out_dir: Path | None = None,
) -> Path:
    ver = str(slot["version"])
    dest_dir = out_dir or (ROOT / "releases" / ver)
    dest = dest_dir / str(slot["filename"])
    if not EXT_SRC.is_dir():
        raise FileNotFoundError(EXT_SRC)
    plat = str(slot.get("platform") or "default")
    # Map linux-x86_64-zip → linux install docs
    install_plat = plat.replace("-zip", "") if plat.endswith("-zip") else plat
    files = _payload_files(install_plat, ver)
    fmt = str(slot.get("format") or "zip")
    if fmt == "tar.gz":
        # arcnames from _payload_files already include the single top folder
        write_tar_gz(dest, files, top="")
    else:
        write_compatible_zip(dest, files)
    print(
        f"package {dest.name} platform={plat} bytes={dest.stat().st_size} "
        f"sha256={sha256_file(dest)[:16]}…",
        flush=True,
    )
    return dest


def package(*, version: str | None = None) -> list[Path]:
    ver = (version or suite_version()).strip()
    out_dir = ROOT / "releases" / ver
    out_dir.mkdir(parents=True, exist_ok=True)
    # Also stage under status_page/assets for Render free-open path
    assets = ROOT / "status_page" / "assets" / ver
    assets.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for slot in platform_package_matrix(ver):
        p = package_one(slot, out_dir=out_dir)
        paths.append(p)
        # Mirror to assets for status host
        dest_a = assets / p.name
        dest_a.write_bytes(p.read_bytes())

    man = {
        "suite_version": ver,
        "product": "Rx Privacy Browser",
        "honesty": (
            "MV3 extension companion packages per platform — not full browser engines"
        ),
        "packages": [
            {
                "filename": p.name,
                "sha256": sha256_file(p),
                "bytes": p.stat().st_size,
                "valid_zip": p.name.endswith(".zip"),
            }
            for p in paths
        ],
        "platforms": [s["platform"] for s in platform_package_matrix(ver)],
    }
    (out_dir / "browser_rx_manifest.json").write_text(
        json.dumps(man, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "BROWSER_RX_README.txt").write_text(
        f"Rx Privacy Browser multi-platform packages for Suite {ver}.\n"
        "Each archive is a valid ZIP/tar.gz (see INSTALL.md inside).\n"
        "Not a full Chromium rebuild.\n",
        encoding="utf-8",
    )
    (assets / "browser_rx_manifest.json").write_text(
        json.dumps(man, indent=2) + "\n", encoding="utf-8"
    )
    return paths


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", default="")
    p.add_argument("--inventory", action="store_true")
    p.add_argument("--validate", action="store_true", help="Validate existing archives")
    args = p.parse_args(argv)
    ver = (args.version or "").strip() or suite_version()
    if args.inventory:
        print(json.dumps(platform_package_matrix(ver), indent=2))
        return 0
    if args.validate:
        out = ROOT / "releases" / ver
        for slot in platform_package_matrix(ver):
            path = out / slot["filename"]
            if not path.is_file():
                print(f"MISSING {path}")
                return 1
            validate_archive(path)
            print(f"OK {path.name}")
        return 0
    package(version=ver)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
