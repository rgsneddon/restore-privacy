"""Ned-guided first setup: timezone → language → email into rpMail."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

StepId = Literal["timezone", "language", "email_rpmail", "complete"]

OOBE_STEPS: tuple[StepId, ...] = ("timezone", "language", "email_rpmail", "complete")

NED_LINES: dict[StepId, str] = {
    "timezone": (
        "Hello — I'm Ned, your Restore Privacy Helper. "
        "We'll set your timezone first so clocks and mail stay honest."
    ),
    "language": (
        "Good. Next, choose the language you want rpOS to speak with you."
    ),
    "email_rpmail": (
        "Almost home. Add the email address you'll use in rpMail — "
        "your private mailbox identity on this from-scratch system."
    ),
    "complete": (
        "All set. Timezone, language, and rpMail email are saved. "
        "Welcome to rpOS — privacy for the good of all humanity."
    ),
}


@dataclass
class OobeState:
    step: StepId = "timezone"
    timezone: str = ""
    language: str = ""
    email: str = ""
    ned_log: list[str] = field(default_factory=list)
    completed: bool = False

    def current_ned_line(self) -> str:
        return NED_LINES[self.step]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ned_line"] = self.current_ned_line()
        d["steps"] = list(OOBE_STEPS)
        return d


class NedOobe:
    """Ordered first-boot machine with Ned narration at every step."""

    def __init__(self, state: OobeState | None = None) -> None:
        self.state = state or OobeState()
        self._say_current()

    def _say_current(self) -> None:
        line = self.state.current_ned_line()
        if not self.state.ned_log or self.state.ned_log[-1] != line:
            self.state.ned_log.append(line)

    def advance(self, value: str) -> OobeState:
        """Apply user value for current step and advance."""
        v = (value or "").strip()
        if self.state.step == "timezone":
            if not v:
                raise ValueError("timezone required")
            self.state.timezone = v
            self.state.step = "language"
        elif self.state.step == "language":
            if not v:
                raise ValueError("language required")
            self.state.language = v
            self.state.step = "email_rpmail"
        elif self.state.step == "email_rpmail":
            if "@" not in v or "." not in v.split("@")[-1]:
                raise ValueError("valid email required for rpMail")
            self.state.email = v.lower()
            self.state.step = "complete"
            self.state.completed = True
        elif self.state.step == "complete":
            pass
        else:
            raise RuntimeError(f"unknown step {self.state.step}")
        self._say_current()
        return self.state

    def bind_rpmail(self) -> dict[str, Any]:
        """Record email as rpMail-bound identity (local product state)."""
        if not self.state.completed or not self.state.email:
            raise RuntimeError("OOBE not complete")
        return {
            "product": "rpMail",
            "address": self.state.email,
            "bound": True,
            "source": "rpos_ned_oobe",
            "timezone": self.state.timezone,
            "language": self.state.language,
        }

    def persist(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "oobe": self.state.to_dict(),
            "rpmail": self.bind_rpmail() if self.state.completed else None,
            "saved_unix": int(time.time()),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "NedOobe":
        data = json.loads(path.read_text(encoding="utf-8"))
        o = data.get("oobe") or {}
        st = OobeState(
            step=o.get("step") or "timezone",
            timezone=o.get("timezone") or "",
            language=o.get("language") or "",
            email=o.get("email") or "",
            ned_log=list(o.get("ned_log") or []),
            completed=bool(o.get("completed")),
        )
        return cls(st)


def run_oobe_scripted(
    timezone: str,
    language: str,
    email: str,
    *,
    persist_path: Path | None = None,
) -> dict[str, Any]:
    """Non-interactive OOBE for smoke/tests — still drives real step machine."""
    oobe = NedOobe()
    steps_out: list[dict[str, Any]] = []
    for value in (timezone, language, email):
        before = oobe.state.step
        ned_before = oobe.state.current_ned_line()
        oobe.advance(value)
        steps_out.append(
            {
                "step": before,
                "ned": ned_before,
                "value": value,
                "next": oobe.state.step,
            }
        )
    assert oobe.state.completed
    rpmail = oobe.bind_rpmail()
    if persist_path:
        oobe.persist(persist_path)
    return {
        "ok": True,
        "ned": NED_LINES["complete"],
        "timezone": oobe.state.timezone,
        "language": oobe.state.language,
        "email": oobe.state.email,
        "rpmail": rpmail,
        "ned_log": list(oobe.state.ned_log),
        "steps": steps_out,
        "persisted": str(persist_path) if persist_path else None,
    }
