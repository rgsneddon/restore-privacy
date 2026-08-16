#!/usr/bin/env python3
"""Catalog macOS zip: signed app plus install-to-Applications wrapper.

Opening ``restore_privacy_client.app`` from inside the zip (Safari auto-extract
or Archive Utility) launches a translocated copy under ``/var/folders``. After
a crash, Launch Services cannot find that path — Gatekeeper Reopen says the
file cannot be found. Users must copy the app to ``/Applications`` first.

This packager does **not** modify the ``.app`` (seal stays intact).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

FOLDER_NAME = "Restore Privacy"
APP_NAME = "restore_privacy_client.app"
INSTALL_COMMAND_NAME = "Install Restore Privacy.command"
HOWTO_NAME = "How to Install.txt"
APPLICATIONS_LINK_NAME = "Applications"


def install_command_text() -> str:
    """Shell installer: ditto the sibling app into /Applications and open it."""
    return """#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="$HERE/restore_privacy_client.app"
DEST="/Applications/restore_privacy_client.app"
if [[ ! -d "$APP" ]]; then
  /usr/bin/osascript -e 'display alert "Restore Privacy" message "restore_privacy_client.app is missing next to this installer. Unzip the download completely, then run Install Restore Privacy from inside the Restore Privacy folder." as critical' >/dev/null || true
  echo "restore_privacy_client.app not found next to this installer" >&2
  exit 1
fi
if [[ -e "$DEST" ]]; then
  rm -rf "$DEST"
fi
/usr/bin/ditto "$APP" "$DEST"
/usr/bin/xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true
/usr/bin/open "$DEST"
"""


def how_to_install_text() -> str:
    """User-facing steps. Do not open the app from inside the zip."""
    return """Install Restore Privacy (macOS)

1. Unzip this archive (double-click the .zip if Safari did not already).
2. Open the Restore Privacy folder.
3. Drag restore_privacy_client.app onto the Applications shortcut
   — or double-click Install Restore Privacy.
4. Open Restore Privacy from Applications / Launchpad.

Do not open the app from inside the zip or from a Downloads extract.
macOS then launches a temporary copy. If that copy quits, Reopen says
the file cannot be found.

First launch: if macOS asks, click Open (Developer ID, notarized).
Allow the Network system extension when asked, then tap Connect.
"""


def find_catalog_app(root: Path) -> Path | None:
    """Host ``restore_privacy_client.app`` under *root* (skip nested appex)."""
    hits = [
        p
        for p in root.rglob(APP_NAME)
        if p.is_dir() and (p / "Contents" / "MacOS").is_dir()
    ]
    if not hits:
        return None
    for p in hits:
        if "PacketTunnel" not in p.name:
            return p
    return hits[0]


def package_macos_catalog_zip(app: Path, dest: Path) -> Path:
    """ditto-zip *app* plus install wrapper. Does not rewrite the bundle."""
    app = Path(app)
    dest = Path(dest)
    if not app.is_dir() or app.suffix != ".app":
        raise FileNotFoundError(f"macOS app bundle missing: {app}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    with tempfile.TemporaryDirectory(prefix="rpt_macos_catalog_") as td:
        folder = Path(td) / FOLDER_NAME
        folder.mkdir()
        staged = folder / APP_NAME
        shutil.copytree(app, staged, symlinks=True)
        cmd = folder / INSTALL_COMMAND_NAME
        cmd.write_text(install_command_text(), encoding="utf-8")
        os.chmod(cmd, 0o755)
        (folder / HOWTO_NAME).write_text(how_to_install_text(), encoding="utf-8")
        os.symlink("/Applications", folder / APPLICATIONS_LINK_NAME)
        subprocess.check_call(
            [
                "ditto",
                "-c",
                "-k",
                "--sequesterRsrc",
                "--keepParent",
                str(folder),
                str(dest),
            ]
        )
    return dest


def repackage_existing_macos_zip(src_zip: Path, dest: Path) -> Path:
    """Rebuild a catalog zip from an existing sealed zip (app bytes unchanged)."""
    src_zip = Path(src_zip)
    dest = Path(dest)
    if not src_zip.is_file():
        raise FileNotFoundError(f"macos zip missing: {src_zip}")
    with tempfile.TemporaryDirectory(prefix="rpt_macos_repack_") as td:
        root = Path(td)
        subprocess.check_call(["ditto", "-x", "-k", str(src_zip), str(root)])
        app = find_catalog_app(root)
        if app is None:
            raise FileNotFoundError(f"no {APP_NAME} inside {src_zip}")
        return package_macos_catalog_zip(app, dest)


def zip_has_install_wrapper(path: Path) -> bool:
    """True when the catalog zip ships the Applications installer files."""
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
    has_app = any(n.endswith(f"{APP_NAME}/Contents/Info.plist") for n in names)
    has_cmd = any(n.endswith(INSTALL_COMMAND_NAME) for n in names)
    has_how = any(n.endswith(HOWTO_NAME) for n in names)
    return has_app and has_cmd and has_how
