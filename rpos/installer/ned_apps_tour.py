"""GOD locked guide: Pens → Tables → Slides before full OS unlock."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

AppId = Literal["Pens", "Tables", "Slides"]

TOUR_ORDER: tuple[AppId, ...] = ("Pens", "Tables", "Slides")

NED_TOUR_LINES: dict[AppId, str] = {
    "Pens": (
        "I'm GOD. First meet **Pens** — your privacy-first writing app. "
        "It lives on your Desktop. Look at it with me before we continue."
    ),
    "Tables": (
        "Next is **Tables** — spreadsheets with simple formulas. "
        "It's free with rpOS and waiting on your Desktop."
    ),
    "Slides": (
        "Finally **Slides** — presentations you control. "
        "After this, I'll unlock full use of rpOS for you."
    ),
}

NED_UNLOCK = (
    "You've met Pens, Tables, and Slides. Full rpOS use is unlocked. "
    "Create freely — privacy for the good of all humanity."
)


@dataclass
class AppsTourState:
    step_index: int = 0
    completed: list[str] = field(default_factory=list)
    locked: bool = True
    os_fully_unlocked: bool = False
    ned_log: list[str] = field(default_factory=list)

    @property
    def current_app(self) -> AppId | None:
        if self.step_index >= len(TOUR_ORDER):
            return None
        return TOUR_ORDER[self.step_index]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["order"] = list(TOUR_ORDER)
        d["current_app"] = self.current_app
        d["ned_line"] = (
            NED_TOUR_LINES[self.current_app] if self.current_app else NED_UNLOCK
        )
        return d


class NedAppsTour:
    """Locked guide: each app in turn; OS unlock only after all three."""

    def __init__(self, state: AppsTourState | None = None) -> None:
        self.state = state or AppsTourState()
        self._say()

    def _say(self) -> None:
        if self.state.current_app:
            line = NED_TOUR_LINES[self.state.current_app]
        else:
            line = NED_UNLOCK
        if not self.state.ned_log or self.state.ned_log[-1] != line:
            self.state.ned_log.append(line)

    def acknowledge_current(self) -> AppsTourState:
        """User confirms they were shown the current app (locked step complete)."""
        app = self.state.current_app
        if app is None:
            self.state.locked = False
            self.state.os_fully_unlocked = True
            self._say()
            return self.state
        if app not in self.state.completed:
            self.state.completed.append(app)
        self.state.step_index += 1
        if self.state.step_index >= len(TOUR_ORDER):
            self.state.locked = False
            self.state.os_fully_unlocked = True
        self._say()
        return self.state

    def run_full_tour(
        self,
        *,
        input_fn: Callable[[str], str] | None = None,
        print_fn: Callable[..., None] | None = None,
        auto: bool = False,
    ) -> dict[str, Any]:
        """Walk Pens → Tables → Slides with GOD narration.

        *auto=True* acknowledges each step without prompts (tests / smoke).
        """
        read = input_fn or input
        write = print_fn or print
        steps: list[dict[str, Any]] = []
        while self.state.locked and self.state.current_app:
            app = self.state.current_app
            ned = NED_TOUR_LINES[app]
            write("")
            write(f"GOD: {ned}")
            write(f"  [Locked guide {self.state.step_index + 1}/{len(TOUR_ORDER)}: {app}]")
            if not auto:
                read(f"Press Enter when you have seen {app} on the Desktop… ")
            before = app
            self.acknowledge_current()
            steps.append(
                {
                    "app": before,
                    "ned": ned,
                    "completed": list(self.state.completed),
                    "os_fully_unlocked": self.state.os_fully_unlocked,
                }
            )
        write("")
        write(f"GOD: {NED_UNLOCK}")
        return {
            "ok": True,
            "order": list(TOUR_ORDER),
            "completed": list(self.state.completed),
            "os_fully_unlocked": self.state.os_fully_unlocked,
            "locked": self.state.locked,
            "ned_log": list(self.state.ned_log),
            "steps": steps,
        }


def tour_state_path(prefix: Path) -> Path:
    return Path(prefix) / "ned_apps_tour.json"


def persist_tour(prefix: Path, result: dict[str, Any]) -> Path:
    prefix = Path(prefix)
    prefix.mkdir(parents=True, exist_ok=True)
    path = tour_state_path(prefix)
    payload = dict(result)
    payload["saved_unix"] = int(time.time())
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    # Update install marker unlock flag
    marker = prefix / "RPOS_INSTALLED.json"
    if marker.is_file():
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {"product": "rpOS"}
    data["apps_tour_complete"] = bool(result.get("os_fully_unlocked"))
    data["os_fully_unlocked"] = bool(result.get("os_fully_unlocked"))
    data["apps_tour"] = list(result.get("completed") or [])
    marker.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path
