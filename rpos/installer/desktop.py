"""Place Pens · Tables · Slides launchers on the user Desktop after install."""

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
    """OS user Desktop directory (product default for immediate discovery)."""
    home = Path.home()
    xdg = os.environ.get("XDG_DESKTOP_DIR", "").strip()
    if xdg:
        return Path(xdg).expanduser()
    for name in ("Desktop", "desktop"):
        p = home / name
        if p.is_dir():
            return p
    return home / "Desktop"


def prefix_desktop_dir(prefix: Path) -> Path:
    """Staged Desktop under install prefix (always written for packages/tests)."""
    return Path(prefix) / "Desktop"


def _write_launchers_to(
    desktop: Path,
    *,
    apps_root: Path,
    is_win: bool,
) -> list[dict[str, str]]:
    desktop.mkdir(parents=True, exist_ok=True)
    created: list[dict[str, str]] = []
    for spec in APP_SPECS:
        if is_win:
            path = desktop / spec["win_name"]
            path.write_text(
                _win_launcher(spec["module"], spec["brand"], apps_root),
                encoding="utf-8",
            )
        else:
            path = desktop / spec["unix_name"]
            path.write_text(
                _unix_launcher(spec["module"], spec["brand"], apps_root),
                encoding="utf-8",
            )
            path.chmod(
                path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            )
        created.append({"brand": spec["brand"], "path": str(path)})
    return created


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
    also_user_desktop: bool = True,
) -> dict[str, Any]:
    """Write Pens / Tables / Slides launchers to Desktop location(s).

    Always stages under ``{prefix}/Desktop``.
    By default **also** writes to the real user Desktop
    (:func:`default_desktop_dir`) so apps appear immediately after install.

    Tests inject *desktop_root* (used as the sole target instead of the live
    user Desktop) while still writing prefix/Desktop.
    """
    prefix = Path(prefix)
    root = Path(apps_root) if apps_root else (prefix / "apps")
    if not root.is_dir():
        alt = prefix / "rpos" / "apps"
        if alt.is_dir():
            root = alt

    is_win = sys.platform.startswith("win")
    staged = prefix_desktop_dir(prefix)
    created_staged = _write_launchers_to(staged, apps_root=root, is_win=is_win)

    user_desktop: Path | None = None
    created_user: list[dict[str, str]] = []
    if desktop_root is not None:
        # Test / operator override: treat as the "user" desktop surface
        user_desktop = Path(desktop_root)
        created_user = _write_launchers_to(
            user_desktop, apps_root=root, is_win=is_win
        )
    elif also_user_desktop:
        user_desktop = default_desktop_dir()
        try:
            created_user = _write_launchers_to(
                user_desktop, apps_root=root, is_win=is_win
            )
        except OSError:
            # Sandbox / missing Desktop dir — prefix Desktop still holds launchers
            created_user = []

    # Primary discoverable path for product claims: user desktop when available
    primary = user_desktop if (user_desktop and created_user) else staged
    all_created = created_user or created_staged
    man = {
        "desktop": str(primary),
        "prefix_desktop": str(staged),
        "user_desktop": str(user_desktop) if user_desktop else None,
        "apps": all_created,
        "apps_prefix_desktop": created_staged,
        "apps_user_desktop": created_user,
        "free_with_rpos": True,
        "brands": [s["brand"] for s in APP_SPECS],
    }
    man_path = prefix / "DESKTOP_APPS.json"
    man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    return man


def assert_desktop_has_all_three(desktop: Path) -> bool:
    if not Path(desktop).is_dir():
        return False
    names = {p.name for p in Path(desktop).iterdir()}
    need_u = {"Pens", "Tables", "Slides"}
    need_w = {"Pens.cmd", "Tables.cmd", "Slides.cmd"}
    return need_u.issubset(names) or need_w.issubset(names)
