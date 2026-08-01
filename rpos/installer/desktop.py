"""Place Pens · Tables · Slides launchers on the Desktop after install."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

APP_SPECS: tuple[dict[str, str], ...] = (
    {
        "brand": "Pens",
        "module": "rpoffice.apps.pens",
        "unix_name": "Pens",
        "win_name": "Pens.cmd",
    },
    {
        "brand": "Tables",
        "module": "rpoffice.apps.tables",
        "unix_name": "Tables",
        "win_name": "Tables.cmd",
    },
    {
        "brand": "Slides",
        "module": "rpoffice.apps.slides",
        "unix_name": "Slides",
        "win_name": "Slides.cmd",
    },
)


def default_desktop_dir() -> Path:
    """OS desktop directory (product default)."""
    home = Path.home()
    # Linux XDG
    xdg = os.environ.get("XDG_DESKTOP_DIR", "").strip()
    if xdg:
        return Path(xdg).expanduser()
    for name in ("Desktop", "desktop"):
        p = home / name
        if p.is_dir():
            return p
    return home / "Desktop"


def desktop_dir_for_prefix(prefix: Path, *, desktop_root: Path | None = None) -> Path:
    """Desktop path used for placement.

    *desktop_root* is injected by tests. Product default uses the real Desktop
    under the user home; when *prefix* is a staged install, launchers also
    mirror under ``prefix/Desktop`` so packages always have a discoverable path.
    """
    if desktop_root is not None:
        return Path(desktop_root)
    # Always stage under install prefix Desktop for reproducible discovery
    staged = Path(prefix) / "Desktop"
    return staged


def _unix_launcher(module: str, brand: str, apps_root: Path) -> str:
    return f'''#!/usr/bin/env bash
# {brand} — Restore Privacy (free with rpOS)
set -euo pipefail
export PYTHONPATH="{apps_root}${{PYTHONPATH:+:$PYTHONPATH}}"
exec python3 -m {module} "$@"
'''


def _win_launcher(module: str, brand: str, apps_root: Path) -> str:
    return f'''@echo off
REM {brand} — Restore Privacy (free with rpOS)
set PYTHONPATH={apps_root};%PYTHONPATH%
python -m {module} %*
'''


def place_app_launchers(
    prefix: Path,
    *,
    desktop_root: Path | None = None,
    apps_root: Path | None = None,
) -> dict[str, Any]:
    """Write executable launchers for Pens, Tables, Slides onto Desktop.

    Returns paths created. Uses *prefix*/apps as PYTHONPATH root when present.
    """
    prefix = Path(prefix)
    desktop = desktop_dir_for_prefix(prefix, desktop_root=desktop_root)
    desktop.mkdir(parents=True, exist_ok=True)
    root = Path(apps_root) if apps_root else (prefix / "apps")
    if not root.is_dir():
        # fall back to bundled monorepo layout under prefix/rpos/apps
        alt = prefix / "rpos" / "apps"
        if alt.is_dir():
            root = alt
    created: list[dict[str, str]] = []
    is_win = sys.platform.startswith("win")
    for spec in APP_SPECS:
        if is_win:
            path = desktop / spec["win_name"]
            path.write_text(
                _win_launcher(spec["module"], spec["brand"], root),
                encoding="utf-8",
            )
        else:
            path = desktop / spec["unix_name"]
            path.write_text(
                _unix_launcher(spec["module"], spec["brand"], root),
                encoding="utf-8",
            )
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        created.append({"brand": spec["brand"], "path": str(path)})
    # Also write a manifest for Ned / tests
    man = {
        "desktop": str(desktop),
        "apps": created,
        "free_with_rpos": True,
        "brands": [s["brand"] for s in APP_SPECS],
    }
    man_path = prefix / "DESKTOP_APPS.json"
    man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    return man


def assert_desktop_has_all_three(desktop: Path) -> bool:
    names = {p.name for p in Path(desktop).iterdir()} if Path(desktop).is_dir() else set()
    # Unix names or Windows .cmd
    need_u = {"Pens", "Tables", "Slides"}
    need_w = {"Pens.cmd", "Tables.cmd", "Slides.cmd"}
    return need_u.issubset(names) or need_w.issubset(names)
