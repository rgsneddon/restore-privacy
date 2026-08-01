#!/usr/bin/env python3
"""Collect per-device product installers and host them on the Helsinki store.

Enumerates the shipped catalog (one package per platform: windows, android,
macos, ios, linux), stages files under ``status_page/assets/{VERSION}/``, and
optionally uploads to the **dedicated Helsinki** paid-asset host (default
``135.181.152.10``) at::

  /opt/restore-privacy/paid_assets/{VERSION}/{filename}

The Iceland residual monopin (``82.221.101.241``) is **node-only** — do not use
it as the installer CDN. Status host (Render) proxies paid downloads from the
Helsinki store (``open_release_asset`` + ``RPT_ASSET_FETCH_TOKEN``).

Usage::

  # List catalog only (no I/O beyond reading constants)
  python scripts/host_paid_assets_vps.py --list

  # Stage from releases/{VERSION} or existing status_page/assets into paid layout
  python scripts/host_paid_assets_vps.py --stage

  # Upload to Helsinki store + install/restart token-gated serve (needs SSH)
  export RPT_SSH_HOST=135.181.152.10 RPT_SSH_USER=root
  # Working store keys on operator Macs (try in order if RPT_SSH_KEY unset):
  #   id_ed25519_restore_privacy_eu  (Helsinki store — current)
  #   id_ed25519_20260725            (legacy name if present)
  export RPT_SSH_KEY=~/.ssh/id_ed25519_restore_privacy_eu
  export RPT_ASSET_FETCH_TOKEN='long-random-secret'
  python scripts/host_paid_assets_vps.py --stage --upload --install-serve

  # Dry-run upload plan
  python scripts/host_paid_assets_vps.py --upload --dry-run

  # Remove paid-assets tree + unit from Iceland residual node (node-only cleanup)
  export RPT_SSH_HOST=82.221.101.241 RPT_SSH_USER=raskul RPT_SSH_SUDO=1
  export RPT_SSH_KEY=~/.ssh/id_ed25519_restore_privacy_vps
  python scripts/host_paid_assets_vps.py --remove-iceland-paid-assets

Environment (SSH):
  RPT_SSH_HOST  default Helsinki store host (payments.DEFAULT_VPS_ASSET_HOST)
  RPT_SSH_USER  default root
  RPT_SSH_KEY / RPT_SSH_PASSWORD
  RPT_ASSET_FETCH_TOKEN  shared secret for store HTTP serve + Render fetch
"""

from __future__ import annotations

import argparse
import os
import secrets
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "status_page"
sys.path.insert(0, str(STATUS))

from downloads import (  # noqa: E402
    RELEASE_VERSION,
    list_catalog_platform_packages,
)
from payments import (  # noqa: E402
    DEFAULT_VPS_ASSET_HOST,
    DEFAULT_VPS_ASSET_REMOTE_ROOT,
    VPS_ASSET_HTTP_PREFIX,
    catalog_filenames,
)

SERVE_SCRIPT_LOCAL = ROOT / "node" / "serve_paid_assets.py"
SERVE_SCRIPT_REMOTE = f"{DEFAULT_VPS_ASSET_REMOTE_ROOT}/serve_paid_assets.py"
UNIT_NAME = "rpt-paid-assets.service"
# Backend binds loopback only; nginx owns public 443/8081 and proxies here.
# Do NOT default install-serve to 8081/0.0.0.0 — that fights nginx and 502s the store.
DEFAULT_SERVE_BACKEND_PORT = 18081
DEFAULT_SERVE_BACKEND_BIND = "127.0.0.1"
DEFAULT_BREADCRUMBS_REMOTE_ROOT = "/opt/restore-privacy/breadcrumbs"


def list_packages(version: str | None = None) -> list[dict[str, str]]:
    """Shipped helper: current catalog version + five platform packages."""
    return list_catalog_platform_packages(version=version)


def list_brand_packages(version: str | None = None) -> list[dict[str, Any]]:
    """Full brand installer inventory for Helsinki push (Suite + rpOS + apps + extras)."""
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from brand_package_inventory import list_brand_installer_packages

    return list_brand_installer_packages(suite_version=version, repo_root=ROOT)


def stage_brand_packages(
    *,
    version: str | None = None,
    allow_missing: bool = False,
    progress_cb: Any | None = None,
) -> list[Path]:
    """Stage all brand packages into status_page/assets/{suite_version}/.

    Flat layout under the Suite catalog pin so Helsinki serve path stays simple.
    *progress_cb(filename, status, progress)* optional.
    """
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from brand_package_inventory import (
        inventory_with_presence,
        resolve_local_path,
        list_brand_installer_packages,
    )

    inv = inventory_with_presence(suite_version=version, repo_root=ROOT)
    suite_ver = inv["suite_version"]
    dst_dir = STATUS / "assets" / suite_ver
    dst_dir.mkdir(parents=True, exist_ok=True)
    staged: list[Path] = []
    for row in inv["packages"]:
        fname = row["filename"]
        if progress_cb:
            progress_cb(fname, "uploading", 5)
        src = resolve_local_path(row, repo_root=ROOT)
        if src is None:
            msg = f"missing brand package: {fname} ({row.get('relative_path')})"
            if allow_missing:
                print(f"skip_missing {msg}")
                if progress_cb:
                    progress_cb(fname, "skipped", 0)
                continue
            if progress_cb:
                progress_cb(fname, "error", 0)
            raise FileNotFoundError(msg)
        # Suite clients: keep CFBundle check via stage_packages path for macos
        dst = dst_dir / fname
        shutil.copy2(src, dst)
        staged.append(dst)
        print(f"staged kind={row.get('kind')} platform={row.get('platform')} {dst} ({dst.stat().st_size} bytes)")
        if progress_cb:
            progress_cb(fname, "done", 100)
    return staged


def upload_brand_packages(
    *,
    version: str | None = None,
    dry_run: bool = False,
    install_serve: bool = False,
    force: bool = False,
    allow_missing: bool = False,
    progress_cb: Any | None = None,
) -> int:
    """Upload staged brand packages (any size > min_bytes for kind)."""
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from brand_package_inventory import inventory_with_presence

    inv = inventory_with_presence(suite_version=version, repo_root=ROOT)
    suite_ver = inv["suite_version"]
    local_dir = STATUS / "assets" / suite_ver
    remote_root = os.environ.get(
        "RPT_VPS_ASSET_REMOTE_ROOT", DEFAULT_VPS_ASSET_REMOTE_ROOT
    ).strip() or DEFAULT_VPS_ASSET_REMOTE_ROOT
    remote_ver = f"{remote_root.rstrip('/')}/{suite_ver}"
    host_default = DEFAULT_VPS_ASSET_HOST

    present: list[dict[str, Any]] = []
    for row in inv["packages"]:
        fname = row["filename"]
        f = local_dir / fname
        min_b = int(row.get("min_bytes") or 1)
        if f.is_file() and f.stat().st_size >= min_b:
            present.append({**row, "local_path": str(f)})
        elif allow_missing:
            print(f"skip_missing upload kind={row.get('kind')} file={fname}")
            if progress_cb:
                progress_cb(fname, "skipped", 0)
        else:
            print(f"missing or too-small local stage: {f}", file=sys.stderr)
            return 1

    if not present:
        print("ERROR: no staged brand packages to upload", file=sys.stderr)
        return 1

    print(f"brand upload plan: {len(present)}/{inv['total']} files -> {host_default}:{remote_ver}/")
    for p in present:
        print(f"  {p.get('kind')}/{p.get('platform')}: {p['filename']}")

    if dry_run:
        for p in present:
            if progress_cb:
                progress_cb(p["filename"], "uploading", 50)
                progress_cb(p["filename"], "done", 100)
        print("dry-run: no SSH")
        return 0

    # Reuse SSH path from upload_packages for each file
    host, user, password, key_path = _ssh_target()
    use_openssh = password is None and key_path is not None and _openssh_available()
    if not use_openssh:
        print("ERROR: brand upload requires OpenSSH key transport", file=sys.stderr)
        return 1
    assert key_path is not None
    code, _ = _ssh_run_openssh(
        f"mkdir -p {remote_ver} && chown -R {user}:{user} {remote_root}",
        host=host,
        user=user,
        key_path=key_path,
        sudo=True,
    )
    if code != 0:
        print("ERROR: could not prepare remote paid_assets dir", file=sys.stderr)
        return 1
    for p in present:
        local = Path(p["local_path"])
        remote = f"{remote_ver}/{p['filename']}"
        if progress_cb:
            progress_cb(p["filename"], "uploading", 10)
        print(f"upload kind={p.get('kind')} file={p['filename']} ({local.stat().st_size} bytes)")
        try:
            _upload_one_installer_openssh(
                local,
                remote,
                host=host,
                user=user,
                key_path=key_path,
                skip_if_present=not force,
            )
            if progress_cb:
                progress_cb(p["filename"], "done", 100)
        except Exception as e:  # noqa: BLE001
            print(f"ERROR file={p['filename']}: {e}", file=sys.stderr)
            if progress_cb:
                progress_cb(p["filename"], "error", 0)
            return 1
    if install_serve:
        # Reuse catalog install-serve when requested
        return upload_packages(version=suite_ver, dry_run=False, install_serve=True, force=force, allow_missing=True)
    print(f"brand upload complete host={host_default} version={suite_ver}")
    return 0



def print_catalog(version: str | None = None) -> None:
    pkgs = list_packages(version)
    ver = pkgs[0]["version"] if pkgs else (version or RELEASE_VERSION)
    print(f"catalog_version={ver}")
    print(f"platforms={len(pkgs)}")
    for p in pkgs:
        print(
            f"  platform={p['platform']:<8} file={p['filename']} "
            f"rel={p['relative_path']}"
        )


def _candidate_sources(version: str, filename: str) -> list[Path]:
    """Prefer sealed ``releases/{ver}/`` over an older stage copy.

    ``status_page/assets`` is the upload stage dest; if it is listed first, a
    stale prior stage permanently shadows freshly notarized zips under
    ``releases/`` and re-hosts old Apple seals even with ``--force``.
    """
    return [
        ROOT / "releases" / version / filename,
        STATUS / "assets" / version / filename,
        STATUS / "assets" / RELEASE_VERSION / filename.replace(version, RELEASE_VERSION, 1)
        if version != RELEASE_VERSION
        else STATUS / "assets" / RELEASE_VERSION / filename,
    ]


def _assert_macos_cfbundle(path: Path, monopin: str) -> None:
    """Fail closed: paid macOS zip host CFBundle must equal catalog monopin."""
    from apple_package_audit import require_macos_zip_matches_monopin

    ver = require_macos_zip_matches_monopin(path, monopin)
    print(f"macos CFBundleShortVersionString={ver} matches monopin {monopin}")


def stage_packages(
    *,
    version: str | None = None,
    allow_missing: bool = False,
) -> list[Path]:
    """Copy each platform installer into status_page/assets/{version}/.

    When *allow_missing* is True, platforms without a local package are skipped
    (honest partial monopin stage — typical while Apple waits on Mac seal).
    """
    pkgs = list_packages(version)
    ver = pkgs[0]["version"]
    dst_dir = STATUS / "assets" / ver
    dst_dir.mkdir(parents=True, exist_ok=True)
    staged: list[Path] = []
    skipped: list[str] = []
    for p in pkgs:
        fname = p["filename"]
        src = None
        for cand in _candidate_sources(ver, fname):
            if cand.is_file() and cand.stat().st_size > 0:
                src = cand
                break
        if src is None:
            msg = (
                f"missing installer for platform={p['platform']}: {fname} "
                f"(looked under status_page/assets/ and releases/)"
            )
            if allow_missing:
                print(f"skip_missing {msg}")
                skipped.append(p["platform"])
                continue
            raise FileNotFoundError(msg)
        dst = dst_dir / fname
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        if p["platform"] == "macos":
            _assert_macos_cfbundle(dst, ver)
        staged.append(dst)
        print(f"staged platform={p['platform']} {dst} ({dst.stat().st_size} bytes)")
    if not staged:
        raise FileNotFoundError(
            f"no installers staged for version={ver} (all platforms missing)"
        )
    if skipped:
        print(f"allow_missing skipped platforms={','.join(skipped)}")
    # refuse privs
    for p in dst_dir.rglob("*.priv"):
        raise RuntimeError(f"refusing to stage private key: {p}")
    # Keep stage root tidy: only current catalog version directory
    removed = tidy_paid_assets_root(STATUS / "assets", ver, dry_run=False)
    for r in removed:
        print(f"tidy_stage_removed {r}")
    return staged


def version_dirs_under_paid_root(root: Path) -> list[Path]:
    """Immediate child dirs of a paid_assets (or status assets) root."""
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(root.iterdir()):
        if not p.is_dir():
            continue
        name = p.name
        if name.startswith(".") or name in ("lost+found",):
            continue
        # Version-like dirs (semver) or any non-hidden dir used as pin folders
        out.append(p)
    return out


def stale_paid_asset_version_dirs(
    root: Path, current_version: str
) -> list[Path]:
    """Dirs under *root* that are not the live catalog pin (pure helper)."""
    cur = (current_version or "").strip()
    if not cur:
        return []
    return [p for p in version_dirs_under_paid_root(root) if p.name != cur]


def tidy_paid_assets_root(
    root: Path,
    current_version: str,
    *,
    dry_run: bool = False,
) -> list[str]:
    """Remove non-current version trees so the store only holds the live pin.

    Returns paths removed (or that would be removed when *dry_run*).
    Does not delete *root* itself or files at the root level (e.g. serve script).
    """
    removed: list[str] = []
    for d in stale_paid_asset_version_dirs(root, current_version):
        removed.append(str(d))
        if dry_run:
            continue
        shutil.rmtree(d)
    return removed


# When package-host SSH keys are missing on this machine, admin upload forces
# the operator browser to the public app-testers page (exact product URL).
APP_TESTERS_FORCE_URL = "https://restoreprivacy.online/app-testers"

# Preferred private-key basenames under ``~/.ssh`` when RPT_SSH_KEY is unset.
SSH_KEY_CANDIDATE_NAMES: tuple[str, ...] = (
    "id_ed25519_restore_privacy_eu",  # Helsinki store (current Macs)
    "id_ed25519_20260725",  # Helsinki store (legacy filename)
    "id_ed25519_restore_privacy_vps",  # Iceland residual node
    "id_ed25519_restore_privacy_hop",  # hop peer key (optional)
    "id_ed25519",
    "id_rsa",
)

# Durable dirs probed when status_page runs on Render (HOME often empty).
SSH_KEY_EXTRA_DIR_ENV = "RPT_SSH_KEY_DIR"
SSH_KEY_MATERIAL_ENVS: tuple[str, ...] = (
    "RPT_SSH_PRIVATE_KEY",
    "RPT_SSH_KEY_BODY",
)


def _ssh_search_dirs(
    *,
    env: dict[str, str],
    home: Path | None = None,
) -> list[Path]:
    """Ordered directories that may hold package-host private keys."""
    dirs: list[Path] = []
    key_dir = (env.get(SSH_KEY_EXTRA_DIR_ENV) or "").strip()
    if key_dir:
        dirs.append(Path(key_dir).expanduser())
    # Render payment disk sibling (optional operator-mounted key store).
    pay = (env.get("RPT_PAYMENT_DATA_DIR") or "").strip()
    if pay:
        try:
            dirs.append(Path(pay).expanduser().resolve().parent / "rpt-ssh")
        except OSError:
            pass
    for fixed in ("/var/data/rpt-ssh", "/var/data/ssh"):
        dirs.append(Path(fixed))
    try:
        base_home = home if home is not None else Path.home()
        dirs.append(base_home / ".ssh")
    except (RuntimeError, OSError):
        pass
    # de-dupe while preserving order
    out: list[Path] = []
    seen: set[str] = set()
    for d in dirs:
        key = str(d)
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def materialize_ssh_key_from_env(
    *,
    env: dict[str, str] | None = None,
    home: Path | None = None,
) -> Path | None:
    """If RPT_SSH_PRIVATE_KEY (PEM) is set, write it to a key file and return path.

    Lets the Render status host provision Helsinki package-upload keys via a
    secret without baking the private key into the image. File mode 0o600.
    """
    e = env if env is not None else dict(os.environ)
    material = ""
    for name in SSH_KEY_MATERIAL_ENVS:
        material = (e.get(name) or "").strip()
        if material:
            break
    if not material:
        return None
    # OpenSSH PEMs sometimes arrive with literal \n from dashboard paste.
    if "\\n" in material and "\n" not in material:
        material = material.replace("\\n", "\n")
    if not material.endswith("\n"):
        material += "\n"
    dest_s = (e.get("RPT_SSH_KEY") or "").strip()
    if not dest_s:
        dirs = _ssh_search_dirs(env=e, home=home)
        # Prefer writable durable dir
        base = None
        for d in dirs:
            try:
                d.mkdir(parents=True, exist_ok=True)
                base = d
                break
            except OSError:
                continue
        if base is None:
            try:
                base = (home if home is not None else Path.home()) / ".ssh"
                base.mkdir(parents=True, exist_ok=True)
            except (RuntimeError, OSError):
                return None
        dest_s = str(base / "id_ed25519_restore_privacy_eu")
    dest = Path(dest_s).expanduser()
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.is_file() or dest.read_text(encoding="utf-8") != material:
            dest.write_text(material, encoding="utf-8")
        try:
            os.chmod(dest, 0o600)
        except OSError:
            pass
        if dest.is_file() and dest.stat().st_size > 0:
            return dest
    except OSError:
        return None
    return None


def resolve_ssh_access_key_path(
    *,
    key_env: str = "",
    home: Path | None = None,
    env: dict[str, str] | None = None,
) -> Path | None:
    """Return a usable SSH private key path on this host, or None.

    Probe order:
    1. Materialize from ``RPT_SSH_PRIVATE_KEY`` secret when set
    2. Explicit *key_env* / ``RPT_SSH_KEY`` file path
    3. Candidate basenames under ``RPT_SSH_KEY_DIR``, ``/var/data/rpt-ssh``,
       payment-disk sibling, and ``home/.ssh``
    """
    e = env if env is not None else dict(os.environ)
    materialized = materialize_ssh_key_from_env(env=e, home=home)
    if materialized is not None:
        return materialized
    key = (key_env or e.get("RPT_SSH_KEY") or "").strip()
    if key:
        p = Path(key).expanduser()
        try:
            if p.is_file() and p.stat().st_size > 0:
                return p
        except OSError:
            pass
    for base in _ssh_search_dirs(env=e, home=home):
        for name in SSH_KEY_CANDIDATE_NAMES:
            p = base / name
            try:
                if p.is_file() and p.stat().st_size > 0:
                    return p
            except OSError:
                continue
    return None


def host_ssh_access_keys_present(
    *,
    env: dict[str, str] | None = None,
    home: Path | None = None,
) -> bool:
    """True when this host has package-upload SSH credentials.

    Accepts either a non-empty ``RPT_SSH_PASSWORD`` or a resolvable private key
    file (``RPT_SSH_KEY``, secret material, or a candidate under known dirs).
    """
    e = env if env is not None else dict(os.environ)
    if (e.get("RPT_SSH_PASSWORD") or "").strip():
        return True
    key_path = resolve_ssh_access_key_path(
        key_env=(e.get("RPT_SSH_KEY") or "").strip(),
        home=home,
        env=e,
    )
    return key_path is not None and key_path.is_file()


def ssh_upload_preflight(
    *,
    upload: bool = True,
    env: dict[str, str] | None = None,
    home: Path | None = None,
) -> dict[str, object]:
    """Pre-SSH gate for admin package upload.

    When *upload* is True and host access keys are missing, returns
    ``ok=False``, ``missing_ssh_keys=True``, and ``redirect`` set to
    :data:`APP_TESTERS_FORCE_URL` so the admin UI can force browser navigation.
    Does **not** open SSH. Stage-only / upload-off paths skip the gate.
    """
    if not upload:
        return {
            "ok": True,
            "missing_ssh_keys": False,
            "redirect": "",
            "error": "",
            "key_path": "",
        }
    e = dict(env) if env is not None else dict(os.environ)
    if host_ssh_access_keys_present(env=e, home=home):
        key_path = resolve_ssh_access_key_path(
            key_env=(e.get("RPT_SSH_KEY") or "").strip(),
            home=home,
            env=e,
        )
        return {
            "ok": True,
            "missing_ssh_keys": False,
            "redirect": "",
            "error": "",
            "key_path": str(key_path) if key_path else "",
        }
    return {
        "ok": False,
        "missing_ssh_keys": True,
        "redirect": APP_TESTERS_FORCE_URL,
        "error": (
            "Package host SSH access keys were not found on this machine "
            "(status host process). Live Helsinki upload needs RPT_SSH_KEY "
            "(path), RPT_SSH_PRIVATE_KEY (PEM secret), RPT_SSH_PASSWORD, or a "
            "key under ~/.ssh / RPT_SSH_KEY_DIR / /var/data/rpt-ssh. "
            "Use Dry-run for a key-free plan, or open "
            f"{APP_TESTERS_FORCE_URL} for client installs."
        ),
        "key_path": "",
    }


def _ssh_target() -> tuple[str, str, str | None, Path | None]:
    """Return (host, user, password_or_None, key_path_or_None)."""
    host = os.environ.get("RPT_SSH_HOST", DEFAULT_VPS_ASSET_HOST).strip() or DEFAULT_VPS_ASSET_HOST
    user = os.environ.get("RPT_SSH_USER", "root").strip() or "root"
    password = os.environ.get("RPT_SSH_PASSWORD")
    key = os.environ.get("RPT_SSH_KEY", "").strip()
    key_path = resolve_ssh_access_key_path(key_env=key, env=dict(os.environ))
    if not password and (key_path is None or not key_path.is_file()):
        raise SystemExit(
            "Need RPT_SSH_PASSWORD, RPT_SSH_PRIVATE_KEY, or SSH key path "
            "(RPT_SSH_KEY / ~/.ssh/id_ed25519_restore_privacy_eu / "
            "RPT_SSH_KEY_DIR / /var/data/rpt-ssh). "
            f"If keys are missing, open {APP_TESTERS_FORCE_URL}"
        )
    return host, user, password, key_path


# Iceland residual monopin — node-only; paid installers live on Helsinki.
ICELAND_RESIDUAL_SSH_HOST = "82.221.101.241"
ICELAND_PAID_ASSETS_ROOT = "/opt/restore-privacy/paid_assets"


def remove_iceland_paid_assets(*, dry_run: bool = False) -> int:
    """Stop paid-asset serve on Iceland residual host and delete installer tree.

    Does **not** touch residual node software, keys, or wipe timers — only the
    paid_assets directory and ``rpt-paid-assets`` systemd unit.
    """
    host = (
        os.environ.get("RPT_SSH_HOST", ICELAND_RESIDUAL_SSH_HOST).strip()
        or ICELAND_RESIDUAL_SSH_HOST
    )
    # Force Iceland residual defaults for this op unless operator overrode user/key
    if not os.environ.get("RPT_SSH_HOST", "").strip():
        os.environ["RPT_SSH_HOST"] = ICELAND_RESIDUAL_SSH_HOST
    if not os.environ.get("RPT_SSH_USER", "").strip():
        os.environ["RPT_SSH_USER"] = "raskul"
    if not os.environ.get("RPT_SSH_SUDO", "").strip():
        os.environ["RPT_SSH_SUDO"] = "1"

    remote_root = ICELAND_PAID_ASSETS_ROOT
    unit = UNIT_NAME
    print(f"iceland_cleanup host={host} root={remote_root} unit={unit}")
    if dry_run:
        print("dry-run: would stop/disable unit, remove unit file, rm -rf paid_assets")
        return 0

    host, user, password, key_path = _ssh_target()
    use_openssh = password is None and key_path is not None and _openssh_available()
    script = (
        f"set -e; "
        f"systemctl stop {unit} 2>/dev/null || true; "
        f"systemctl disable {unit} 2>/dev/null || true; "
        f"rm -f /etc/systemd/system/{unit}; "
        f"systemctl daemon-reload 2>/dev/null || true; "
        f"rm -rf {remote_root}; "
        f"echo REMOVED_ROOT; "
        f"test ! -e {remote_root} && echo paid_assets_absent=yes || echo paid_assets_absent=no; "
        f"systemctl is-active {unit} 2>/dev/null || echo unit_inactive; "
        f"ss -lntp 2>/dev/null | grep -E ':8081|:44044' || true; "
        f"pgrep -af 'rpt|node|serve_paid' 2>/dev/null | head -20 || true"
    )
    if use_openssh:
        assert key_path is not None
        code, out = _ssh_run_openssh(
            script, host=host, user=user, key_path=key_path, sudo=True
        )
        print(out)
        if code != 0:
            print(f"ERROR iceland cleanup failed code={code}", file=sys.stderr)
            return 1
        if "paid_assets_absent=yes" not in out and "REMOVED_ROOT" not in out:
            # tolerate partial if tree already gone
            if "paid_assets_absent=no" in out:
                print("ERROR paid_assets still present", file=sys.stderr)
                return 1
        print(f"iceland_cleanup_ok host={host}")
        return 0

    client, host, user = _ssh_connect()
    use_sudo = _want_sudo(user)
    try:
        code, out = _run(client, script, sudo=use_sudo, user=user)
        print(out)
        if code != 0:
            return 1
        print(f"iceland_cleanup_ok host={host}")
        return 0
    finally:
        client.close()


def _ssh_connect():
    try:
        import paramiko
    except ImportError as e:
        raise SystemExit("paramiko required: pip install paramiko") from e

    host, user, password, key_path = _ssh_target()
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kw: dict = {
        "hostname": host,
        "username": user,
        "timeout": 60,
        "banner_timeout": 60,
        "auth_timeout": 60,
        "allow_agent": False,
        "look_for_keys": False,
    }
    if password:
        kw["password"] = password
    else:
        kw["key_filename"] = str(key_path)
        print(f"ssh key={key_path}")
    print(f"connecting {user}@{host} …")
    client.connect(**kw)
    return client, host, user


def _openssh_available() -> bool:
    from shutil import which

    return bool(which("scp") and which("ssh"))


def _scp_put_file(
    local: Path,
    remote: str,
    *,
    host: str,
    user: str,
    key_path: Path | None,
) -> None:
    """Upload one file via OpenSSH scp (more reliable for multi‑MB installers)."""
    import subprocess

    cmd = [
        "scp",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=12",
        "-o",
        "ConnectTimeout=45",
    ]
    if key_path is not None:
        cmd.extend(["-i", str(key_path)])
    cmd.extend([str(local), f"{user}@{host}:{remote}"])
    print(f"$ scp {local.name} -> {user}@{host}:{remote}")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"scp failed code={proc.returncode}: {msg}")


def _want_sudo(user: str, *, force: bool = False) -> bool:
    if force:
        return True
    return os.environ.get("RPT_SSH_SUDO", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ) or user != "root"


def _run(client, cmd: str, *, sudo: bool, user: str) -> tuple[int, str]:
    use_sudo = _want_sudo(user, force=sudo)
    if use_sudo and not cmd.strip().startswith("sudo "):
        # Run the whole pipeline as root via bash -lc
        import shlex

        cmd = f"sudo -n bash -lc {shlex.quote(cmd)}"
    print(f"$ {cmd}")
    _, stdout, stderr = client.exec_command(cmd, timeout=600)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out, end="" if out.endswith("\n") else "\n")
    if err:
        print(err, end="" if err.endswith("\n") else "\n", file=sys.stderr)
    return code, out + err


def _ssh_run_openssh(
    cmd: str,
    *,
    host: str,
    user: str,
    key_path: Path,
    sudo: bool = False,
) -> tuple[int, str]:
    """Run a remote shell command via OpenSSH (fresh connection each call)."""
    import shlex
    import subprocess

    if sudo or _want_sudo(user):
        remote = f"sudo -n bash -lc {shlex.quote(cmd)}"
    else:
        remote = f"bash -lc {shlex.quote(cmd)}"
    argv = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ConnectTimeout=45",
        "-i",
        str(key_path),
        f"{user}@{host}",
        remote,
    ]
    print(f"$ ssh {user}@{host} {remote[:120]}{'…' if len(remote) > 120 else ''}")
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=600)
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr:
        print(proc.stderr, end="" if proc.stderr.endswith("\n") else "\n", file=sys.stderr)
    return proc.returncode, out


def _remote_size_openssh(
    remote_path: str,
    *,
    host: str,
    user: str,
    key_path: Path,
) -> int | None:
    code, out = _ssh_run_openssh(
        f"if test -f {remote_path}; then stat -c%s {remote_path}; else echo MISSING; fi",
        host=host,
        user=user,
        key_path=key_path,
        sudo=True,
    )
    if code != 0:
        return None
    for line in (out or "").splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return None


def _upload_one_installer_openssh(
    local: Path,
    remote_final: str,
    *,
    host: str,
    user: str,
    key_path: Path,
    skip_if_present: bool = True,
) -> None:
    """Upload one installer with OpenSSH scp + size verify (fresh connections)."""
    expected = local.stat().st_size
    if skip_if_present:
        existing = _remote_size_openssh(
            remote_final, host=host, user=user, key_path=key_path
        )
        if existing == expected:
            print(f"  skip (already on VPS) {local.name} bytes={expected}")
            return
    # Absolute home path (tilde breaks under sudo bash -lc).
    home = "/root" if user == "root" else f"/home/{user}"
    home_tmp = f"{home}/rpt-paid-upload-{local.name}"
    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            print(
                f"  scp attempt {attempt}: {local.name} ({expected} bytes) "
                f"-> {user}@{host}:{home_tmp}"
            )
            _scp_put_file(
                local, home_tmp, host=host, user=user, key_path=key_path
            )
            # Verify as user first (file is owned by scp user), then root-move to /opt.
            code, out = _ssh_run_openssh(
                f"set -e; "
                f"test -f {home_tmp}; "
                f"SZ=$(stat -c%s {home_tmp}); "
                f"test \"$SZ\" -eq {expected}; "
                f"echo size_ok=$SZ",
                host=host,
                user=user,
                key_path=key_path,
                sudo=False,
            )
            if code != 0:
                raise RuntimeError(f"size verify failed code={code}: {out}")
            code, out = _ssh_run_openssh(
                f"set -e; "
                f"mkdir -p $(dirname {remote_final}); "
                f"mv -f {home_tmp} {remote_final}; "
                f"chmod 644 {remote_final}; "
                f"chown root:root {remote_final} || true; "
                f"stat -c%s {remote_final}",
                host=host,
                user=user,
                key_path=key_path,
                sudo=True,
            )
            if code != 0:
                raise RuntimeError(f"remote install failed code={code}: {out}")
            print(f"  remote_ok {local.name} bytes={expected}")
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"  upload attempt {attempt} failed: {e}", file=sys.stderr)
            try:
                _ssh_run_openssh(
                    f"rm -f {home_tmp}",
                    host=host,
                    user=user,
                    key_path=key_path,
                    sudo=False,
                )
            except Exception:  # noqa: BLE001
                pass
    raise RuntimeError(f"upload failed after retries: {local.name}: {last_err}")


def _sync_remote_catalog_version(
    ver: str,
    *,
    host: str,
    user: str,
    key_path: Path,
) -> None:
    """Patch RPT_CATALOG_VERSION on rpt-paid-assets.service and restart if unit exists.

    Upload without ``--install-serve`` used to leave a stale pin (e.g. 0.5.5) while
    packages only lived under ``paid_assets/0.5.6/`` — serve then 404'd every paid
    download. Preserve token/bind/port; only bump the pin.
    """
    ver = (ver or "").strip()
    if not ver:
        return
    unit_path = f"/etc/systemd/system/{UNIT_NAME}"
    # sed in-place if key present; else append Environment= under [Service]
    script = (
        f"set -e; "
        f"U={unit_path}; "
        f"test -f \"$U\" || {{ echo no_unit; exit 0; }}; "
        f"if grep -q '^Environment=RPT_CATALOG_VERSION=' \"$U\"; then "
        f"  sed -i 's/^Environment=RPT_CATALOG_VERSION=.*/Environment=RPT_CATALOG_VERSION={ver}/' \"$U\"; "
        f"else "
        f"  sed -i '/^\\[Service\\]/a Environment=RPT_CATALOG_VERSION={ver}' \"$U\"; "
        f"fi; "
        f"systemctl daemon-reload; "
        f"systemctl restart {UNIT_NAME}; "
        f"systemctl is-active {UNIT_NAME}; "
        f"echo catalog_pin={ver}"
    )
    code, out = _ssh_run_openssh(
        script, host=host, user=user, key_path=key_path, sudo=True
    )
    if out:
        print(out.strip())
    if code != 0:
        print(
            f"WARN: could not sync RPT_CATALOG_VERSION={ver} on host "
            f"(paid downloads may 404 until --install-serve-only): {out}",
            file=sys.stderr,
        )


def install_serve_only(
    *,
    version: str | None = None,
) -> int:
    """Install/restart token-gated HTTP serve without re-uploading packages."""
    host, user, password, key_path = _ssh_target()
    if password is not None or key_path is None or not _openssh_available():
        print("install-serve-only requires OpenSSH key auth", file=sys.stderr)
        return 1
    remote_root = os.environ.get(
        "RPT_VPS_ASSET_REMOTE_ROOT", DEFAULT_VPS_ASSET_REMOTE_ROOT
    ).strip() or DEFAULT_VPS_ASSET_REMOTE_ROOT
    ver = (version or RELEASE_VERSION).strip()
    # Verify at least one package exists remotely
    sample = list_packages(ver)[0]
    remote_sample = f"{remote_root.rstrip('/')}/{ver}/{sample['filename']}"
    sz = _remote_size_openssh(
        remote_sample, host=host, user=user, key_path=key_path
    )
    if not sz or sz < 1_000_000:
        print(
            f"ERROR: remote packages missing under {remote_root}/{ver}/ "
            f"(run --upload first). sample={remote_sample} size={sz}",
            file=sys.stderr,
        )
        return 1
    if not SERVE_SCRIPT_LOCAL.is_file():
        print(f"missing {SERVE_SCRIPT_LOCAL}", file=sys.stderr)
        return 1
    home = "/root" if user == "root" else f"/home/{user}"
    tmp_serve = f"{home}/serve_paid_assets.py"
    _scp_put_file(
        SERVE_SCRIPT_LOCAL, tmp_serve, host=host, user=user, key_path=key_path
    )
    token = os.environ.get("RPT_ASSET_FETCH_TOKEN", "").strip()
    if not token:
        # Prefer monorepo secrets (same value Render already holds) over a new random.
        for cand in (
            ROOT / "secrets" / "rpt_asset_fetch_token",
            ROOT / "secrets" / "RPT_ASSET_FETCH_TOKEN",
        ):
            try:
                if cand.is_file():
                    token = cand.read_text(encoding="utf-8").strip()
                    if token:
                        print(f"using asset token from {cand.relative_to(ROOT)}")
                        break
            except OSError:
                continue
    if not token and key_path is not None:
        # Preserve token already installed on the unit (avoid breaking Render).
        code, out = _ssh_run_openssh(
            "grep -E '^Environment=RPT_ASSET_FETCH_TOKEN=' "
            "/etc/systemd/system/rpt-paid-assets.service 2>/dev/null "
            "| head -1 | sed 's/^[^=]*=[^=]*=//'",
            host=host,
            user=user,
            key_path=key_path,
            sudo=False,
        )
        if code == 0 and (out or "").strip():
            token = out.strip().splitlines()[0].strip()
            print("preserving existing host RPT_ASSET_FETCH_TOKEN")
    if not token:
        token = secrets.token_urlsafe(32)
        print(
            f"generated RPT_ASSET_FETCH_TOKEN (set on Render too): {token}",
            file=sys.stderr,
        )
    port = os.environ.get(
        "RPT_VPS_ASSET_PORT", str(DEFAULT_SERVE_BACKEND_PORT)
    ).strip()
    bind = os.environ.get(
        "RPT_VPS_ASSET_BIND", DEFAULT_SERVE_BACKEND_BIND
    ).strip() or DEFAULT_SERVE_BACKEND_BIND
    bc_root = os.environ.get(
        "RPT_BREADCRUMBS_REMOTE_ROOT", DEFAULT_BREADCRUMBS_REMOTE_ROOT
    ).strip() or DEFAULT_BREADCRUMBS_REMOTE_ROOT
    unit = f"""[Unit]
Description=Restore Privacy paid asset server (token-gated)
After=network.target

[Service]
Type=simple
Environment=RPT_ASSET_FETCH_TOKEN={token}
Environment=RPT_VPS_ASSET_REMOTE_ROOT={remote_root}
Environment=RPT_VPS_ASSET_PORT={port}
Environment=RPT_VPS_ASSET_BIND={bind}
Environment=RPT_BREADCRUMBS_REMOTE_ROOT={bc_root}
Environment=RPT_CATALOG_VERSION={ver}
ExecStart=/usr/bin/python3 {SERVE_SCRIPT_REMOTE}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    import base64

    # Drop non-current version trees before (re)starting serve
    tidy_remote = (
        f"set -e; "
        f"for d in {remote_root}/*; do "
        f"[ -d \"$d\" ] || continue; "
        f"bn=$(basename \"$d\"); "
        f"[ \"$bn\" = '{ver}' ] && continue; "
        f"rm -rf \"$d\"; echo tidy_removed=$bn; "
        f"done"
    )
    _tc, tout = _ssh_run_openssh(
        tidy_remote, host=host, user=user, key_path=key_path, sudo=True
    )
    if tout:
        print(tout)

    b64 = base64.b64encode(unit.encode("utf-8")).decode("ascii")
    code, out = _ssh_run_openssh(
        f"set -e; "
        f"mv -f {tmp_serve} {SERVE_SCRIPT_REMOTE}; "
        f"chmod +x {SERVE_SCRIPT_REMOTE}; "
        f"echo {b64} | base64 -d > /tmp/{UNIT_NAME}; "
        f"mv /tmp/{UNIT_NAME} /etc/systemd/system/{UNIT_NAME}; "
        f"systemctl daemon-reload; "
        f"systemctl enable {UNIT_NAME}; "
        f"systemctl restart {UNIT_NAME}; "
        f"systemctl is-active {UNIT_NAME}",
        host=host,
        user=user,
        key_path=key_path,
        sudo=True,
    )
    if code != 0:
        print(f"ERROR install-serve failed: {out}", file=sys.stderr)
        return 1
    print(f"serve: http://{host}:{port}{VPS_ASSET_HTTP_PREFIX}/{{version}}/{{file}}")
    print("Render env: RPT_VPS_ASSET_BASE + RPT_ASSET_FETCH_TOKEN")
    print(f"token_len={len(token)}")
    print(f"install-serve complete host={host} version={ver}")
    return 0


def upload_packages(
    *,
    version: str | None = None,
    dry_run: bool = False,
    install_serve: bool = False,
    force: bool = False,
    allow_missing: bool = False,
) -> int:
    pkgs = list_packages(version)
    ver = pkgs[0]["version"]
    local_dir = STATUS / "assets" / ver
    remote_root = os.environ.get(
        "RPT_VPS_ASSET_REMOTE_ROOT", DEFAULT_VPS_ASSET_REMOTE_ROOT
    ).strip() or DEFAULT_VPS_ASSET_REMOTE_ROOT
    remote_ver = f"{remote_root.rstrip('/')}/{ver}"
    host_default = DEFAULT_VPS_ASSET_HOST

    present: list[dict[str, str]] = []
    for p in pkgs:
        f = local_dir / p["filename"]
        if f.is_file() and f.stat().st_size >= 1_000_000:
            present.append(p)
        elif allow_missing:
            print(
                f"skip_missing upload platform={p['platform']} file={p['filename']}"
            )
        else:
            print(f"missing or tiny local stage: {f}", file=sys.stderr)
            print("Run with --stage first (or --allow-missing).", file=sys.stderr)
            return 1

    if not present:
        print("ERROR: no staged packages to upload", file=sys.stderr)
        return 1

    print(f"upload plan: {len(present)}/{len(pkgs)} files -> {host_default}:{remote_ver}/")
    for p in present:
        print(f"  {p['platform']}: {p['filename']}")

    if dry_run:
        print("dry-run: no SSH")
        return 0

    for p in present:
        f = local_dir / p["filename"]
        if p["platform"] == "macos":
            try:
                _assert_macos_cfbundle(f, ver)
            except (RuntimeError, FileNotFoundError, ValueError) as e:
                print(f"ERROR: {e}", file=sys.stderr)
                return 1

    host, user, password, key_path = _ssh_target()
    use_openssh = (
        password is None and key_path is not None and _openssh_available()
    )

    if use_openssh:
        assert key_path is not None
        print(f"transport=openssh key={key_path}")
        code, _ = _ssh_run_openssh(
            f"mkdir -p {remote_ver} && chown -R {user}:{user} {remote_root}",
            host=host,
            user=user,
            key_path=key_path,
            sudo=True,
        )
        if code != 0:
            print("ERROR: could not prepare remote paid_assets dir", file=sys.stderr)
            return 1
        for p in present:
            local = local_dir / p["filename"]
            remote = f"{remote_ver}/{p['filename']}"
            print(
                f"upload platform={p['platform']} file={p['filename']} "
                f"({local.stat().st_size} bytes)"
            )
            try:
                _upload_one_installer_openssh(
                    local,
                    remote,
                    host=host,
                    user=user,
                    key_path=key_path,
                    skip_if_present=not force,
                )
            except Exception as e:  # noqa: BLE001
                print(f"ERROR platform={p['platform']}: {e}", file=sys.stderr)
                return 1
        if install_serve:
            if not SERVE_SCRIPT_LOCAL.is_file():
                print(f"missing {SERVE_SCRIPT_LOCAL}", file=sys.stderr)
                return 1
            home = "/root" if user == "root" else f"/home/{user}"
            tmp_serve = f"{home}/serve_paid_assets.py"
            _scp_put_file(
                SERVE_SCRIPT_LOCAL,
                tmp_serve,
                host=host,
                user=user,
                key_path=key_path,
            )
            token = os.environ.get("RPT_ASSET_FETCH_TOKEN", "").strip()
            if not token:
                for cand in (
                    ROOT / "secrets" / "rpt_asset_fetch_token",
                    ROOT / "secrets" / "RPT_ASSET_FETCH_TOKEN",
                ):
                    try:
                        if cand.is_file():
                            token = cand.read_text(encoding="utf-8").strip()
                            if token:
                                break
                    except OSError:
                        continue
            if not token:
                code_t, out_t = _ssh_run_openssh(
                    "grep -E '^Environment=RPT_ASSET_FETCH_TOKEN=' "
                    "/etc/systemd/system/rpt-paid-assets.service 2>/dev/null "
                    "| head -1 | sed 's/^[^=]*=[^=]*=//'",
                    host=host,
                    user=user,
                    key_path=key_path,
                    sudo=False,
                )
                if code_t == 0 and (out_t or "").strip():
                    token = out_t.strip().splitlines()[0].strip()
            if not token:
                token = secrets.token_urlsafe(32)
                print(
                    f"generated RPT_ASSET_FETCH_TOKEN (set on Render too): {token}",
                    file=sys.stderr,
                )
            port = os.environ.get(
                "RPT_VPS_ASSET_PORT", str(DEFAULT_SERVE_BACKEND_PORT)
            ).strip()
            bind = os.environ.get(
                "RPT_VPS_ASSET_BIND", DEFAULT_SERVE_BACKEND_BIND
            ).strip() or DEFAULT_SERVE_BACKEND_BIND
            bc_root = os.environ.get(
                "RPT_BREADCRUMBS_REMOTE_ROOT", DEFAULT_BREADCRUMBS_REMOTE_ROOT
            ).strip() or DEFAULT_BREADCRUMBS_REMOTE_ROOT
            unit = f"""[Unit]
Description=Restore Privacy paid asset server (token-gated)
After=network.target

[Service]
Type=simple
Environment=RPT_ASSET_FETCH_TOKEN={token}
Environment=RPT_VPS_ASSET_REMOTE_ROOT={remote_root}
Environment=RPT_VPS_ASSET_PORT={port}
Environment=RPT_VPS_ASSET_BIND={bind}
Environment=RPT_BREADCRUMBS_REMOTE_ROOT={bc_root}
Environment=RPT_CATALOG_VERSION={ver}
ExecStart=/usr/bin/python3 {SERVE_SCRIPT_REMOTE}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
            import base64

            b64 = base64.b64encode(unit.encode("utf-8")).decode("ascii")
            tidy_remote = (
                f"set -e; "
                f"for d in {remote_root}/*; do "
                f"[ -d \"$d\" ] || continue; "
                f"bn=$(basename \"$d\"); "
                f"[ \"$bn\" = '{ver}' ] && continue; "
                f"rm -rf \"$d\"; echo tidy_removed=$bn; "
                f"done"
            )
            _tc, tout = _ssh_run_openssh(
                tidy_remote,
                host=host,
                user=user,
                key_path=key_path,
                sudo=True,
            )
            if tout:
                print(tout)
            code, out = _ssh_run_openssh(
                f"set -e; "
                f"mv -f {tmp_serve} {SERVE_SCRIPT_REMOTE}; "
                f"chmod +x {SERVE_SCRIPT_REMOTE}; "
                f"echo {b64} | base64 -d > /tmp/{UNIT_NAME}; "
                f"mv /tmp/{UNIT_NAME} /etc/systemd/system/{UNIT_NAME}; "
                f"systemctl daemon-reload; "
                f"systemctl enable {UNIT_NAME}; "
                f"systemctl restart {UNIT_NAME}; "
                f"systemctl is-active {UNIT_NAME}",
                host=host,
                user=user,
                key_path=key_path,
                sudo=True,
            )
            if code != 0:
                print(f"ERROR install-serve failed: {out}", file=sys.stderr)
                return 1
            print(
                f"serve: http://{host}:{port}{VPS_ASSET_HTTP_PREFIX}/{{version}}/{{file}}"
            )
            print("Render env: RPT_VPS_ASSET_BASE + RPT_ASSET_FETCH_TOKEN")
            print(f"token_len={len(token)}")
        else:
            # Packages uploaded without unit rewrite — still drop old pin trees
            tidy_remote = (
                f"set -e; "
                f"for d in {remote_root}/*; do "
                f"[ -d \"$d\" ] || continue; "
                f"bn=$(basename \"$d\"); "
                f"[ \"$bn\" = '{ver}' ] && continue; "
                f"rm -rf \"$d\"; echo tidy_removed=$bn; "
                f"done"
            )
            _tc, tout = _ssh_run_openssh(
                tidy_remote,
                host=host,
                user=user,
                key_path=key_path,
                sudo=True,
            )
            if tout:
                print(tout)
            # Keep token-gated serve pin in sync with monopin (avoids 404 when
            # packages are under paid_assets/{ver}/ but unit still has old pin).
            _sync_remote_catalog_version(
                ver, host=host, user=user, key_path=key_path
            )
        print(f"upload complete host={host} version={ver}")
        return 0

    # Password / paramiko fallback path
    client, host, user = _ssh_connect()
    use_sudo = _want_sudo(user)
    try:
        _run(client, f"mkdir -p {remote_ver}", sudo=use_sudo, user=user)
        if use_sudo:
            _run(
                client,
                f"chown -R {user}:{user} {remote_root}",
                sudo=True,
                user=user,
            )
        for p in present:
            local = local_dir / p["filename"]
            remote = f"{remote_ver}/{p['filename']}"
            print(
                f"upload platform={p['platform']} file={p['filename']} "
                f"({local.stat().st_size} bytes)"
            )
            sftp = client.open_sftp()
            try:
                sftp.put(str(local), remote)
                st = sftp.stat(remote)
                if st.st_size != local.stat().st_size:
                    print(
                        f"ERROR size mismatch remote={st.st_size} local={local.stat().st_size}",
                        file=sys.stderr,
                    )
                    return 1
                print(f"  remote_ok {p['platform']} bytes={st.st_size}")
            finally:
                sftp.close()
        if install_serve:
            print(
                "install-serve requires OpenSSH key path in this build; "
                "re-run with RPT_SSH_KEY set",
                file=sys.stderr,
            )
            return 1
        print(f"upload complete host={host} version={ver}")
        return 0
    finally:
        client.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Stage per-device installers and host them on the Helsinki paid store "
            "(not the Iceland residual node)"
        )
    )
    ap.add_argument(
        "--version",
        default="",
        help=f"Catalog version (default: shipped RELEASE_VERSION={RELEASE_VERSION})",
    )
    ap.add_argument(
        "--list",
        action="store_true",
        help="Print version + five platform filenames (no stage/upload)",
    )
    ap.add_argument(
        "--stage",
        action="store_true",
        help="Copy each platform package into status_page/assets/{version}/",
    )
    ap.add_argument(
        "--upload",
        action="store_true",
        help="Upload staged packages to Helsinki paid_assets path",
    )
    ap.add_argument(
        "--install-serve",
        action="store_true",
        help="Install/restart token-gated HTTP serve on store host (with --upload)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="With --upload or --remove-iceland-paid-assets: print plan only (no SSH)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Re-upload even when remote size already matches local",
    )
    ap.add_argument(
        "--allow-missing",
        action="store_true",
        help=(
            "Stage/upload only packages present locally (skip missing platforms). "
            "Use when Apple zips await Mac seal under the same monopin."
        ),
    )
    ap.add_argument(
        "--install-serve-only",
        action="store_true",
        help="Only install/restart the token-gated store HTTP serve (no package upload)",
    )
    ap.add_argument(
        "--remove-iceland-paid-assets",
        action="store_true",
        help=(
            "On Iceland residual host: stop/disable rpt-paid-assets and delete "
            "/opt/restore-privacy/paid_assets only (node-only cleanup)"
        ),
    )
    args = ap.parse_args(argv)
    ver = (args.version or "").strip() or None

    if args.remove_iceland_paid_assets:
        return remove_iceland_paid_assets(dry_run=args.dry_run)

    if args.install_serve_only:
        return install_serve_only(version=ver)

    if args.list or not (args.stage or args.upload):
        print_catalog(ver)
        if not (args.stage or args.upload):
            return 0

    if args.stage:
        try:
            stage_packages(version=ver, allow_missing=args.allow_missing)
        except (FileNotFoundError, RuntimeError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        # Sanity: catalog filenames match staged (full set unless allow_missing)
        pkgs = list_packages(ver)
        names = {p["filename"] for p in pkgs}
        if (
            not args.allow_missing
            and names != set(catalog_filenames())
            and (ver is None or ver == RELEASE_VERSION)
        ):
            # only enforce exact catalog set for current RELEASE_VERSION
            missing = set(catalog_filenames()) - names
            if missing:
                print(f"ERROR catalog mismatch missing={missing}", file=sys.stderr)
                return 1

    if args.upload:
        return upload_packages(
            version=ver,
            dry_run=args.dry_run,
            install_serve=args.install_serve,
            force=args.force,
            allow_missing=args.allow_missing,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
