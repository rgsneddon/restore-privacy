"""Audit staged Apple catalog zips for monopin productVersion honesty.

Windows hosts cannot notarize; operators often stage placeholder zips under
``status_page/assets/{VERSION}/``. This helper reads CFBundleShortVersionString
from the real zip contents so CI / ops can detect mislabeled packages.

Also provides pure codesign-output parsers and optional live Gatekeeper checks
so **Apple Development** (or unsigned) zips cannot be treated as a catalog seal.
"""

from __future__ import annotations

import plistlib
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


def _read_short_version_from_plist_bytes(data: bytes) -> str | None:
    try:
        pl = plistlib.loads(data)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(pl, dict):
        return None
    ver = pl.get("CFBundleShortVersionString") or pl.get("CFBundleVersion")
    if ver is None:
        return None
    return str(ver).strip() or None


def inspect_apple_zip(path: Path, *, platform: str) -> dict[str, Any]:
    """Return version audit for one macos/ios catalog zip."""
    out: dict[str, Any] = {
        "path": str(path),
        "platform": platform,
        "exists": path.is_file(),
        "size": path.stat().st_size if path.is_file() else 0,
        "bundle_versions": [],
        "primary_version": None,
        "plist_paths": [],
    }
    if not path.is_file():
        out["error"] = "missing"
        return out
    try:
        with zipfile.ZipFile(path) as zf:
            plist_names = [
                n
                for n in zf.namelist()
                if n.endswith("Info.plist")
                and (
                    (platform == "macos" and "restore_privacy_client.app/Contents/Info.plist" in n)
                    or (platform == "ios" and n.endswith("Runner.app/Info.plist"))
                    or n.count("/") <= 3
                )
            ]
            # Prefer main app Info.plist
            preferred = []
            for n in zf.namelist():
                if platform == "macos" and n.endswith(
                    "restore_privacy_client.app/Contents/Info.plist"
                ):
                    preferred.append(n)
                if platform == "ios" and n.endswith("Runner.app/Info.plist"):
                    preferred.append(n)
            names = preferred or plist_names[:3]
            out["plist_paths"] = names
            versions: list[str] = []
            for n in names:
                ver = _read_short_version_from_plist_bytes(zf.read(n))
                if ver:
                    versions.append(ver)
                    out["bundle_versions"].append({"plist": n, "version": ver})
            out["primary_version"] = versions[0] if versions else None
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)[:200]
    return out


def macos_zip_cfbundle_short_version(path: Path | str) -> str | None:
    """Host app ``CFBundleShortVersionString`` from a macOS catalog zip (or None)."""
    info = inspect_apple_zip(Path(path), platform="macos")
    ver = info.get("primary_version")
    return str(ver).strip() if ver else None


def parse_codesign_dv_output(text: str) -> dict[str, Any]:
    """Pure parse of ``codesign -dv --verbose=2`` stderr/stdout text."""
    lines = (text or "").splitlines()
    authorities: list[str] = []
    team = ""
    runtime = ""
    notarization = ""
    identifier = ""
    for line in lines:
        s = line.strip()
        if s.startswith("Authority="):
            authorities.append(s.split("=", 1)[1].strip())
        elif s.startswith("TeamIdentifier="):
            team = s.split("=", 1)[1].strip()
        elif s.startswith("Runtime Version="):
            runtime = s.split("=", 1)[1].strip()
        elif s.startswith("Notarization Ticket="):
            notarization = s.split("=", 1)[1].strip()
        elif s.startswith("Identifier="):
            identifier = s.split("=", 1)[1].strip()
    leaf = authorities[0] if authorities else ""
    is_dev_id = "Developer ID Application" in leaf
    is_apple_development = leaf.startswith("Apple Development:")
    is_adhoc = "Signature=adhoc" in text or leaf == ""
    return {
        "authorities": authorities,
        "leaf_authority": leaf,
        "team_identifier": team,
        "runtime_version": runtime,
        "notarization_ticket": notarization,
        "identifier": identifier,
        "is_developer_id_application": is_dev_id,
        "is_apple_development": is_apple_development,
        "is_adhoc": is_adhoc,
        "ticket_stapled": notarization.lower() == "stapled",
    }


def distribution_seal_ok_from_codesign(text: str) -> dict[str, Any]:
    """Pure: catalog distribution seal requires Developer ID Application leaf.

    Apple Development / ad-hoc fail closed — they produce Gatekeeper
    \"Apple could not verify… / Not Opened\" for downloaded apps.
    """
    parsed = parse_codesign_dv_output(text)
    ok = bool(parsed["is_developer_id_application"]) and not parsed["is_apple_development"]
    reason = "developer_id_application"
    if parsed["is_apple_development"]:
        reason = "apple_development_not_distribution"
    elif parsed["is_adhoc"] or not parsed["leaf_authority"]:
        reason = "unsigned_or_adhoc"
    elif not parsed["is_developer_id_application"]:
        reason = "not_developer_id_application"
    return {
        "ok": ok,
        "reason": reason,
        **parsed,
    }


def assess_macos_catalog_zip_codesign(path: Path | str) -> dict[str, Any]:
    """Extract catalog zip and run real ``codesign -dv`` (Darwin only).

    Returns distribution_seal_ok fields; on non-Darwin or missing zip, reports
    error without claiming a notarized seal.
    """
    p = Path(path)
    out: dict[str, Any] = {
        "path": str(p),
        "exists": p.is_file(),
        "ok": False,
        "reason": "unknown",
    }
    if not p.is_file():
        out["reason"] = "missing_zip"
        return out
    import sys

    if sys.platform != "darwin":
        out["reason"] = "not_darwin"
        out["note"] = "codesign assessment requires macOS"
        return out
    try:
        with tempfile.TemporaryDirectory() as td:
            # ditto preserves code signature / staple; Python zipfile does not
            # (spctl then reports "no usable signature" on extracted apps).
            dig = subprocess.run(
                ["ditto", "-x", "-k", str(p), td],
                capture_output=True,
                text=True,
            )
            if dig.returncode != 0:
                # Fallback: system unzip
                dig2 = subprocess.run(
                    ["unzip", "-q", str(p), "-d", td],
                    capture_output=True,
                    text=True,
                )
                if dig2.returncode != 0:
                    out["reason"] = "extract_failed"
                    out["error"] = ((dig.stderr or "") + (dig2.stderr or ""))[:200]
                    return out
            apps = list(Path(td).rglob("restore_privacy_client.app"))
            if not apps:
                apps = list(Path(td).rglob("*.app"))
            if not apps:
                out["reason"] = "no_app_in_zip"
                return out
            app = apps[0]
            proc = subprocess.run(
                ["codesign", "-dv", "--verbose=2", str(app)],
                capture_output=True,
                text=True,
            )
            # codesign -dv writes to stderr
            text = (proc.stderr or "") + (proc.stdout or "")
            seal = distribution_seal_ok_from_codesign(text)
            out.update(seal)
            out["codesign_exit"] = proc.returncode
            out["app_path"] = str(app)
            # Deep seal: nested frameworks must verify (Python zipfile packaging
            # often leaves outer DevID leaf but unsigned FlutterMacOS.framework).
            deep = subprocess.run(
                [
                    "codesign",
                    "--verify",
                    "--deep",
                    "--strict",
                    "--verbose=2",
                    str(app),
                ],
                capture_output=True,
                text=True,
            )
            deep_text = ((deep.stderr or "") + (deep.stdout or "")).strip()
            out["codesign_deep_exit"] = deep.returncode
            out["codesign_deep_text"] = deep_text[:400]
            out["codesign_deep_ok"] = deep.returncode == 0
            if seal.get("ok") and deep.returncode != 0:
                out["ok"] = False
                out["reason"] = "codesign_deep_verify_failed"
            # Live Gatekeeper assess when seal claims DevID + deep ok
            if out.get("ok"):
                sp = subprocess.run(
                    ["spctl", "--assess", "--type", "execute", "-vv", str(app)],
                    capture_output=True,
                    text=True,
                )
                sp_text = (sp.stderr or "") + (sp.stdout or "")
                out["spctl_exit"] = sp.returncode
                out["spctl_text"] = sp_text.strip()[:400]
                out["spctl_notarized_developer_id"] = (
                    "Notarized Developer ID" in sp_text
                    or "source=Notarized Developer ID" in sp_text
                )
                if sp.returncode != 0 or not out["spctl_notarized_developer_id"]:
                    out["ok"] = False
                    out["reason"] = "spctl_not_notarized_developer_id"
            return out
    except Exception as exc:  # noqa: BLE001
        out["reason"] = "assess_error"
        out["error"] = str(exc)[:200]
        return out


def require_macos_zip_developer_id_distribution(path: Path | str) -> dict[str, Any]:
    """Fail closed when catalog zip is not Developer ID (and ideally notarized)."""
    report = assess_macos_catalog_zip_codesign(path)
    if not report.get("ok"):
        raise RuntimeError(
            f"macOS catalog zip is not a Developer ID distribution seal: "
            f"reason={report.get('reason')!r} leaf={report.get('leaf_authority')!r} "
            f"path={path}. Rebuild with scripts/sign_and_notarize_macos.py "
            f"(RP_CODESIGN_IDENTITY=Developer ID Application… + notarytool)."
        )
    return report


def host_app_has_packet_tunnel_provider(app: Path | str) -> bool:
    """True when the host app embeds packet-tunnel-provider (residual NE)."""
    p = Path(app)
    if not p.is_dir():
        return False
    proc = subprocess.run(
        ["codesign", "-d", "--entitlements", ":-", str(p)],
        capture_output=True,
    )
    blob = (proc.stdout or b"") + (proc.stderr or b"")
    return b"packet-tunnel-provider" in blob


def launch_probe_app_alive(app: Path | str, *, settle_s: float = 2.5) -> dict[str, Any]:
    """Prove *app* launches and stays alive (not AMFI SIGKILL 137).

    Same contract as ``scripts/sign_and_notarize_macos.launch_probe_alive`` —
    kept here so residual catalog audit does not require importing ship scripts.
    """
    import time

    p = Path(app)
    main_bin = p / "Contents" / "MacOS" / "restore_privacy_client"
    if not main_bin.is_file():
        # Alternate product binary name inside Contents/MacOS
        mac = p / "Contents" / "MacOS"
        bins = [x for x in mac.iterdir() if x.is_file()] if mac.is_dir() else []
        if not bins:
            return {"ok": False, "error": f"missing main binary under {mac}", "rc": None}
        main_bin = bins[0]
    proc = subprocess.Popen(
        [str(main_bin)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    time.sleep(settle_s)
    rc = proc.poll()
    if rc is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
        return {"ok": True, "rc": None, "alive": True, "error": None}
    return {
        "ok": False,
        "rc": rc,
        "alive": False,
        "error": f"app exited immediately rc={rc} (137=AMFI SIGKILL often host NE)",
    }


def assess_macos_zip_residual_capable(path: Path | str) -> dict[str, Any]:
    """Catalog residual seal: host packet-tunnel-provider + codesign valid + launch alive.

    Residual monopin ships Team residual (Apple Development + NE profiles) so
    Packet Tunnel can register. That is **not** Notarized Developer ID — and
    must not be confused with DevID+host-NE which AMFI kills (rc=137).
    """
    p = Path(path)
    out: dict[str, Any] = {
        "path": str(p),
        "exists": p.is_file(),
        "ok": False,
        "reason": "unknown",
        "host_packet_tunnel_provider": False,
        "launch_alive": False,
    }
    if not p.is_file():
        out["reason"] = "missing_zip"
        return out
    import sys

    if sys.platform != "darwin":
        out["reason"] = "not_darwin"
        return out
    try:
        with tempfile.TemporaryDirectory() as td:
            dig = subprocess.run(
                ["ditto", "-x", "-k", str(p), td],
                capture_output=True,
                text=True,
            )
            if dig.returncode != 0:
                dig2 = subprocess.run(
                    ["unzip", "-q", str(p), "-d", td],
                    capture_output=True,
                    text=True,
                )
                if dig2.returncode != 0:
                    out["reason"] = "extract_failed"
                    out["error"] = ((dig.stderr or "") + (dig2.stderr or ""))[:200]
                    return out
            apps = list(Path(td).rglob("restore_privacy_client.app"))
            if not apps:
                apps = [a for a in Path(td).rglob("*.app") if a.is_dir()]
            if not apps:
                out["reason"] = "no_app_in_zip"
                return out
            app = apps[0]
            out["app_path"] = str(app)
            # Prefer host app (not nested appex)
            for cand in apps:
                if cand.name == "restore_privacy_client.app" or (
                    "PacketTunnel" not in cand.name and cand.suffix == ".app"
                ):
                    app = cand
                    out["app_path"] = str(app)
                    break
            deep = subprocess.run(
                ["codesign", "--verify", "--deep", "--strict", str(app)],
                capture_output=True,
                text=True,
            )
            out["codesign_deep_exit"] = deep.returncode
            out["codesign_deep_ok"] = deep.returncode == 0
            if deep.returncode != 0:
                out["reason"] = "codesign_deep_verify_failed"
                out["error"] = ((deep.stderr or "") + (deep.stdout or ""))[:300]
                return out
            dv = subprocess.run(
                ["codesign", "-dv", "--verbose=2", str(app)],
                capture_output=True,
                text=True,
            )
            text = (dv.stderr or "") + (dv.stdout or "")
            parsed = parse_codesign_dv_output(text)
            out.update({k: parsed[k] for k in parsed})
            has_ne = host_app_has_packet_tunnel_provider(app)
            out["host_packet_tunnel_provider"] = has_ne
            if not has_ne:
                out["reason"] = "host_missing_packet_tunnel_provider"
                return out
            probe = launch_probe_app_alive(app)
            out["launch_probe"] = probe
            out["launch_alive"] = bool(probe.get("ok"))
            if not probe.get("ok"):
                out["reason"] = "launch_probe_failed"
                out["error"] = probe.get("error")
                return out
            out["ok"] = True
            out["reason"] = "residual_capable_host_ne_launch_alive"
            return out
    except Exception as exc:  # noqa: BLE001
        out["reason"] = "assess_error"
        out["error"] = str(exc)[:200]
        return out


def require_macos_zip_residual_capable(path: Path | str) -> dict[str, Any]:
    """Fail closed when catalog residual monopin lacks host NE or dies on launch."""
    report = assess_macos_zip_residual_capable(path)
    if not report.get("ok"):
        raise RuntimeError(
            f"macOS residual monopin seal failed: reason={report.get('reason')!r} "
            f"host_ne={report.get('host_packet_tunnel_provider')} "
            f"launch_alive={report.get('launch_alive')} path={path}. "
            f"Package residual-team.app (Team residual NE + launch probe), "
            f"not DevID+host-NE without a DevID NE profile (AMFI 137)."
        )
    return report


def require_macos_zip_matches_monopin(path: Path | str, monopin: str) -> str:
    """Fail closed when paid macOS zip CFBundle lags (or leads) the catalog monopin.

    Used by release/stage and paid-asset upload so a carry-forward rename cannot
    become the current catalog installer with a stale internal CFBundle.
    """
    pin = (monopin or "").strip()
    p = Path(path)
    if not pin:
        raise ValueError("monopin required")
    if not p.is_file():
        raise FileNotFoundError(f"macOS catalog zip missing: {p}")
    found = macos_zip_cfbundle_short_version(p)
    if found != pin:
        raise RuntimeError(
            f"macOS CFBundleShortVersionString {found!r} != monopin {pin!r} "
            f"in {p}; refuse catalog publish — rebuild Flutter macOS release "
            f"so FLUTTER_BUILD_NAME/pubspec product version is {pin} "
            f"(scripts/build_release_{pin}.py --apple-only on Darwin)."
        )
    return found


def ios_zip_cfbundle_short_version(path: Path | str) -> str | None:
    """Host app ``CFBundleShortVersionString`` from an iOS catalog zip (or None)."""
    info = inspect_apple_zip(Path(path), platform="ios")
    ver = info.get("primary_version")
    return str(ver).strip() if ver else None


def require_ios_zip_matches_monopin(path: Path | str, monopin: str) -> str:
    """Fail closed when paid iOS zip CFBundle lags (or leads) the catalog monopin.

    Prevents secret-inject / Team-sign of a stale 0.5.x Runner.app into a
    monopin-named zip (same class of bug as macOS carry-forward rename).
    """
    pin = (monopin or "").strip()
    p = Path(path)
    if not pin:
        raise ValueError("monopin required")
    if not p.is_file():
        raise FileNotFoundError(f"iOS catalog zip missing: {p}")
    found = ios_zip_cfbundle_short_version(p)
    if found != pin:
        raise RuntimeError(
            f"iOS CFBundleShortVersionString {found!r} != monopin {pin!r} "
            f"in {p}; refuse catalog publish — rebuild Flutter iOS release "
            f"so FLUTTER_BUILD_NAME/pubspec product version is {pin} "
            f"(flutter build ios --release --no-codesign, then "
            f"scripts/build_release_{pin}.py --apple-only on Darwin)."
        )
    return found


def audit_catalog_apple_packages(
    *,
    version: str,
    assets_root: Path | None = None,
) -> dict[str, Any]:
    """Compare staged Apple zips under assets/{version}/ to catalog monopin."""
    root = assets_root or (
        Path(__file__).resolve().parent / "assets" / version
    )
    macos = root / f"restore-privacy-client-{version}-macos.zip"
    ios = root / f"restore-privacy-client-{version}-ios.zip"
    mac = inspect_apple_zip(macos, platform="macos")
    ios_a = inspect_apple_zip(ios, platform="ios")
    mac_ok = mac.get("primary_version") == version
    ios_ok = ios_a.get("primary_version") == version
    missing = (not mac.get("exists")) or (not ios_a.get("exists"))
    if mac_ok and ios_ok:
        honesty = "Apple zips match catalog monopin"
    elif missing:
        honesty = (
            "STAGED APPLE ZIPS MISSING under assets "
            f"(macos_exists={mac.get('exists')} ios_exists={ios_a.get('exists')}) "
            f"expected={version!r}. Re-build on Mac per client_app/APPLE_HANDOFF_"
            f"{version}.md then re-run host_paid_assets_vps.py --upload "
            "(status_page/assets/* is gitignored)."
        )
    else:
        honesty = (
            "STAGED APPLE ZIPS DO NOT MATCH CATALOG MONOPIN — "
            f"macos={mac.get('primary_version')!r} ios={ios_a.get('primary_version')!r} "
            f"expected={version!r}. Re-build on Mac per client_app/APPLE_HANDOFF_"
            f"{version}.md then re-run host_paid_assets_vps.py --upload."
        )
    return {
        "catalog_version": version,
        "assets_root": str(root),
        "macos": mac,
        "ios": ios_a,
        "macos_matches_catalog": mac_ok,
        "ios_matches_catalog": ios_ok,
        "all_match": bool(mac_ok and ios_ok),
        # True only when files exist but CFBundle/marketing version lags monopin
        "placeholder_suspected": bool(
            (mac.get("exists") and not mac_ok)
            or (ios_a.get("exists") and not ios_ok)
        ),
        "honesty": honesty,
    }
