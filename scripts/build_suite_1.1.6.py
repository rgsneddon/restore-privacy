#!/usr/bin/env python3
"""Build Restore Privacy residual VPN monopin 1.1.6 installers and stage for Helsinki.

Suite is free to download; Connect still requires a KEYGEN (£3/month licence).

On Darwin this builds **android**, **macos**, and **ios** from ``client_app``
(residual VPN client shell). **Windows** and **linux** are staged from the newest local
prior catalog pin when a native rebuild is unavailable on this host — filenames
are re-pinned to 1.1.6 for store layout; operators should replace with native
rebuilds when a Windows/Linux build agent is available.

Usage::

  python3 scripts/build_suite_1.1.6.py
  python3 scripts/build_suite_1.1.6.py --skip-build   # stage/copy only
  python3 scripts/build_suite_1.1.6.py --host-paid     # stage + Helsinki upload
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.1.6"
OUT = ROOT / "releases" / VERSION
CLIENT_APP = ROOT / "client_app"
STATUS_ASSETS = ROOT / "status_page" / "assets" / VERSION

NAMES = {
    "windows": f"restore-privacy-client-{VERSION}-windows-x64-setup.exe",
    "android": f"restore-privacy-client-{VERSION}-android.apk",
    "macos": f"restore-privacy-client-{VERSION}-macos.zip",
    "ios": f"restore-privacy-client-{VERSION}-ios.zip",
    "linux": f"restore-privacy-client-{VERSION}-linux-x64.tar.gz",
}

# Prefer newest local pin for carry-forward when native build unavailable
PRIOR_CANDIDATES = (
    "1.1.5",
    "1.1.4",
    "1.1.3",
    "1.1.2",
    "1.1.1",
    "1.1.0",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=str(cwd or ROOT), env=env)


def find_prior(platform_key: str) -> Path | None:
    """Locate a prior **Suite client** catalog file for *platform_key*.

    Prefers ``restore-privacy-client-*`` then ``restore-privacy-suite-*``.
    Never picks companion brand zips (rpos, rx-browser, node-installer, …).
    """
    for ver in PRIOR_CANDIDATES:
        d = ROOT / "releases" / ver
        if not d.is_dir():
            continue
        clients: list[Path] = []
        suites: list[Path] = []
        for p in d.iterdir():
            if not p.is_file():
                continue
            name = p.name.lower()
            if name.startswith("restore-privacy-client-"):
                clients.append(p)
            elif name.startswith("restore-privacy-suite-"):
                suites.append(p)
        for group in (clients, suites):
            for p in group:
                name = p.name.lower()
                if platform_key == "windows" and name.endswith(".exe") and "windows" in name:
                    return p
                if platform_key == "android" and name.endswith(".apk"):
                    return p
                if platform_key == "macos" and "macos" in name and name.endswith(".zip"):
                    return p
                if platform_key == "ios" and "ios" in name and name.endswith(".zip"):
                    return p
                if platform_key == "linux" and "linux" in name and (
                    name.endswith(".tar.gz") or name.endswith(".tgz")
                ):
                    return p
        # Fallback: status_page assets for that monopin
        ad = ROOT / "status_page" / "assets" / ver
        if ad.is_dir():
            for p in ad.iterdir():
                if not p.is_file():
                    continue
                name = p.name.lower()
                if not name.startswith("restore-privacy-client-"):
                    continue
                if platform_key == "windows" and name.endswith(".exe") and "windows" in name:
                    return p
                if platform_key == "android" and name.endswith(".apk"):
                    return p
                if platform_key == "macos" and "macos" in name and name.endswith(".zip"):
                    return p
                if platform_key == "ios" and "ios" in name and name.endswith(".zip"):
                    return p
                if platform_key == "linux" and "linux" in name and (
                    name.endswith(".tar.gz") or name.endswith(".tgz")
                ):
                    return p
    return None


def stage_copy(src: Path, dest: Path, *, note: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    print(f"staged {dest.name} from {src} ({note}) sha256={sha256_file(dest)[:16]}…")


def build_android() -> Path | None:
    out_apk = (
        CLIENT_APP
        / "build"
        / "app"
        / "outputs"
        / "flutter-apk"
        / "app-release.apk"
    )
    try:
        _run(
            [
                "flutter",
                "build",
                "apk",
                "--release",
                f"--build-name={VERSION}",
                "--build-number=1",
            ],
            cwd=CLIENT_APP,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"android build failed: {e}", file=sys.stderr)
        return None
    if not out_apk.is_file():
        return None
    dest = OUT / NAMES["android"]
    stage_copy(out_apk, dest, note="flutter apk")
    return dest


def build_macos() -> Path | None:
    """Build, Developer-ID sign, notarize, and ditto-zip the macOS residual client.

    Must **not** use Python ``zipfile`` for the catalog zip — that strips nested
    framework signatures and produces Gatekeeper
    \"Apple could not verify … free of malware\" on download. Packaging is
    ``scripts/sign_and_notarize_macos.py`` (ditto + notarytool + staple).
    """
    app = (
        CLIENT_APP
        / "build"
        / "macos"
        / "Build"
        / "Products"
        / "Release"
        / "restore_privacy_client.app"
    )
    try:
        _run(
            [
                "flutter",
                "build",
                "macos",
                "--release",
                f"--build-name={VERSION}",
            ],
            cwd=CLIENT_APP,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"macos build failed: {e}", file=sys.stderr)
        return None
    if not app.is_dir():
        # alternate product name
        products = CLIENT_APP / "build" / "macos" / "Build" / "Products" / "Release"
        apps = list(products.glob("*.app")) if products.is_dir() else []
        if not apps:
            return None
        app = apps[0]
    # Every residual macOS catalog build: Team residual NE re-sign on a **copy**
    # (host packet-tunnel-provider). Public DevID zip still omits host NE (AMFI).
    # Fail soft when profiles missing so DevID ship continues; residual copy is
    # for operator residual Connect on this Mac.
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import apple_ship_gates as _asg  # noqa: WPS433

        r = _asg.run_residual_team_resign(app, require=False)
        print(
            f"residual_team_resign ok={r.get('ok')} skipped={r.get('skipped')} "
            f"path={r.get('path')} err={r.get('error')}",
            flush=True,
        )
    except Exception as e:  # noqa: BLE001
        print(f"residual_team_resign best-effort failed: {e}", flush=True)
    dest = OUT / NAMES["macos"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    sign_script = ROOT / "scripts" / "sign_and_notarize_macos.py"
    if not sign_script.is_file():
        print("sign_and_notarize_macos.py missing", file=sys.stderr)
        return None
    try:
        _run(
            [
                sys.executable,
                str(sign_script),
                "--app",
                str(app),
                "--zip",
                str(dest),
            ],
            cwd=ROOT,
        )
    except subprocess.CalledProcessError as e:
        print(f"macos sign/notarize failed: {e}", file=sys.stderr)
        return None
    if not dest.is_file() or dest.stat().st_size < 1_000_000:
        print(f"macos sealed zip missing or too small: {dest}", file=sys.stderr)
        return None
    # Fail closed: catalog zip must be Notarized Developer ID after deep verify
    try:
        sys.path.insert(0, str(ROOT / "status_page"))
        from apple_package_audit import require_macos_zip_developer_id_distribution

        report = require_macos_zip_developer_id_distribution(dest)
        print(
            f"macos distribution seal ok reason={report.get('reason')!r} "
            f"spctl_notarized={report.get('spctl_notarized_developer_id')}"
        )
    except Exception as e:  # noqa: BLE001
        print(f"macos catalog seal rejected: {e}", file=sys.stderr)
        return None
    print(f"staged {dest.name} notarized DevID zip sha256={sha256_file(dest)[:16]}…")
    return dest


def inject_ios_residual_pubs(runner: Path) -> Path:
    """Embed live residual **public** ElGamal pins into iOS Runner.app.

    Live catalog only: IS ``node_elgamal.pub``, DE ``de_node_elgamal.pub``,
    multihop ``exit_node_elgamal.pub``. **Does not** inject retired
    ``us_node_elgamal.pub``. Fail-closed if entry pin missing. Uses
    ``inject_apple_secrets`` (host ``Runner.app/secrets/`` + PacketTunnel
    ``.appex/secrets/``). Must run **before** final Distribution codesign
    and catalog zip. (Developer ID + notarize are macOS-only — not iOS.)
    """
    if not runner.is_dir():
        raise FileNotFoundError(f"iOS Runner.app not found: {runner}")
    # Import real inject API (same module operators call with --app … --ios).
    scripts_dir = ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import inject_apple_secrets as ias  # type: ignore

    source = ias.resolve_source(None)
    dest = ias.inject(runner, source, ios=True)
    entry = dest / ias.NODE_PUB
    if not entry.is_file() or entry.stat().st_size < 32:
        raise FileNotFoundError(
            f"iOS inject did not embed required {ias.NODE_PUB} under {dest}"
        )
    print(f"ios residual pins injected -> {dest} ({ias.NODE_PUB}={entry.stat().st_size}B)")
    return dest


def codesign_ios_distribution(runner: Path) -> bool:
    """Best-effort Apple Distribution sign after inject (covers secrets in seal).

    Returns True when host ``Runner.app`` codesign succeeds. Missing identity is
    non-fatal so catalog zip can still ship with residual pubs for sideload.
    """
    identity = os.environ.get(
        "RP_IOS_CODESIGN_IDENTITY",
        "Apple Distribution: Russell Sneddon (SFCBP95595)",
    )
    try:
        # Nested frameworks / bundles first (inside-out).
        fw_dir = runner / "Frameworks"
        if fw_dir.is_dir():
            for fw in sorted(fw_dir.glob("*.framework")):
                subprocess.run(
                    ["codesign", "--force", "--timestamp", "--sign", identity, str(fw)],
                    check=False,
                )
        for bundle in sorted(runner.rglob("*.bundle")):
            if bundle.is_dir():
                subprocess.run(
                    ["codesign", "--force", "--timestamp", "--sign", identity, str(bundle)],
                    check=False,
                )
        appex = runner / "PlugIns" / "PacketTunnel.appex"
        if appex.is_dir():
            ent = CLIENT_APP / "ios" / "PacketTunnel" / "PacketTunnel.entitlements"
            cmd = ["codesign", "--force", "--timestamp", "--sign", identity]
            if ent.is_file():
                cmd.extend(["--entitlements", str(ent)])
            cmd.append(str(appex))
            if subprocess.run(cmd, check=False).returncode != 0:
                subprocess.run(
                    ["codesign", "--force", "--timestamp", "--sign", identity, str(appex)],
                    check=False,
                )
        r = subprocess.run(
            ["codesign", "--force", "--timestamp", "--sign", identity, str(runner)],
            check=False,
        )
        if r.returncode == 0:
            print(f"ios Distribution codesign OK identity={identity!r}")
            return True
        print(f"ios Distribution codesign failed rc={r.returncode} (zip still has pubs)", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("ios codesign tool missing; shipping unsigned zip with residual pubs", file=sys.stderr)
        return False


def package_ios_zip(runner: Path, dest: Path | None = None) -> Path:
    """Zip Runner.app as catalog ``restore-privacy-client-*-ios.zip``."""
    dest = dest or (OUT / NAMES["ios"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(runner):
            for fn in files:
                fp = Path(root) / fn
                arc = Path("Runner.app") / fp.relative_to(runner)
                zf.write(fp, arc.as_posix())
    print(f"staged {dest.name} flutter ios zip sha256={sha256_file(dest)[:16]}…")
    return dest


def build_ios() -> Path | None:
    """Build iphoneos Runner, inject residual pubs, optional Distribution sign, zip.

    Order is fail-closed for residual Connect: inject **must** embed
    ``node_elgamal.pub`` before the catalog zip is written.
    """
    try:
        _run(
            [
                "flutter",
                "build",
                "ios",
                "--release",
                "--no-codesign",
                f"--build-name={VERSION}",
            ],
            cwd=CLIENT_APP,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ios build failed: {e}", file=sys.stderr)
        return None
    runner = CLIENT_APP / "build" / "ios" / "iphoneos" / "Runner.app"
    if not runner.is_dir():
        return None
    try:
        inject_ios_residual_pubs(runner)
    except (FileNotFoundError, OSError) as e:
        print(f"ios residual inject failed (fail-closed): {e}", file=sys.stderr)
        return None
    codesign_ios_distribution(runner)
    return package_ios_zip(runner)


def carry_forward(platform_key: str) -> Path | None:
    src = find_prior(platform_key)
    if not src:
        print(f"no prior {platform_key} package to carry forward", file=sys.stderr)
        return None
    dest = OUT / NAMES[platform_key]
    stage_copy(src, dest, note=f"carry-forward from {src.parent.name}")
    return dest


def write_manifest(built: dict[str, Path]) -> Path:
    rows = []
    for plat, path in sorted(built.items()):
        rows.append(
            {
                "platform": plat,
                "filename": path.name,
                "version": VERSION,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "product": "Restore Privacy Suite",
                "free_download": True,
                "keygen_required": True,
                "licence": "£3.00/month",
            }
        )
    man = {
        "version": VERSION,
        "product": "Restore Privacy Suite",
        "free_download": True,
        "keygen_required": True,
        "licence_monthly": "£3.00",
        "packages": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "manifest.json"
    path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"manifest={path}")
    return path


def mirror_status_assets(built: dict[str, Path]) -> None:
    STATUS_ASSETS.mkdir(parents=True, exist_ok=True)
    for path in built.values():
        dest = STATUS_ASSETS / path.name
        shutil.copy2(path, dest)
        print(f"status_assets {dest}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skip-build", action="store_true", help="Only stage/copy, no flutter")
    p.add_argument(
        "--host-paid",
        action="store_true",
        help="After stage, run host_paid_assets_vps --stage --upload",
    )
    p.add_argument("--android-only", action="store_true")
    p.add_argument("--macos-only", action="store_true")
    p.add_argument("--ios-only", action="store_true")
    args = p.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    built: dict[str, Path] = {}
    is_darwin = platform.system() == "Darwin"
    only = args.android_only or args.macos_only or args.ios_only

    if not args.skip_build and is_darwin:
        if args.android_only or not only:
            r = build_android()
            if r:
                built["android"] = r
        if args.macos_only or not only:
            r = build_macos()
            if r:
                built["macos"] = r
        if args.ios_only or not only:
            r = build_ios()
            if r:
                built["ios"] = r

    # Fill missing platforms via carry-forward so Helsinki catalog is complete
    if not only:
        for plat in ("windows", "android", "macos", "ios", "linux"):
            if plat in built:
                continue
            r = carry_forward(plat)
            if r:
                built[plat] = r

    if not built:
        print("ERROR: no packages staged", file=sys.stderr)
        return 2

    write_manifest(built)
    mirror_status_assets(built)

    # Suite-named aliases for suite package path
    for plat, path in built.items():
        suite_name = path.name.replace("restore-privacy-client-", "restore-privacy-suite-")
        alias = OUT / suite_name
        if not alias.exists():
            shutil.copy2(path, alias)
            print(f"alias {alias.name}")

    if args.host_paid:
        host = ROOT / "scripts" / "host_paid_assets_vps.py"
        env = os.environ.copy()
        env.setdefault("RPT_SSH_HOST", "135.181.152.10")
        env.setdefault("RPT_SSH_USER", "root")
        key = Path.home() / ".ssh" / "id_ed25519_restore_privacy_eu"
        if key.is_file():
            env.setdefault("RPT_SSH_KEY", str(key))
        cmd = [
            sys.executable,
            str(host),
            "--stage",
            "--upload",
            "--version",
            VERSION,
            "--force",
        ]
        print("host_paid:", " ".join(cmd), flush=True)
        try:
            subprocess.check_call(cmd, cwd=str(ROOT), env=env)
        except subprocess.CalledProcessError as e:
            print(f"host_paid failed rc={e.returncode}", file=sys.stderr)
            return e.returncode

    print(f"OK suite {VERSION} packages={len(built)} dir={OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
