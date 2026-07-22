#!/usr/bin/env python3
"""One-command Windows multihop residual rebuild for catalog 0.3.7.

Run **on a Windows x64 machine** (PyInstaller cannot cross-build Windows PE from macOS):

  python scripts/build_windows_multihop.py

Or double-click / run:

  scripts\\build_windows_multihop.bat

Produces::

  releases/0.3.7/restore-privacy-client-0.3.7-windows-x64-setup.exe

Ships current ``client/`` (incl. multihop residual-via-exit), entry + exit ElGamal
**public** keys only, Wintun, frozen runtime — no ``*.priv``.

See ``client/windows/WINDOWS_HANDOFF_0.3.7.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.3.7"
OUT = ROOT / "releases" / VERSION
WINDOWS_EXE_NAME = f"restore-privacy-client-{VERSION}-windows-x64-setup.exe"
RECIPE = ROOT / "scripts" / "build_release_0.0.8.py"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_recipe():
    if not RECIPE.is_file():
        raise FileNotFoundError(f"missing Windows PyInstaller recipe: {RECIPE}")
    spec = importlib.util.spec_from_file_location("rpt_build_win_036", RECIPE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {RECIPE}")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.VERSION = VERSION
    m.OUT = OUT
    m.DIST = ROOT / "dist" / VERSION
    m.CLIENT_ONEDIR_NAME = f"RestorePrivacy-{VERSION}"
    m.WINDOWS_EXE_NAME = WINDOWS_EXE_NAME
    m.ANDROID_APK_NAME = f"restore-privacy-client-{VERSION}-android.apk"
    m.APP_NAME = "RestorePrivacy"
    m.ROOT = ROOT
    return m


def rebuild_windows_setup() -> Path:
    """Fresh PyInstaller onedir + onefile setup with multihop + entry/exit pubs."""
    # Pin monorepo version file for frozen upgrade banner
    (ROOT / "client" / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    entry = ROOT / "product" / "node_elgamal.pub"
    exit_p = ROOT / "product" / "exit_node_elgamal.pub"
    if not entry.is_file() or entry.stat().st_size < 32:
        raise FileNotFoundError(f"missing entry pub: {entry}")
    if not exit_p.is_file() or exit_p.stat().st_size < 32:
        raise FileNotFoundError(
            f"missing exit pub (required for multihop residual package): {exit_p}"
        )
    m = _load_recipe()
    print(f"=== Windows multihop rebuild {VERSION} (PyInstaller) ===")
    print(f"recipe: {RECIPE}")
    onedir = m.build_client_onedir()
    print(f"client onedir: {onedir}")
    # Re-inject pubs after freeze (guarantees product/ + secrets/ layouts)
    m.inject_product_secrets(onedir)
    setup = m.build_windows_installer_exe(onedir)
    if not setup.is_file():
        raise RuntimeError(f"Windows setup missing: {setup}")
    dest = OUT / WINDOWS_EXE_NAME
    if setup.resolve() != dest.resolve():
        OUT.mkdir(parents=True, exist_ok=True)
        shutil.copy2(setup, dest)
    return dest


def _assert_no_priv(path: Path) -> None:
    for p in path.rglob("*.priv") if path.is_dir() else []:
        raise RuntimeError(f"refusing package with private key material: {p}")
    if path.is_file():
        raw = path.read_bytes()
        if b"node_elgamal.priv" in raw:
            raise RuntimeError("setup.exe embeds node_elgamal.priv name — refuse")
        if b"BEGIN PRIVATE" in raw or b"BEGIN RSA PRIVATE" in raw:
            raise RuntimeError("setup.exe appears to embed PEM private key material")


def _post_check(setup: Path) -> None:
    """Lightweight gates that the multihop payload is present (not carry-forward)."""
    raw = setup.read_bytes()
    # Frozen code / strings
    if b"multihop" not in raw and b"MULTI_HOP" not in raw:
        print(
            "WARNING: setup.exe does not contain multihop string markers "
            "(may still work if module is compressed); extract and verify on device.",
            file=sys.stderr,
        )
    if b"exit_node_elgamal" not in raw and b"185.146.232.107" not in raw:
        print(
            "WARNING: setup.exe missing exit hop markers; "
            "confirm product/exit_node_elgamal.pub was injected.",
            file=sys.stderr,
        )
    dig = sha256_file(setup)
    print(f"windows: {setup}")
    print(f"  size:   {setup.stat().st_size} bytes")
    print(f"  sha256: {dig}")
    # Update SHA256SUMS / manifest if present
    man_path = OUT / "SHA256SUMS.json"
    if man_path.is_file():
        try:
            data = json.loads(man_path.read_text(encoding="utf-8"))
            assets = data.get("assets") or []
            updated = False
            for a in assets:
                if a.get("filename") == WINDOWS_EXE_NAME:
                    a["sha256"] = dig
                    a["bytes"] = setup.stat().st_size
                    updated = True
            if not updated:
                assets.append(
                    {
                        "filename": WINDOWS_EXE_NAME,
                        "sha256": dig,
                        "bytes": setup.stat().st_size,
                    }
                )
            data["assets"] = assets
            data["version"] = VERSION
            data["tag"] = VERSION
            notes = data.get("notes") or ""
            if "Windows multihop" not in notes:
                data["notes"] = (
                    (notes + " " if notes else "")
                    + "Windows multihop residual PE rebuilt via build_windows_multihop.py."
                ).strip()
            text = json.dumps(data, indent=2) + "\n"
            man_path.write_text(text, encoding="utf-8")
            (OUT / "manifest.json").write_text(text, encoding="utf-8")
            print(f"updated {man_path.name} + manifest.json")
        except (OSError, json.JSONDecodeError) as exc:
            print(f"manifest update skipped: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check-only",
        action="store_true",
        help="Verify prereqs (PyInstaller, pubs, wintun) without building",
    )
    args = ap.parse_args(argv)

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print(
            "ERROR: PyInstaller required.\n"
            "  python -m pip install pyinstaller cryptography\n",
            file=sys.stderr,
        )
        return 1

    wintun = ROOT / "client" / "windows" / "native" / "wintun.dll"
    if not wintun.is_file():
        alt = ROOT / "client" / "windows" / "native" / "wintun-amd64.dll"
        if alt.is_file():
            shutil.copy2(alt, wintun)
    if not wintun.is_file():
        print(f"ERROR: missing {wintun}", file=sys.stderr)
        return 1

    for p in (
        ROOT / "product" / "node_elgamal.pub",
        ROOT / "product" / "exit_node_elgamal.pub",
        ROOT / "client" / "multihop.py",
        ROOT / "client" / "windows" / "app.py",
        RECIPE,
    ):
        if not p.is_file():
            print(f"ERROR: missing required file: {p}", file=sys.stderr)
            return 1

    if args.check_only:
        print("OK: Windows multihop build prereqs present")
        print(f"  VERSION={VERSION}")
        print(f"  PyInstaller importable")
        print(f"  recipe={RECIPE}")
        print(f"  entry+exit pubs under product/")
        print(f"  multihop.py present")
        return 0

    try:
        setup = rebuild_windows_setup()
        _assert_no_priv(setup)
        _post_check(setup)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Windows multihop rebuild failed: {exc}", file=sys.stderr)
        log = ROOT / "dist" / VERSION / "pyinstaller_client.log"
        if log.is_file():
            print(f"  see also: {log}", file=sys.stderr)
        log2 = ROOT / "dist" / VERSION / "pyinstaller_installer.log"
        if log2.is_file():
            print(f"  see also: {log2}", file=sys.stderr)
        return 1

    print("OK: Windows multihop setup ready for GH Release / paid host stage")
    print(f"  Next: gh release upload {VERSION} {OUT / WINDOWS_EXE_NAME} --clobber")
    print(
        f"  Then:  python scripts/host_paid_assets_vps.py --stage "
        f"(and --upload when Iceland SSH works)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
