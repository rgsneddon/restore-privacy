"""Wipe-intent adapters — default is dry-run (never touches host disks)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol


class WipeAdapter(Protocol):
    def run_absolute_format_intent(self) -> dict[str, Any]:
        """Execute or simulate absolute format / remove-all-files intent."""
        ...


@dataclass
class DryRunWipeAdapter:
    """Safe default: log absolute wipe intent without reformatting the host."""

    log: list[str] = field(default_factory=list)

    def run_absolute_format_intent(self) -> dict[str, Any]:
        ts = int(time.time())
        msg = (
            "DRY-RUN absolute format intent: remove all files and settings, "
            "prepare blank system for rpOS from scratch"
        )
        self.log.append(msg)
        return {
            "mode": "dry_run",
            "wiped": False,
            "intent": "absolute_format_and_remove_all",
            "message": msg,
            "unix": ts,
            "host_disk_touched": False,
        }


@dataclass
class PrivilegedHostWipeStub:
    """Stub for elevated host wipe — requires privileged host, not used in tests.

    Real platform hooks (diskpart / diskutil / wipefs) would plug in here only
    on operator-approved media; this stub refuses unless force_unsafe is set.
    """

    force_unsafe: bool = False

    def run_absolute_format_intent(self) -> dict[str, Any]:
        if not self.force_unsafe:
            return {
                "mode": "privileged_stub",
                "wiped": False,
                "intent": "absolute_format_and_remove_all",
                "message": "privileged wipe hook not armed (force_unsafe=False)",
                "host_disk_touched": False,
            }
        # Still does not call real OS format tools — product boundary.
        return {
            "mode": "privileged_stub_armed",
            "wiped": False,
            "intent": "absolute_format_and_remove_all",
            "message": "armed stub only — no diskutil/diskpart invoked in this build",
            "host_disk_touched": False,
        }


def default_wipe_adapter() -> WipeAdapter:
    return DryRunWipeAdapter()
