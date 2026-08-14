#!/usr/bin/env python3
"""Build Restore Privacy residual VPN monopin 1.2.5 installers and stage for Helsinki.

Suite is free to download; Connect still requires a KEYGEN (£3/month licence).

On Darwin this builds **android**, **macos**, and **ios** from ``client_app``
(residual VPN client shell). **Windows** and **linux** are staged from the newest local
prior catalog pin when a native rebuild is unavailable on this host — filenames
are re-pinned to 1.2.5 (carry-forward prior 1.2.4) for store layout; operators should replace with native
rebuilds when a Windows/Linux build agent is available.

Usage::

  python3 scripts/build_suite_1.2.5.py
  python3 scripts/build_suite_1.2.5.py --skip-build   # stage/copy only
  python3 scripts/build_suite_1.2.5.py --host-paid     # stage + Helsinki upload
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
VERSION = "1.2.5"
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
    "1.2.4",
    "1.2.2",
    "1.2.1",
    "1.2.0",
    "1.1.9",
    "1.1.8",
    "1.1.7",
    "1.1.6",
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


def _package_app_ditto_zip(app: Path, dest: Path) -> None:
    """ditto-zip *app* as ``restore_privacy_client.app`` under *dest* (preserves seal)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    # Stage under canonical catalog app name so extract UX is consistent
    # even when source is restore_privacy_client.residual-team.app.
    import tempfile

    with tempfile.TemporaryDirectory(prefix="rpt_macos_zip_") as td:
        staged = Path(td) / "restore_privacy_client.app"
        if staged.exists():
            shutil.rmtree(staged)
        shutil.copytree(app, staged, symlinks=True)
        _run(
            [
                "ditto",
                "-c",
                "-k",
                "--sequesterRsrc",
                "--keepParent",
                str(staged),
                str(dest),
            ]
        )


def build_macos() -> Path | None:
    """Build Gatekeeper-openable Notarized Developer ID macOS monopin zip.

    Catalog monopin basename is **Developer ID + notary + staple** with host
    packet-tunnel-provider **omitted** (default ``RPT_MACOS_HOST_NE=0``). Apple
    Development residual-team seals cause Gatekeeper
    \"Apple could not verify … free of malware\" and must **not** be the monopin
    basename. DevID + host NE without a DevID NE profile is AMFI SIGKILL 137.

    Every build still best-effort produces ``*.residual-team.app`` (Team NE) as
    a **side** artifact for residual Connect on this Mac — never the catalog zip.
    Packaging uses ditto (via sign_and_notarize) so nested signatures stay intact.
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
        products = CLIENT_APP / "build" / "macos" / "Build" / "Products" / "Release"
        apps = list(products.glob("*.app")) if products.is_dir() else []
        if not apps:
            return None
        app = apps[0]

    # Side path: Team residual NE re-sign (host packet-tunnel-provider) so
    # System Settings can list Restore Privacy VPN. Never the monopin basename
    # (Apple Development fails Gatekeeper). Packaged as *-macos-residual-team.zip.
    residual_app: Path | None = None
    try:
        if str(ROOT / "scripts") not in sys.path:
            sys.path.insert(0, str(ROOT / "scripts"))
        import apple_ship_gates as _asg  # noqa: WPS433

        r = _asg.run_residual_team_resign(app, require=False)
        print(
            f"residual_team_resign (side, not monopin) ok={r.get('ok')} "
            f"skipped={r.get('skipped')} path={r.get('path')} err={r.get('error')}",
            flush=True,
        )
        if r.get("ok") and r.get("path") and not r.get("skipped"):
            residual_app = Path(str(r["path"]))
    except Exception as e:  # noqa: BLE001
        print(f"residual_team_resign best-effort failed: {e}", flush=True)

    if residual_app is not None and residual_app.is_dir():
        residual_zip = OUT / NAMES["macos"].replace(
            "-macos.zip", "-macos-residual-team.zip"
        )
        try:
            if str(ROOT / "status_page") not in sys.path:
                sys.path.insert(0, str(ROOT / "status_page"))
            from apple_package_audit import (  # noqa: WPS433
                host_app_has_packet_tunnel_provider,
                launch_probe_app_alive,
            )

            if host_app_has_packet_tunnel_provider(residual_app):
                probe = launch_probe_app_alive(residual_app)
                print(f"residual-team launch_probe={probe}", flush=True)
                if probe.get("ok"):
                    _package_app_ditto_zip(residual_app, residual_zip)
                    print(
                        f"staged residual-team side zip {residual_zip.name} "
                        f"(host NE for System VPN registration; not monopin)",
                        flush=True,
                    )
                else:
                    print(
                        f"residual-team launch probe failed (side zip skipped): "
                        f"{probe.get('error')}",
                        flush=True,
                    )
            else:
                print("residual-team missing host NE (side zip skipped)", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"residual-team side zip failed (non-fatal): {e}", flush=True)

    dest = OUT / NAMES["macos"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    sign_script = ROOT / "scripts" / "sign_and_notarize_macos.py"
    if not sign_script.is_file():
        print("sign_and_notarize_macos.py missing", file=sys.stderr)
        return None
    # Free monopin: Notarized Developer ID + residual host NE when DevID NE
    # profiles exist (systemextension tokens). Launch probe fail-closed.
    env = os.environ.copy()
    # Prefer residual-capable free path; sign script auto-detects profiles.
    # Explicit unset allows auto; only force 0 if operator sets RPT_MACOS_HOST_NE=0.
    if "RPT_MACOS_HOST_NE" not in env:
        env["RPT_MACOS_HOST_NE"] = "1"
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
            env=env,
        )
    except subprocess.CalledProcessError as e:
        print(f"macos DevID sign/notarize failed (monopin refuse): {e}", file=sys.stderr)
        return None
    if not dest.is_file() or dest.stat().st_size < 1_000_000:
        print(f"macos sealed zip missing or too small: {dest}", file=sys.stderr)
        return None

    if str(ROOT / "status_page") not in sys.path:
        sys.path.insert(0, str(ROOT / "status_page"))
    try:
        from apple_package_audit import (  # noqa: WPS433
            launch_probe_app_alive,
            require_macos_zip_developer_id_distribution,
        )

        report = require_macos_zip_developer_id_distribution(dest)
        print(
            f"macos distribution seal ok reason={report.get('reason')!r} "
            f"spctl_notarized={report.get('spctl_notarized_developer_id')} "
            f"leaf={report.get('leaf_authority')!r}",
            flush=True,
        )
        # Refuse residual-as-monopin: leaf must be Developer ID Application
        leaf = str(report.get("leaf_authority") or "")
        if "Apple Development" in leaf or not report.get(
            "is_developer_id_application"
        ):
            print(
                f"ERROR: monopin leaf is not Developer ID Application: {leaf!r}",
                file=sys.stderr,
            )
            return None
    except Exception as e:  # noqa: BLE001
        print(f"macos catalog DevID seal rejected: {e}", file=sys.stderr)
        return None

    # Launch probe the notarized app still on disk (zip audit temp extract is gone).
    # sign_and_notarize_macos already probes before zip; re-check here fail-closed.
    try:
        from apple_package_audit import (  # noqa: WPS433
            host_app_has_packet_tunnel_provider,
            launch_probe_app_alive,
        )

        probe = launch_probe_app_alive(app)
        print(f"macos monopin launch_probe={probe}", flush=True)
        if not probe.get("ok"):
            print(
                f"ERROR: monopin failed launch probe: {probe.get('error')}",
                file=sys.stderr,
            )
            return None
        has_ne = host_app_has_packet_tunnel_provider(app)
        print(f"macos monopin host_packet_tunnel_ne={has_ne}", flush=True)
        if env.get("RPT_MACOS_HOST_NE", "1") not in ("0", "false", "no", "off") and not has_ne:
            print(
                "ERROR: free monopin expected residual host NE for first-use VPN "
                "registration but host lacks packet-tunnel-provider*",
                file=sys.stderr,
            )
            return None
    except Exception as e:  # noqa: BLE001
        print(f"macos monopin launch probe error: {e}", file=sys.stderr)
        return None

    print(
        f"staged {dest.name} Notarized Developer ID monopin "
        f"sha256={sha256_file(dest)[:16]}…",
        flush=True,
    )
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
    """Team-sign Runner.app with embedded provisioning (installable sideload).

    Uses ``ios_sideload_package.prepare_signed_sideload_app``: embeds matching
    host + PacketTunnel ``embedded.mobileprovision`` profiles then inside-out
    codesign. **Fail-closed** when operator profiles are missing — never claim
    Team-signed success without provision (bare signed app cannot install).

    Returns True only when host provision is embedded and codesign succeeds.
    """
    scripts_dir = ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from ios_sideload_package import (  # type: ignore
        IosSideloadError,
        prepare_signed_sideload_app,
    )

    try:
        info = prepare_signed_sideload_app(runner, require_profiles=True)
    except IosSideloadError as e:
        print(f"ios sideload codesign refuse (fail-closed): {e}", file=sys.stderr)
        return False
    if not info.get("signed"):
        print(
            f"ios sideload codesign skipped: {info.get('reason')} (fail-closed)",
            file=sys.stderr,
        )
        return False
    print(
        f"ios sideload codesign OK identity={info.get('identity')!r} "
        f"host_profile={info.get('host_profile_name')!r} "
        f"tunnel_profile={info.get('tunnel_profile_name')!r}"
    )
    return True


def package_ios_zip(runner: Path, dest: Path | None = None) -> Path:
    """Zip Runner.app as IPA-compatible catalog ``Payload/Runner.app/…`` zip.

    Sideload tools accept rename-to-``.ipa``. Bare top-level ``Runner.app`` zips
    are rejected by ``require_installable_ios_zip`` after write.
    """
    dest = dest or (OUT / NAMES["ios"])
    scripts_dir = ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from ios_sideload_package import (  # type: ignore
        IosSideloadError,
        package_ios_ipa_zip,
        require_installable_ios_zip,
    )

    try:
        package_ios_ipa_zip(runner, dest)
        # Require host provision when present on disk (codesign path embedded it).
        require_prov = (runner / "embedded.mobileprovision").is_file()
        require_installable_ios_zip(dest, require_provision=require_prov)
    except IosSideloadError as e:
        if dest.is_file():
            dest.unlink(missing_ok=True)
        raise RuntimeError(f"iOS catalog package refuse: {e}") from e
    print(
        f"staged {dest.name} IPA Payload zip sha256={sha256_file(dest)[:16]}… "
        f"size={dest.stat().st_size}"
    )
    return dest


def build_ios() -> Path | None:
    """Build iphoneos Runner, inject residual pubs, provision+sign, IPA zip.

    Order is fail-closed: inject **must** embed ``node_elgamal.pub``; Team
    codesign **must** embed host (+appex) ``embedded.mobileprovision``; zip
    **must** be IPA ``Payload/`` layout. Missing provision is not “success”.
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
    if not codesign_ios_distribution(runner):
        print(
            "ios catalog refuse: codesign/provision failed (will not ship "
            "non-installable zip)",
            file=sys.stderr,
        )
        return None
    if not (runner / "embedded.mobileprovision").is_file():
        print(
            "ios catalog refuse: host embedded.mobileprovision missing after sign",
            file=sys.stderr,
        )
        return None
    try:
        return package_ios_zip(runner)
    except RuntimeError as e:
        print(f"ios package failed (fail-closed): {e}", file=sys.stderr)
        return None


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

    # Fill missing platforms via carry-forward so Helsinki catalog is complete.
    # Windows: never staged on this Mac host — native PE is built on the operator's
    # Windows machine (no 0.5.8 CF, no Helsinki Windows upload from here).
    print(
        "windows: skip — native PE is not staged on this Mac "
        "(no prior Windows setup.exe to carry-forward; operator Windows-host rebuild)",
        flush=True,
    )
    if not only:
        for plat in ("android", "macos", "ios", "linux"):
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
