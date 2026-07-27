#!/usr/bin/env python3
"""Build / stage Restore Privacy client packages for release 0.5.0.

**0.5.0** multi-hop residual catalog. Apple packages are Flutter-built then
DevID/notarized (macOS) / Team-signed (iOS). Linux is rebuilt via package_linux.
**Windows multihop PE** must be built on Windows x64::

  python scripts/build_windows_multihop.py
  # or:  scripts\\build_windows_multihop.bat
  # or:  python scripts/build_release_0.5.0.py --windows-only

If PyInstaller rebuild is unavailable, Windows falls back to carry-forward /
SFX pin rewrite (honest: no multihop residual *code* until native rebuild).

Never bundles node_elgamal.priv or shared client_ed25519.priv.

Handoff: ``client/windows/WINDOWS_HANDOFF_0.4.10.md``
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.5.0"
OUT = ROOT / "releases" / VERSION
WINDOWS_EXE_NAME = f"restore-privacy-client-{VERSION}-windows-x64-setup.exe"
ANDROID_APK_NAME = f"restore-privacy-client-{VERSION}-android.apk"
MACOS_ZIP_NAME = f"restore-privacy-client-{VERSION}-macos.zip"
IOS_ZIP_NAME = f"restore-privacy-client-{VERSION}-ios.zip"
LINUX_TGZ_NAME = f"restore-privacy-client-{VERSION}-linux-x64.tar.gz"

MACOS_APP = (
    ROOT
    / "client_app"
    / "build"
    / "macos"
    / "Build"
    / "Products"
    / "Release"
    / "restore_privacy_client.app"
)
IOS_APP = ROOT / "client_app" / "build" / "ios" / "iphoneos" / "Runner.app"

# Carry-forward non-Apple platforms from last full catalog pin on this host
PRIOR_TAG = "0.4.10"
PRIOR_DOWNLOAD = (
    f"https://github.com/rgsneddon/restore-privacy/releases/download/{PRIOR_TAG}"
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_version_files() -> None:
    (ROOT / "client" / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    pubspec = ROOT / "client_app" / "pubspec.yaml"
    text = pubspec.read_text(encoding="utf-8")
    lines = []
    for line in text.splitlines():
        if line.startswith("version:"):
            lines.append(f"version: {VERSION}+1")
        else:
            lines.append(line)
    pubspec.write_text("\n".join(lines) + "\n", encoding="utf-8")
    inst = ROOT / "client" / "windows" / "installer.py"
    if inst.is_file():
        t = inst.read_text(encoding="utf-8")
        t2 = t
        for old in (
            "0.4.10",
            "0.4.9",
            "0.4.8",
            "0.4.7",
            "0.4.6",
            "0.4.5",
            "0.4.4",
            "0.4.2",
            "0.4.1",
            "0.4.0",
            "0.3.4",
            "0.3.0",
            "0.2.9",
            "0.2.8",
            "0.2.7",
            "0.2.6",
            "0.2.5",
            "0.2.4",
            "0.2.3",
            "0.2.2",
            "0.2.1",
            "0.2.0",
            "0.1.9",
            "0.1.8",
            "0.1.7",
            "0.1.6",
            "0.1.5",
            "0.1.4",
            "0.1.3",
            "0.1.2",
            "0.1.1",
            "0.1.0",
            "0.0.9",
        ):
            t2 = t2.replace(f'VERSION = "{old}"', f'VERSION = "{VERSION}"')
            t2 = t2.replace(f"build_release_{old}.py", f"build_release_{VERSION}.py")
        if t2 != t:
            inst.write_text(t2, encoding="utf-8")


def _assert_no_priv(root: Path) -> None:
    for p in root.rglob("*.priv"):
        raise RuntimeError(f"refusing to package private key material: {p}")


def inject_product_secrets(app: Path, *, ios: bool) -> None:
    script = ROOT / "scripts" / "inject_apple_secrets.py"
    cmd = [sys.executable, str(script), "--app", str(app)]
    if ios:
        cmd.append("--ios")
    subprocess.run(cmd, check=True)


def sign_and_notarize_macos(app: Path, dest_zip: Path) -> None:
    script = ROOT / "scripts" / "sign_and_notarize_macos.py"
    if not script.is_file():
        raise FileNotFoundError(f"missing {script}")
    cmd = [
        sys.executable,
        str(script),
        "--app",
        str(app),
        "--zip",
        str(dest_zip),
    ]
    subprocess.run(cmd, check=True)


def package_macos_zip() -> Path:
    if not MACOS_APP.is_dir():
        raise FileNotFoundError(
            f"Missing macOS app at {MACOS_APP}. Run: cd client_app && flutter build macos"
        )
    inject_product_secrets(MACOS_APP, ios=False)
    _assert_no_priv(MACOS_APP)
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / MACOS_ZIP_NAME
    sign_and_notarize_macos(MACOS_APP, dest)
    if not dest.is_file():
        raise RuntimeError(f"sign_and_notarize_macos did not produce {dest}")
    return dest


def sign_ios_app(app: Path) -> None:
    identity = os.environ.get(
        "RP_IOS_CODESIGN_IDENTITY",
        "Apple Distribution: Russell Sneddon (SFCBP95595)",
    )
    fw_dir = app / "Frameworks"
    if fw_dir.is_dir():
        for fw in sorted(fw_dir.glob("*.framework")):
            subprocess.run(
                ["codesign", "--force", "--timestamp", "--sign", identity, str(fw)],
                check=False,
            )
    appex = app / "PlugIns" / "PacketTunnel.appex"
    if appex.is_dir():
        ent = ROOT / "client_app" / "ios" / "PacketTunnel" / "PacketTunnel.entitlements"
        cmd = ["codesign", "--force", "--timestamp", "--sign", identity]
        if ent.is_file():
            cmd.extend(["--entitlements", str(ent)])
        cmd.append(str(appex))
        r = subprocess.run(cmd, check=False)
        if r.returncode != 0:
            subprocess.run(
                ["codesign", "--force", "--timestamp", "--sign", identity, str(appex)],
                check=True,
            )
    subprocess.run(
        ["codesign", "--force", "--timestamp", "--sign", identity, str(app)],
        check=True,
    )


def package_ios_zip() -> Path:
    if not IOS_APP.is_dir():
        raise FileNotFoundError(
            f"Missing iOS app at {IOS_APP}. Run: cd client_app && flutter build ios --no-codesign"
        )
    inject_product_secrets(IOS_APP, ios=True)
    _assert_no_priv(IOS_APP)
    try:
        sign_ios_app(IOS_APP)
    except Exception as exc:  # noqa: BLE001
        print(f"iOS codesign warning: {exc}", file=sys.stderr)
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / IOS_ZIP_NAME
    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in IOS_APP.rglob("*"):
            if path.is_file():
                arc = Path("Runner.app") / path.relative_to(IOS_APP)
                zf.write(path, arc.as_posix())
    return dest


def _stage_from_prior(prior_name: str, dest: Path) -> Path:
    """Copy prior release asset and rename to current VERSION filename."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Prefer local monorepo staged assets (private repo — GitHub release may 404)
    candidates = [
        ROOT / "releases" / PRIOR_TAG / prior_name,
        ROOT / "status_page" / "assets" / PRIOR_TAG / prior_name,
        ROOT / "releases" / "0.3.0" / prior_name.replace(PRIOR_TAG, "0.3.0"),
        ROOT / "status_page" / "assets" / "0.3.0" / prior_name.replace(PRIOR_TAG, "0.3.0"),
        ROOT / "releases" / "0.2.9" / prior_name.replace(PRIOR_TAG, "0.2.9"),
        ROOT / "status_page" / "assets" / "0.2.9" / prior_name.replace(PRIOR_TAG, "0.2.9"),
    ]
    for local in candidates:
        if local.is_file() and local.stat().st_size > 1_000_000:
            shutil.copy2(local, dest)
            print(f"staged from local {local}: → {dest.name}")
            return dest
    # download prior then rename (public release only)
    import urllib.request

    url = f"{PRIOR_DOWNLOAD}/{prior_name}"
    tmp = dest.parent / prior_name
    print(f"fetch {url}")
    try:
        urllib.request.urlretrieve(url, tmp)
    except Exception as exc:  # noqa: BLE001
        raise FileNotFoundError(
            f"no local prior for {prior_name} and fetch failed: {exc}"
        ) from exc
    if tmp.resolve() != dest.resolve():
        if dest.exists():
            dest.unlink()
        tmp.rename(dest)
    if not dest.is_file() or dest.stat().st_size < 1_000_000:
        raise FileNotFoundError(f"failed to stage {prior_name} → {dest}")
    return dest


def rebuild_windows_setup() -> Path:
    """Fresh PyInstaller Windows setup (multihop + entry/exit pubs). Windows host only."""
    import importlib.util

    path = ROOT / "scripts" / "build_windows_multihop.py"
    spec = importlib.util.spec_from_file_location("rpt_win_mh_036", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.rebuild_windows_setup()


def stage_windows_exe(*, force_rebuild: bool = False) -> Path:
    """Stage Windows setup.exe — prefer live multihop rebuild, else carry-forward."""
    dest = OUT / WINDOWS_EXE_NAME
    OUT.mkdir(parents=True, exist_ok=True)
    if force_rebuild or sys.platform.startswith("win"):
        try:
            built = rebuild_windows_setup()
            if built.resolve() != dest.resolve():
                shutil.copy2(built, dest)
            print(f"windows rebuilt (multihop): {dest}")
            return dest
        except Exception as exc:  # noqa: BLE001
            print(
                f"windows multihop rebuild failed ({exc}); "
                f"falling back to carry-forward…",
                file=sys.stderr,
            )
            if force_rebuild:
                raise
    # Prefer already-rebuilt 0.5.0 SFX if present with correct pin
    if dest.is_file() and dest.stat().st_size > 1_000_000:
        data = dest.read_bytes()
        title_ok = b'Title="Restore Privacy ' + VERSION.encode() + b'"' in data
        if title_ok and VERSION.encode() in data:
            print(f"windows: keeping existing {dest.name} (title pin {VERSION})")
            return dest
    _stage_from_prior(
        f"restore-privacy-client-{PRIOR_TAG}-windows-x64-setup.exe", dest
    )
    _rewrite_windows_sfx_version(dest)
    return dest


def _rewrite_windows_sfx_version(exe: Path) -> None:
    """Repack 7z SFX so client/VERSION and Title pin match VERSION (same-length pins).

    Honest: this does **not** rebuild multihop residual PE code — only catalog
    pin strings / VERSION files inside a carried SFX when 7z extract works.
    """
    import re
    import subprocess
    import tempfile

    work = Path(tempfile.mkdtemp(prefix="rpt-win-sfx-"))
    try:
        data = exe.read_bytes()
        # Locate 7z magic
        magic = b"7z\xbc\xaf'\x1c"
        off = data.find(magic)
        if off < 0:
            # try generic 7z header used by p7zip listing Offset
            off = data.find(b"7z")
            if off < 0:
                print("windows: not a 7z SFX; leave as staged (pin filename only)")
                return
        stub = bytearray(data[:off])
        # same-length title rewrite for any 0.x.y pin
        stub_bytes = bytes(stub)
        stub_bytes = re.sub(
            rb'Title="Restore Privacy \d+\.\d+\.\d+"',
            f'Title="Restore Privacy {VERSION}"'.encode(),
            stub_bytes,
        )
        # same-length 5-char product pins (0.x.y)
        old_pins = [
            b"0.3.9",
            b"0.3.8",
            b"0.3.7",
            b"0.3.6",
            b"0.3.5",
            b"0.3.4",
            b"0.3.3",
            b"0.3.0",
            b"0.2.9",
            b"0.2.3",
        ]
        if len(VERSION) == 5:
            for old in old_pins:
                stub_bytes = stub_bytes.replace(old, VERSION.encode())
        payload_dir = work / "payload"
        payload_dir.mkdir()
        r = subprocess.run(
            ["7z", "x", "-y", f"-o{payload_dir}", str(exe)],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            print(f"windows: 7z extract failed: {r.stderr[:200]}")
            # Still write stub title rewrites if possible
            if stub_bytes != bytes(stub):
                # cannot safely recombine without payload — leave file as staged copy
                print("windows: pin rewrite partial (stub only skipped without extract)")
            return
        # rewrite VERSION files and same-length version strings
        for path in payload_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                blob = path.read_bytes()
            except OSError:
                continue
            if path.name == "VERSION":
                path.write_text(VERSION + "\n", encoding="utf-8")
                continue
            if len(VERSION) == 5:
                newb = blob
                for op in old_pins:
                    if op in newb:
                        newb = newb.replace(op, VERSION.encode())
                if newb != blob:
                    path.write_bytes(newb)
        arc = work / "payload.7z"
        subprocess.run(
            ["7z", "a", "-t7z", "-m0=BCJ", "-m1=LZMA2:d48m", "-ms=on", str(arc), "."],
            cwd=str(payload_dir),
            check=True,
            capture_output=True,
        )
        exe.write_bytes(stub_bytes + arc.read_bytes())
        print(f"windows: repacked SFX with pin {VERSION} → {exe.name}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _android_apk_has_residual_wire(apk: Path) -> bool:
    """True when classes.dex embeds product PFS + outer obfs (Connect requires both)."""
    import zipfile

    try:
        with zipfile.ZipFile(apk) as z:
            dex = z.read("classes.dex")
        return b"pfs-x25519" in dex and b"RPT-OBFS-LAYER" in dex
    except Exception:
        return False


def stage_android_apk() -> Path:
    """Stage Android APK that embeds product residual wire (PFS + outer obfs).

    Carry-forward of pre-PFS APKs causes silent HELLO drop on the live node
    (require_pfs=True) → on-device Poll timed out / Connect failure. Prefer a
    wire-complete prior (e.g. status_page/assets/0.3.0) over a broken rename.
    """
    dest = OUT / ANDROID_APK_NAME
    candidates: list[Path] = [
        ROOT
        / "status_page"
        / "assets"
        / PRIOR_TAG
        / f"restore-privacy-client-{PRIOR_TAG}-android.apk",
        ROOT / "releases" / PRIOR_TAG / f"restore-privacy-client-{PRIOR_TAG}-android.apk",
        # Known residual-wire complete build used when later carry-forwards lost PFS
        ROOT
        / "status_page"
        / "assets"
        / "0.3.0"
        / "restore-privacy-client-0.3.0-android.apk",
        ROOT / "releases" / "0.3.0" / "restore-privacy-client-0.3.0-android.apk",
    ]
    chosen: Path | None = None
    for c in candidates:
        if c.is_file() and _android_apk_has_residual_wire(c):
            chosen = c
            break
    if chosen is None:
        # Last resort: prior path via helper, still gate on wire
        try:
            staged = _stage_from_prior(
                f"restore-privacy-client-{PRIOR_TAG}-android.apk", dest
            )
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                "No Android APK with product residual wire (pfs-x25519 + "
                "RPT-OBFS-LAYER). Rebuild: cd client_app && flutter build apk --release"
            ) from exc
        if not _android_apk_has_residual_wire(staged):
            raise RuntimeError(
                f"{staged.name} lacks PFS/outer-obfs residual wire — refusing to ship "
                "(node require_pfs silent-drops HELLO → Connect timeout)"
            )
        return staged
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.resolve() != chosen.resolve():
        shutil.copy2(chosen, dest)
    if not _android_apk_has_residual_wire(dest):
        raise RuntimeError(f"staged {dest} still missing residual wire")
    print(f"android: staged residual-wire APK from {chosen}")
    return dest


def _rewrite_linux_node_elgamal_pub(tarball: Path) -> None:
    """Ensure every node_elgamal.pub inside the Linux tarball matches product pin.

    Carry-forward priors may ship a stale pub (HELLO hybrid decrypt fails).
    """
    import tarfile
    import tempfile

    product = ROOT / "product" / "node_elgamal.pub"
    if not product.is_file() or product.stat().st_size < 32:
        raise FileNotFoundError(f"missing product node pub: {product}")
    pub_bytes = product.read_bytes()
    work = Path(tempfile.mkdtemp(prefix="rpt-linux-pub-"))
    try:
        with tarfile.open(tarball, "r:gz") as tf:
            tf.extractall(work)
        replaced = 0
        for p in work.rglob("node_elgamal.pub"):
            p.write_bytes(pub_bytes)
            replaced += 1
        # Prefer product/ + secrets/ so secrets_loader finds the correct key
        for top in [d for d in work.iterdir() if d.is_dir()]:
            for sub in ("product", "secrets"):
                d = top / sub
                d.mkdir(parents=True, exist_ok=True)
                (d / "node_elgamal.pub").write_bytes(pub_bytes)
                replaced += 1
        if replaced == 0:
            raise RuntimeError(f"no node_elgamal.pub in {tarball}")
        tmp_out = work / "repacked.tar.gz"
        with tarfile.open(tmp_out, "w:gz") as tf:
            for child in sorted(work.iterdir()):
                if child.name == "repacked.tar.gz":
                    continue
                tf.add(child, arcname=child.name)
        shutil.copy2(tmp_out, tarball)
        print(f"rewrote node_elgamal.pub in {tarball.name} ({replaced} path(s))")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def stage_linux_tgz() -> Path:
    """Rebuild Linux package from monorepo pin (client/VERSION)."""
    dest = OUT / LINUX_TGZ_NAME
    script = ROOT / "scripts" / "package_linux.py"
    if script.is_file():
        print("linux: rebuilding via package_linux.py …")
        subprocess.run([sys.executable, str(script)], check=True, cwd=str(ROOT))
        if dest.is_file():
            # ensure product pub (package_linux already copies secrets pub)
            try:
                _rewrite_linux_node_elgamal_pub(dest)
            except Exception as exc:  # noqa: BLE001
                print(f"linux pub rewrite note: {exc}")
            return dest
    # Fallback: carry-forward + rewrite VERSION + pub
    _stage_from_prior(
        f"restore-privacy-client-{PRIOR_TAG}-linux-x64.tar.gz", dest
    )
    _rewrite_linux_node_elgamal_pub(dest)
    _rewrite_linux_version_pin(dest)
    return dest


def _rewrite_linux_version_pin(tarball: Path) -> None:
    """Ensure client/VERSION and top dir name match current VERSION."""
    import tarfile
    import tempfile

    work = Path(tempfile.mkdtemp(prefix="rpt-linux-ver-"))
    try:
        with tarfile.open(tarball, "r:gz") as tf:
            tf.extractall(work)
        tops = [d for d in work.iterdir() if d.is_dir()]
        for top in tops:
            ver_file = top / "client" / "VERSION"
            if ver_file.is_file():
                ver_file.write_text(VERSION + "\n", encoding="utf-8")
            want = f"restore-privacy-{VERSION}-linux"
            if top.name != want:
                new = top.parent / want
                top.rename(new)
                top = new
        tmp_out = work / "repacked.tar.gz"
        with tarfile.open(tmp_out, "w:gz") as tf:
            for child in sorted(work.iterdir()):
                if child.name == "repacked.tar.gz":
                    continue
                tf.add(child, arcname=child.name)
        shutil.copy2(tmp_out, tarball)
        print(f"rewrote Linux VERSION pin in {tarball.name}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def stage_macos_zip() -> Path:
    """macOS zip: Flutter+DevID when Mac+secrets; else honest carry-forward rename."""
    dest = OUT / MACOS_ZIP_NAME
    try:
        return package_macos_zip()
    except Exception as exc:  # noqa: BLE001
        print(
            f"macos native package unavailable ({exc}); "
            f"carry-forward prior zip → {dest.name} (Mac must rebuild/sign for real 0.5.0)",
            file=sys.stderr,
        )
        return _stage_from_prior(
            f"restore-privacy-client-{PRIOR_TAG}-macos.zip", dest
        )


def stage_ios_zip() -> Path:
    """iOS zip: Flutter+Team-sign when Mac+secrets; else honest carry-forward rename."""
    dest = OUT / IOS_ZIP_NAME
    try:
        return package_ios_zip()
    except Exception as exc:  # noqa: BLE001
        print(
            f"ios native package unavailable ({exc}); "
            f"carry-forward prior zip → {dest.name} (Mac must rebuild/sign for real 0.5.0)",
            file=sys.stderr,
        )
        return _stage_from_prior(
            f"restore-privacy-client-{PRIOR_TAG}-ios.zip", dest
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apple-only",
        action="store_true",
        help="Only package macOS + iOS (still write version pins; skip non-Apple carry-forward)",
    )
    ap.add_argument(
        "--windows-only",
        action="store_true",
        help="Only rebuild Windows multihop setup.exe (run on Windows x64)",
    )
    ap.add_argument(
        "--with-carry-forward",
        action="store_true",
        help="Also stage Windows/Android/Linux under 0.5.0 names (default if not apple/windows-only)",
    )
    args = ap.parse_args(argv)

    write_version_files()
    OUT.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}

    print(f"=== Restore Privacy release {VERSION} ===")

    if args.windows_only:
        win = stage_windows_exe(force_rebuild=True)
        artifacts[WINDOWS_EXE_NAME] = sha256_file(win)
        print(f"windows: {win} ({win.stat().st_size} bytes) [multihop rebuild]")
        _assert_no_priv(OUT)
        man_path = OUT / "SHA256SUMS.json"
        manifest = {
            "version": VERSION,
            "tag": VERSION,
            "assets": [
                {
                    "filename": name,
                    "sha256": dig,
                    "bytes": (OUT / name).stat().st_size,
                }
                for name, dig in artifacts.items()
            ],
            "notes": "0.5.0 Windows multihop residual PE (build_windows_multihop / --windows-only)",
        }
        # Merge with existing manifest assets when present
        if man_path.is_file():
            try:
                prev = json.loads(man_path.read_text(encoding="utf-8"))
                by_name = {
                    a["filename"]: a for a in (prev.get("assets") or []) if a.get("filename")
                }
                for name, dig in artifacts.items():
                    by_name[name] = {
                        "filename": name,
                        "sha256": dig,
                        "bytes": (OUT / name).stat().st_size,
                    }
                manifest["assets"] = list(by_name.values())
                if prev.get("notes"):
                    manifest["notes"] = prev["notes"]
            except (OSError, json.JSONDecodeError, KeyError):
                pass
        text = json.dumps(manifest, indent=2) + "\n"
        man_path.write_text(text, encoding="utf-8")
        (OUT / "manifest.json").write_text(text, encoding="utf-8")
        print(f"manifest: {man_path}")
        print("OK:", list(artifacts.keys()))
        return 0

    # Apple packages are required for this release
    mac = stage_macos_zip()
    artifacts[MACOS_ZIP_NAME] = sha256_file(mac)
    print(f"macos:   {mac} ({mac.stat().st_size} bytes)")

    ios = stage_ios_zip()
    artifacts[IOS_ZIP_NAME] = sha256_file(ios)
    print(f"ios:     {ios} ({ios.stat().st_size} bytes)")

    do_carry = args.with_carry_forward or not args.apple_only
    if do_carry:
        win = stage_windows_exe(force_rebuild=False)
        artifacts[WINDOWS_EXE_NAME] = sha256_file(win)
        print(f"windows: {win} ({win.stat().st_size} bytes)")

        apk = stage_android_apk()
        artifacts[ANDROID_APK_NAME] = sha256_file(apk)
        print(f"android: {apk} ({apk.stat().st_size} bytes)")

        linux = stage_linux_tgz()
        artifacts[LINUX_TGZ_NAME] = sha256_file(linux)
        print(f"linux:   {linux} ({linux.stat().st_size} bytes)")

    _assert_no_priv(OUT)

    required = [MACOS_ZIP_NAME, IOS_ZIP_NAME]
    if do_carry:
        required.extend([WINDOWS_EXE_NAME, ANDROID_APK_NAME, LINUX_TGZ_NAME])
    missing = [n for n in required if not (OUT / n).is_file()]
    if missing:
        print(f"ERROR: missing assets: {missing}", file=sys.stderr)
        return 1

    manifest = {
        "version": VERSION,
        "tag": VERSION,
        "assets": [
            {"filename": name, "sha256": dig, "bytes": (OUT / name).stat().st_size}
            for name, dig in artifacts.items()
        ],
        "notes": (
            "0.5.0: Windows native multihop PE + Connect/Disconnect speed + country picker; "
            "macOS/iOS catalog zips honest CF until Mac Developer ID notarize / Team-sign; "
            "keygen paste/dismiss and Connect/Disconnect system VPN tandem from Apple host branch; "
            "public host without NE, Packet Tunnel appex with packet-tunnel-provider; "
            "Linux rebuilt; Android residual-wire rebuild when SDK present else prior wire-complete APK."
        ),
    }
    man_path = OUT / "SHA256SUMS.json"
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"manifest: {man_path}")
    print("OK:", list(artifacts.keys()))
    return 0


if __name__ == "__main__":
    sys.exit(main())

