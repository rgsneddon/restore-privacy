"""GOD-guided first setup: timezone → language → email into rpMail."""

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
        "Hello — I'm GOD, your Restore Privacy Helper. "
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
    """Ordered first-boot machine with GOD narration at every step."""

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


def oobe_state_path(prefix: Path) -> Path:
    """Canonical OOBE/rpMail prefs path under an install prefix."""
    return Path(prefix) / "oobe_state.json"


def install_marker_path(prefix: Path) -> Path:
    return Path(prefix) / "RPOS_INSTALLED.json"


def mark_oobe_complete_on_prefix(prefix: Path, oobe_payload: dict[str, Any]) -> dict[str, Any]:
    """Persist OOBE under *prefix* and clear oobe_pending on RPOS_INSTALLED.json."""
    prefix = Path(prefix)
    prefix.mkdir(parents=True, exist_ok=True)
    state_path = oobe_state_path(prefix)
    state_path.write_text(
        json.dumps(oobe_payload, indent=2) + "\n", encoding="utf-8"
    )
    marker = install_marker_path(prefix)
    if marker.is_file():
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"product": "rpOS"}
    else:
        data = {
            "product": "rpOS",
            "installed_unix": int(time.time()),
            "from_scratch": True,
        }
    data["oobe_pending"] = False
    data["oobe_completed_unix"] = int(time.time())
    data["timezone"] = oobe_payload.get("timezone") or ""
    data["language"] = oobe_payload.get("language") or ""
    data["rpmail"] = oobe_payload.get("rpmail")
    data["oobe_state"] = str(state_path)
    marker.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    # Secondary GOD growth signal: completed narrative / OOBE session.
    try:
        import sys
        from pathlib import Path as _P

        _sp = _P(__file__).resolve().parents[2] / "status_page"
        if _sp.is_dir() and str(_sp) not in sys.path:
            sys.path.insert(0, str(_sp))
        from admin_rps import record_narrative_session

        growth = record_narrative_session()
        data["ned_growth"] = {
            "narrative_sessions": growth.get("narrative_sessions"),
            "growth_score": growth.get("growth_score"),
            "learning_epochs": growth.get("learning_epochs"),
        }
    except Exception:  # noqa: BLE001
        data["ned_growth"] = None
    return data


def _finish_oobe(
    oobe: NedOobe,
    steps_out: list[dict[str, Any]],
    *,
    persist_path: Path | None = None,
    prefix: Path | None = None,
) -> dict[str, Any]:
    assert oobe.state.completed
    rpmail = oobe.bind_rpmail()
    payload = {
        "ok": True,
        "mode": "interactive" if any(
            s.get("interactive") for s in steps_out
        ) else "scripted",
        "ned": NED_LINES["complete"],
        "timezone": oobe.state.timezone,
        "language": oobe.state.language,
        "email": oobe.state.email,
        "rpmail": rpmail,
        "ned_log": list(oobe.state.ned_log),
        "steps": steps_out,
        "persisted": None,
        "prefix": str(prefix) if prefix else None,
        "oobe_pending": True,
    }
    # Prefer install prefix binding when provided
    if prefix is not None:
        # Also write full payload for reload
        full = {
            "oobe": oobe.state.to_dict(),
            "rpmail": rpmail,
            "timezone": oobe.state.timezone,
            "language": oobe.state.language,
            "email": oobe.state.email,
            "ned_log": list(oobe.state.ned_log),
            "saved_unix": int(time.time()),
        }
        mark_oobe_complete_on_prefix(prefix, full)
        payload["persisted"] = str(oobe_state_path(prefix))
        payload["oobe_pending"] = False
        payload["install_marker"] = str(install_marker_path(prefix))
    elif persist_path is not None:
        oobe.persist(persist_path)
        payload["persisted"] = str(persist_path)
        payload["oobe_pending"] = False
    return payload


def run_oobe_scripted(
    timezone: str,
    language: str,
    email: str,
    *,
    persist_path: Path | None = None,
    prefix: Path | None = None,
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
                "interactive": False,
            }
        )
    return _finish_oobe(oobe, steps_out, persist_path=persist_path, prefix=prefix)


def run_oobe_interactive(
    *,
    persist_path: Path | None = None,
    prefix: Path | None = None,
    input_fn=None,
    print_fn=None,
) -> dict[str, Any]:
    """Product OOBE: GOD prints each line; user supplies timezone, language, email.

    *input_fn* / *print_fn* default to builtins so tests can inject fakes.
    """
    read = input_fn or input
    write = print_fn or print
    oobe = NedOobe()
    steps_out: list[dict[str, Any]] = []
    prompts = {
        "timezone": "Timezone (e.g. Europe/London, America/New_York, UTC): ",
        "language": "Language (e.g. en-GB, en-US, fr, de): ",
        "email_rpmail": "Email for rpMail (you@example.com): ",
    }
    while not oobe.state.completed:
        step = oobe.state.step
        ned = oobe.state.current_ned_line()
        write("")
        write(f"GOD: {ned}")
        prompt = prompts.get(step, f"{step}: ")
        while True:
            try:
                value = read(prompt)
            except EOFError as exc:
                raise ValueError(f"{step} required") from exc
            try:
                oobe.advance(str(value or ""))
                break
            except ValueError as exc:
                write(f"  ({exc}) Please try again.")
        steps_out.append(
            {
                "step": step,
                "ned": ned,
                "value": (
                    oobe.state.timezone
                    if step == "timezone"
                    else oobe.state.language
                    if step == "language"
                    else oobe.state.email
                ),
                "next": oobe.state.step,
                "interactive": True,
            }
        )
    write("")
    write(f"GOD: {NED_LINES['complete']}")
    return _finish_oobe(oobe, steps_out, persist_path=persist_path, prefix=prefix)
