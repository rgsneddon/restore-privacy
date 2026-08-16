#!/usr/bin/env python3
"""IPA-compatible iOS packaging for Restore Privacy catalog sideload.

Catalog iOS must be installable by standard sideload tools (rename-to-``.ipa``):

* Archive layout: ``Payload/<App>.app/…`` (not a bare top-level ``Runner.app`` zip)
* Host + Packet Tunnel carry ``embedded.mobileprovision`` after Team codesign
* Fail closed when Distribution/Development codesign is claimed without matching
  operator provisioning profiles — never ship a non-installable “Team-signed”
  zip as success

Product bundle IDs (must match ``client_app`` Xcode + RptVpnChannel)::

  host:   com.restoreprivacy.restorePrivacyClient
  tunnel: com.restoreprivacy.restorePrivacyClient.PacketTunnel
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import tempfile
import urllib.parse
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

HOST_BUNDLE_ID = "com.restoreprivacy.restorePrivacyClient"
TUNNEL_BUNDLE_ID = "com.restoreprivacy.restorePrivacyClient.PacketTunnel"
TEAM_ID = "SFCBP95595"

DEFAULT_DISTRIBUTION_IDENTITY = "Apple Distribution: Russell Sneddon (SFCBP95595)"
DEFAULT_DEVELOPMENT_IDENTITY = "Apple Development: Russell Sneddon (U37S5938B4)"


class IosSideloadError(RuntimeError):
    """Raised when the catalog iOS package cannot be made installable."""


@dataclass(frozen=True)
class ProvisionProfile:
    path: Path
    name: str
    application_identifier: str  # e.g. TEAM.bundle.id
    bundle_id: str
    get_task_allow: bool
    has_devices: bool
    provisions_all_devices: bool
    entitlements: dict

    @property
    def is_development(self) -> bool:
        return bool(self.get_task_allow)

    @property
    def is_ad_hoc(self) -> bool:
        return self.has_devices and not self.get_task_allow

    @property
    def is_app_store(self) -> bool:
        return (
            not self.has_devices
            and not self.provisions_all_devices
            and not self.get_task_allow
        )


def profile_search_dirs() -> list[Path]:
    home = Path.home()
    return [
        home / "Library" / "MobileDevice" / "Provisioning Profiles",
        home / "Library" / "Developer" / "Xcode" / "UserData" / "Provisioning Profiles",
    ]


def decode_mobileprovision(path: Path) -> dict:
    raw = subprocess.check_output(
        ["security", "cms", "-D", "-i", str(path)],
        stderr=subprocess.DEVNULL,
    )
    return plistlib.loads(raw)


def _bundle_id_from_app_id(app_id: str) -> str:
    # TEAMID.bundle.id → bundle.id
    if "." not in app_id:
        return app_id
    parts = app_id.split(".", 1)
    if len(parts[0]) == 10 and parts[0].isalnum():
        return parts[1]
    return app_id


def load_provision_profile(path: Path) -> ProvisionProfile | None:
    try:
        pl = decode_mobileprovision(path)
    except (subprocess.CalledProcessError, OSError, plistlib.InvalidFileException):
        return None
    ents = pl.get("Entitlements") or {}
    app_id = str(ents.get("application-identifier") or "")
    if not app_id:
        return None
    return ProvisionProfile(
        path=path,
        name=str(pl.get("Name") or path.name),
        application_identifier=app_id,
        bundle_id=_bundle_id_from_app_id(app_id),
        get_task_allow=bool(ents.get("get-task-allow")),
        has_devices=bool(pl.get("ProvisionedDevices")),
        provisions_all_devices=bool(pl.get("ProvisionsAllDevices")),
        entitlements=dict(ents),
    )


def iter_local_profiles(dirs: Iterable[Path] | None = None) -> list[ProvisionProfile]:
    out: list[ProvisionProfile] = []
    for d in dirs or profile_search_dirs():
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if f.suffix not in (".mobileprovision", ".provisionprofile"):
                continue
            prof = load_provision_profile(f)
            if prof is not None:
                out.append(prof)
    return out


def find_profile_for_bundle(
    bundle_id: str,
    *,
    profiles: list[ProvisionProfile] | None = None,
    prefer_installable: bool = True,
) -> ProvisionProfile | None:
    """Pick best profile for *bundle_id*.

    Prefer profiles that can install on devices (development / ad hoc with
    ProvisionedDevices) over pure App Store profiles when *prefer_installable*.
    """
    cands = [
        p
        for p in (profiles if profiles is not None else iter_local_profiles())
        if p.bundle_id == bundle_id
    ]
    if not cands:
        return None

    def rank(p: ProvisionProfile) -> tuple:
        # Higher is better when prefer_installable
        installable = 2 if (p.has_devices or p.provisions_all_devices) else 0
        # Prefer ad hoc (Distribution + devices) over dev when both exist
        ad_hoc = 1 if p.is_ad_hoc else 0
        dev = 1 if p.is_development else 0
        if prefer_installable:
            return (installable, ad_hoc, dev, p.path.stat().st_mtime)
        # Prefer store / distribution style
        store = 1 if p.is_app_store else 0
        return (store, ad_hoc, installable, p.path.stat().st_mtime)

    return sorted(cands, key=rank, reverse=True)[0]


def identity_for_profile(
    profile: ProvisionProfile,
    *,
    distribution: str | None = None,
    development: str | None = None,
) -> str:
    dist = distribution or os.environ.get(
        "RP_IOS_CODESIGN_IDENTITY", DEFAULT_DISTRIBUTION_IDENTITY
    )
    dev = development or os.environ.get(
        "RP_IOS_DEVELOPMENT_IDENTITY", DEFAULT_DEVELOPMENT_IDENTITY
    )
    if profile.is_development:
        return dev
    return dist


# iOS App Store rejects some macOS-only / newer NE tokens baked into
# MAC_APP_DIRECT / IOS_APP_STORE templates (ITMS-90046).
_IOS_UNSUPPORTED_NE = frozenset({"hotspot-provider"})


def ios_app_store_entitlements(ents: dict) -> dict:
    """Copy profile entitlements, dropping iOS-invalid Network Extension tokens."""
    out = dict(ents)
    ne = out.get("com.apple.developer.networking.networkextension")
    if isinstance(ne, list):
        filtered = [x for x in ne if x not in _IOS_UNSUPPORTED_NE]
        if filtered:
            out["com.apple.developer.networking.networkextension"] = filtered
        else:
            out.pop("com.apple.developer.networking.networkextension", None)
    return out


def write_entitlements_plist(profile: ProvisionProfile, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        plistlib.dump(ios_app_store_entitlements(profile.entitlements), f)
    return dest


# App Store Connect rejects binaries that link camera/auth/photo APIs without
# a purpose string (ITMS-90683). Flutter plugins in this client do that.
_IOS_PRIVACY_USAGE = {
    "NSCameraUsageDescription": (
        "Restore Privacy uses the camera to scan a KEYGEN or node QR code so "
        "you can unlock or join without typing. The image stays on this device."
    ),
    "NSFaceIDUsageDescription": (
        "Restore Privacy can use Face ID to unlock stored KEYGEN or vault "
        "secrets on this device."
    ),
    "NSPhotoLibraryUsageDescription": (
        "Restore Privacy can read a photo you choose so you can import a "
        "KEYGEN or QR image. Nothing is uploaded."
    ),
    "NSPhotoLibraryAddUsageDescription": (
        "Restore Privacy can save an export you choose (for example a local "
        "connection log) to Photos on this device."
    ),
    "NSMicrophoneUsageDescription": (
        "Some on-device scanner libraries declare microphone access. Restore "
        "Privacy does not record audio for VPN Connect."
    ),
}


def ensure_ios_privacy_usage_keys(info_plist: Path) -> list[str]:
    """Insert missing App Store purpose strings. Returns keys that were added."""
    if not info_plist.is_file():
        raise IosSideloadError(f"Info.plist missing: {info_plist}")
    with info_plist.open("rb") as f:
        pl = plistlib.load(f)
    if not isinstance(pl, dict):
        raise IosSideloadError(f"Info.plist is not a dict: {info_plist}")
    added: list[str] = []
    for key, text in _IOS_PRIVACY_USAGE.items():
        if not str(pl.get(key) or "").strip():
            pl[key] = text
            added.append(key)
    if added:
        with info_plist.open("wb") as f:
            plistlib.dump(pl, f)
    return added


def _ensure_tunnel_version_keys(runner: Path, appex: Path) -> None:
    """App Store requires CFBundleVersion + CFBundleShortVersionString on the appex."""
    host_pl = runner / "Info.plist"
    tun_pl = appex / "Info.plist"
    host = {}
    if host_pl.is_file():
        with host_pl.open("rb") as f:
            loaded = plistlib.load(f)
            if isinstance(loaded, dict):
                host = loaded
    short = str(host.get("CFBundleShortVersionString") or "").strip() or "1.0"
    build = str(host.get("CFBundleVersion") or "").strip() or "1"
    if not tun_pl.is_file():
        return
    with tun_pl.open("rb") as f:
        tun = plistlib.load(f)
    if not isinstance(tun, dict):
        return
    changed = False
    if not str(tun.get("CFBundleShortVersionString") or "").strip():
        tun["CFBundleShortVersionString"] = short
        changed = True
    if not str(tun.get("CFBundleVersion") or "").strip():
        tun["CFBundleVersion"] = build
        changed = True
    if changed:
        with tun_pl.open("wb") as f:
            plistlib.dump(tun, f)


def embed_mobileprovision(bundle: Path, profile: ProvisionProfile) -> Path:
    """Copy profile to ``bundle/embedded.mobileprovision`` (required for install)."""
    if not bundle.is_dir():
        raise IosSideloadError(f"bundle not a directory: {bundle}")
    dest = bundle / "embedded.mobileprovision"
    shutil.copy2(profile.path, dest)
    if dest.stat().st_size < 64:
        raise IosSideloadError(f"embedded.mobileprovision too small: {dest}")
    return dest


def _codesign(path: Path, identity: str, entitlements: Path | None = None) -> None:
    cmd = [
        "codesign",
        "--force",
        "--timestamp",
        "--generate-entitlement-der",
        "--sign",
        identity,
    ]
    if entitlements is not None and entitlements.is_file():
        cmd.extend(["--entitlements", str(entitlements)])
    cmd.append(str(path))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        raise IosSideloadError(f"codesign failed for {path}: {err}")


def codesign_ios_runner_with_profiles(
    runner: Path,
    *,
    host_profile: ProvisionProfile,
    tunnel_profile: ProvisionProfile | None,
    work_dir: Path | None = None,
) -> str:
    """Inside-out codesign Runner.app after embedding provisions.

    Returns the codesign identity used for the host.
    """
    if not runner.is_dir():
        raise IosSideloadError(f"Runner.app missing: {runner}")

    host_identity = identity_for_profile(host_profile)
    ensure_ios_privacy_usage_keys(runner / "Info.plist")
    embed_mobileprovision(runner, host_profile)

    td = work_dir or Path(tempfile.mkdtemp(prefix="ios-ents-"))
    td.mkdir(parents=True, exist_ok=True)
    host_ent = write_entitlements_plist(host_profile, td / "host.entitlements")

    # Inside-out: plugin .bundle nested in a .framework must be signed before
    # the parent framework. Signing the bundle afterwards invalidates the
    # framework seal (ITMS-90035 sealed resource missing or invalid).
    for bundle in sorted(
        (p for p in runner.rglob("*.bundle") if p.is_dir() and "PlugIns" not in p.parts),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        _codesign(bundle, host_identity)
    fw_dir = runner / "Frameworks"
    if fw_dir.is_dir():
        for fw in sorted(fw_dir.glob("*.framework")):
            _codesign(fw, host_identity)

    appex = runner / "PlugIns" / "PacketTunnel.appex"
    if appex.is_dir():
        if tunnel_profile is None:
            raise IosSideloadError(
                "PacketTunnel.appex present but no tunnel provisioning profile"
            )
        _ensure_tunnel_version_keys(runner, appex)
        tunnel_identity = identity_for_profile(tunnel_profile)
        embed_mobileprovision(appex, tunnel_profile)
        tunnel_ent = write_entitlements_plist(
            tunnel_profile, td / "tunnel.entitlements"
        )
        _codesign(appex, tunnel_identity, tunnel_ent)

    _codesign(runner, host_identity, host_ent)
    return host_identity


def package_ios_ipa_zip(runner: Path, dest: Path, *, app_name: str = "Runner.app") -> Path:
    """Write catalog zip with IPA layout: ``Payload/<app_name>/…``."""
    if not runner.is_dir():
        raise IosSideloadError(f"Runner.app missing: {runner}")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(runner):
            for fn in files:
                fp = Path(root) / fn
                rel = fp.relative_to(runner)
                arc = Path("Payload") / app_name / rel
                zf.write(fp, arc.as_posix())
    if dest.stat().st_size < 1_000_000 and any(
        (runner / "Frameworks").glob("*")
    ):
        # Tiny fixture zips OK in tests; real Flutter apps exceed 1MB
        pass
    write_ios_ipa_sibling(dest)
    return dest


def ios_ipa_sibling_path(zip_path: Path) -> Path:
    """Catalog ``*-ios.zip`` → sibling ``*-ios.ipa`` (same IPA bytes)."""
    p = Path(zip_path)
    if p.suffix.lower() == ".ipa":
        return p
    return p.with_suffix(".ipa")


def write_ios_ipa_sibling(zip_path: Path) -> Path:
    """Copy catalog zip bytes to a ``.ipa`` sibling so iOS/sideload UTIs match.

    The zip is already IPA ``Payload/`` layout; iPhone/iPad will not treat
    ``.zip`` as an installer. Fail closed if the zip is missing.
    """
    src = Path(zip_path)
    if not src.is_file():
        raise IosSideloadError(f"iOS zip missing for IPA sibling: {src}")
    dest = ios_ipa_sibling_path(src)
    if dest.resolve() != src.resolve():
        shutil.copy2(src, dest)
    return dest


def ios_install_download_filename(catalog_name: str) -> str:
    """On-device download name: ``…-ios.zip`` → ``…-ios.ipa``."""
    name = (catalog_name or "").strip()
    if name.lower().endswith(".zip"):
        return name[: -len(".zip")] + ".ipa"
    if name.lower().endswith(".ipa"):
        return name
    return name + ".ipa" if name else "restore-privacy-client.ipa"


def ios_itms_services_href(manifest_https_url: str) -> str:
    """OTA install URL. Safari on iPhone/iPad opens this; a raw .zip tap does not."""
    url = (manifest_https_url or "").strip()
    if not url:
        raise IosSideloadError("itms-services manifest URL is empty")
    return "itms-services://?action=download-manifest&url=" + urllib.parse.quote(
        url, safe=""
    )


def write_ios_ota_manifest(
    dest: Path,
    *,
    ipa_https_url: str,
    bundle_id: str = HOST_BUNDLE_ID,
    bundle_version: str = "",
    title: str = "Restore Privacy",
) -> Path:
    """Write Apple OTA ``manifest.plist`` for *ipa_https_url* (itms-services)."""
    ipa_url = (ipa_https_url or "").strip()
    if not ipa_url:
        raise IosSideloadError("OTA manifest missing IPA HTTPS URL")
    bid = (bundle_id or HOST_BUNDLE_ID).strip() or HOST_BUNDLE_ID
    ver = (bundle_version or "").strip() or "1.0"
    title_s = (title or "Restore Privacy").strip() or "Restore Privacy"
    plist = {
        "items": [
            {
                "assets": [
                    {
                        "kind": "software-package",
                        "url": ipa_url,
                    }
                ],
                "metadata": {
                    "bundle-identifier": bid,
                    "bundle-version": ver,
                    "kind": "software",
                    "title": title_s,
                },
            }
        ]
    }
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        plistlib.dump(plist, f)
    return dest


def inspect_ios_zip(path: Path) -> dict:
    """Structural facts for a catalog iOS zip (real zipfile API)."""
    path = Path(path)
    report: dict = {
        "path": str(path),
        "exists": path.is_file(),
        "size": path.stat().st_size if path.is_file() else 0,
        "names_sample": [],
        "has_payload_prefix": False,
        "has_top_level_runner_only": False,
        "host_embedded_mobileprovision": False,
        "tunnel_embedded_mobileprovision": False,
        "packet_tunnel_appex": False,
        "node_elgamal_pub": False,
        "private_key_members": [],
        "app_prefix": None,
    }
    if not path.is_file():
        return report
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        report["names_sample"] = names[:40]
        payload_apps = [
            n for n in names if n.startswith("Payload/") and ".app/" in n
        ]
        report["has_payload_prefix"] = bool(payload_apps)
        top_runner = [
            n for n in names if n.startswith("Runner.app/") and not n.startswith("Payload/")
        ]
        report["has_top_level_runner_only"] = bool(top_runner) and not report[
            "has_payload_prefix"
        ]
        # Detect app root under Payload/
        app_prefix = None
        for n in names:
            if n.startswith("Payload/") and n.endswith(".app/"):
                app_prefix = n.rstrip("/")
                break
            if n.startswith("Payload/") and ".app/" in n:
                app_prefix = n.split(".app/")[0] + ".app"
                break
        if app_prefix is None and top_runner:
            app_prefix = "Runner.app"
        report["app_prefix"] = app_prefix
        if app_prefix:
            host_prov = f"{app_prefix}/embedded.mobileprovision"
            report["host_embedded_mobileprovision"] = host_prov in names
            tunnel_prov_suffix = "/PlugIns/PacketTunnel.appex/embedded.mobileprovision"
            report["tunnel_embedded_mobileprovision"] = any(
                n.endswith(tunnel_prov_suffix) or n == f"{app_prefix}{tunnel_prov_suffix}"
                for n in names
            )
            report["packet_tunnel_appex"] = any(
                "PacketTunnel.appex" in n for n in names
            )
            report["node_elgamal_pub"] = any(
                Path(n).name == "node_elgamal.pub" for n in names
            )
        report["private_key_members"] = [
            n
            for n in names
            if n.endswith(".priv")
            or "private_key" in n.lower()
            or n.endswith("_priv.pem")
        ]
    return report


def require_installable_ios_zip(path: Path, *, require_provision: bool = True) -> dict:
    """Fail closed if zip is bare Runner.app or lacks host provision when required."""
    rep = inspect_ios_zip(path)
    if not rep["exists"]:
        raise IosSideloadError(f"iOS zip missing: {path}")
    if rep["has_top_level_runner_only"]:
        raise IosSideloadError(
            f"iOS zip is bare top-level Runner.app (not IPA Payload layout): {path}"
        )
    if not rep["has_payload_prefix"]:
        raise IosSideloadError(
            f"iOS zip missing Payload/ IPA layout: {path}"
        )
    if require_provision and not rep["host_embedded_mobileprovision"]:
        raise IosSideloadError(
            f"iOS zip missing host embedded.mobileprovision (not installable): {path}"
        )
    if require_provision and rep["packet_tunnel_appex"] and not rep[
        "tunnel_embedded_mobileprovision"
    ]:
        raise IosSideloadError(
            f"iOS zip has PacketTunnel.appex without embedded.mobileprovision: {path}"
        )
    if rep["private_key_members"]:
        raise IosSideloadError(
            f"iOS zip contains private key material: {rep['private_key_members']}"
        )
    return rep


def prepare_signed_sideload_app(
    runner: Path,
    *,
    profiles: list[ProvisionProfile] | None = None,
    require_profiles: bool = True,
) -> dict:
    """Embed provisions + codesign. Fail closed when *require_profiles* and missing."""
    host = find_profile_for_bundle(HOST_BUNDLE_ID, profiles=profiles)
    tunnel = find_profile_for_bundle(TUNNEL_BUNDLE_ID, profiles=profiles)
    if require_profiles:
        if host is None:
            raise IosSideloadError(
                f"No iOS provisioning profile for host {HOST_BUNDLE_ID}. "
                "Install a Development/Ad Hoc profile for Team SFCBP95595 "
                "under ~/Library/MobileDevice/Provisioning Profiles."
            )
        appex = runner / "PlugIns" / "PacketTunnel.appex"
        if appex.is_dir() and tunnel is None:
            raise IosSideloadError(
                f"No iOS provisioning profile for tunnel {TUNNEL_BUNDLE_ID}."
            )
    if host is None:
        return {
            "signed": False,
            "skipped": True,
            "reason": "no_host_profile",
        }
    with tempfile.TemporaryDirectory(prefix="ios-sideload-") as td:
        identity = codesign_ios_runner_with_profiles(
            runner,
            host_profile=host,
            tunnel_profile=tunnel,
            work_dir=Path(td),
        )
    # Verify provisions present on disk after sign
    if not (runner / "embedded.mobileprovision").is_file():
        raise IosSideloadError("host embedded.mobileprovision missing after sign")
    appex = runner / "PlugIns" / "PacketTunnel.appex"
    if appex.is_dir() and not (appex / "embedded.mobileprovision").is_file():
        raise IosSideloadError("tunnel embedded.mobileprovision missing after sign")
    return {
        "signed": True,
        "skipped": False,
        "identity": identity,
        "host_profile": str(host.path),
        "tunnel_profile": str(tunnel.path) if tunnel else None,
        "host_profile_name": host.name,
        "tunnel_profile_name": tunnel.name if tunnel else None,
    }


def package_catalog_ios_zip(
    runner: Path,
    dest: Path,
    *,
    require_profiles: bool = True,
    profiles: list[ProvisionProfile] | None = None,
) -> tuple[Path, dict]:
    """Sign (fail-closed) + IPA-zip + structural require. Returns (dest, report)."""
    sign_info = prepare_signed_sideload_app(
        runner, profiles=profiles, require_profiles=require_profiles
    )
    if require_profiles and not sign_info.get("signed"):
        raise IosSideloadError(
            f"iOS catalog refuse: signing skipped ({sign_info.get('reason')})"
        )
    package_ios_ipa_zip(runner, dest)
    # Real Flutter apps are large; fixtures may be small — only enforce size
    # when Frameworks/Flutter.framework exists.
    flutter_fw = runner / "Frameworks" / "Flutter.framework"
    if flutter_fw.is_dir() and dest.stat().st_size < 1_000_000:
        raise IosSideloadError(f"catalog iOS zip too small: {dest}")
    rep = require_installable_ios_zip(
        dest, require_provision=bool(require_profiles and sign_info.get("signed"))
    )
    rep["sign"] = sign_info
    return dest, rep


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--app", type=Path, required=True, help="path to Runner.app")
    ap.add_argument("--zip", type=Path, required=True, help="output catalog zip")
    ap.add_argument(
        "--allow-unsigned",
        action="store_true",
        help="package IPA layout even without profiles (tests only)",
    )
    args = ap.parse_args()
    dest, rep = package_catalog_ios_zip(
        args.app,
        args.zip,
        require_profiles=not args.allow_unsigned,
    )
    print(json.dumps({"dest": str(dest), "report": rep}, indent=2, default=str))
