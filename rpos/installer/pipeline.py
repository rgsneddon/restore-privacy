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
        self.stages.append("complete")
        return {
            "ok": True,
            "proceeded": True,
            "stages": list(self.stages),
            "gate": gate.reason,
            "advisories_present": True,
            "wipe": wipe_result,
            "install": install_result,
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
        return {
            "prefix": str(self.prefix),
            "marker": str(marker),
            "foundation_copied": copied,
            "oobe_pending": True,
        }
