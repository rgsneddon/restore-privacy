"""RESTORE pipeline: advisories → gate → wipe-intent → install foundation."""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .advisories import advisory_text_blob
from .gate import evaluate_confirmation
from .desktop import place_app_launchers
from .wipe_adapter import WipeAdapter, default_wipe_adapter


@dataclass
class RestorePipeline:
    """Single-click RESTORE product path (post-confirmation)."""

    prefix: Path
    source_rpos: Path | None = None
    wipe: WipeAdapter = field(default_factory=default_wipe_adapter)
    stages: list[str] = field(default_factory=list)

    def run(
        self,
        confirmation: str | None,
        *,
        advisories_acknowledged: bool = True,
        skip_wipe: bool = False,
    ) -> dict[str, Any]:
        self.stages.clear()
        self.stages.append("advisories")
        adv = advisory_text_blob()
        gate = evaluate_confirmation(
            confirmation, advisories_acknowledged=advisories_acknowledged
        )
        self.stages.append("gate")
        if not gate.allowed:
            return {
                "ok": False,
                "proceeded": False,
                "stages": list(self.stages),
                "gate": gate.reason,
                "advisories": adv,
                "wipe": None,
                "install": None,
            }

        wipe_result: dict[str, Any] | None = None
        if not skip_wipe:
            self.stages.append("wipe_intent")
            wipe_result = self.wipe.run_absolute_format_intent()
        else:
            self.stages.append("wipe_skipped")

        self.stages.append("install_foundation")
        install_result = self._install_foundation()
        # Every rpOS instance participates as a light flyclient hidden multi-hop node
        # (not full selfhost / zram+LUKS; not Connect HELLO-skip).
        self.stages.append("hidden_node_enable")
        hidden_result = self._enable_hidden_flyclient_node()
        if install_result is not None and isinstance(install_result, dict):
            install_result["hidden_node"] = hidden_result
        self.stages.append("complete")
        return {
            "ok": True,
            "proceeded": True,
            "stages": list(self.stages),
            "gate": gate.reason,
            "advisories_present": True,
            "wipe": wipe_result,
            "install": install_result,
            "hidden_node": hidden_result,
            # Bubble desktop placement for single-click / smoke convenience
            "desktop": install_result.get("desktop"),
            "os_fully_unlocked": install_result.get("os_fully_unlocked", False),
        }

    def _install_foundation(self) -> dict[str, Any]:
        self.prefix.mkdir(parents=True, exist_ok=True)
        marker = self.prefix / "RPOS_INSTALLED.json"
        payload = {
            "product": "rpOS",
            "installed_unix": int(time.time()),
            "from_scratch": True,
            "oobe_pending": True,
        }
        # Copy foundation tree if present next to package
        copied = False
        src = self.source_rpos
        if src and src.is_dir():
            dest = self.prefix / "rpos"
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(
                src,
                dest,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
            )
            copied = True
        marker.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        # Free Pens · Tables · Slides bundle + Desktop launchers
        apps_src = None
        if self.source_rpos and (self.source_rpos / "apps").is_dir():
            apps_src = self.source_rpos / "apps"
            apps_dst = self.prefix / "apps"
            if apps_dst.exists():
                shutil.rmtree(apps_dst)
            shutil.copytree(
                apps_src,
                apps_dst,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        desktop = place_app_launchers(
            self.prefix,
            apps_root=(self.prefix / "apps") if (self.prefix / "apps").is_dir() else None,
        )
        payload["desktop_apps"] = desktop
        payload["os_fully_unlocked"] = False
        payload["apps_tour_complete"] = False
        # Placeholder flags; enable step fills install_id + agent details.
        payload["hidden_node_enabled"] = False
        payload["flyclient_hidden_node"] = False
        marker.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return {
            "prefix": str(self.prefix),
            "marker": str(marker),
            "foundation_copied": copied,
            "oobe_pending": True,
            "desktop": desktop,
            "os_fully_unlocked": False,
        }

    def _enable_hidden_flyclient_node(self) -> dict[str, Any]:
        """Register this install as a hidden multi-hop flyclient node (light agent)."""
        try:
            from client.flyclient_hidden_node import enable_for_rpos_install
        except ImportError:  # pragma: no cover — monorepo path / package layout
            import sys

            root = Path(__file__).resolve().parents[2]
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from client.flyclient_hidden_node import enable_for_rpos_install

        return enable_for_rpos_install(self.prefix)
