"""In-process action learner for GOD / NED / FRED / PEDRO."""

from __future__ import annotations

from typing import Any

PRODUCT_FAMILIES = (
    "restore_privacy_vpn",
    "evolve_suite",
    "perc_wallet",
    "rpoffice",
    "rpmail",
    "beam_addons",
    "gnfp_pool",
)

_LEARNER: "ActionLearner | None" = None


class ActionLearner:
    def __init__(self) -> None:
        self.state: dict[str, Any] = {
            "parts": [],
            "by_agent": {name: {"learned": 0, "lastLine": "—"} for name in ("GOD", "NED", "FRED", "PEDRO")},
            "seen": set(),
        }

    def learn(
        self,
        agent: str,
        family: str,
        action: str,
        *,
        note: str = "",
        persist: bool = True,
    ) -> bool:
        who = str(agent or "GOD").strip().upper()
        fam = str(family or "evolve_suite").strip().lower() or "evolve_suite"
        act = str(action or "").strip() or "observe"
        key = f"{who}|{fam}|{act}"
        seen = self.state.setdefault("seen", set())
        if key in seen:
            return False
        if persist:
            seen.add(key)
            row = self.state.setdefault("by_agent", {}).setdefault(
                who, {"learned": 0, "lastLine": "—"}
            )
            row["learned"] = int(row.get("learned") or 0) + 1
            line = f"{fam}: {act}"
            if note:
                line = f"{line} — {note}"
            row["lastLine"] = line[:240]
            parts = self.state.setdefault("parts", [])
            parts.append(
                {
                    "key": key,
                    "agent": who,
                    "family": fam,
                    "family_label": fam.replace("_", " ").title(),
                    "action": act,
                }
            )
            if len(parts) > 80:
                del parts[:-80]
        return True


def get_action_learner() -> ActionLearner:
    global _LEARNER
    if _LEARNER is None:
        _LEARNER = ActionLearner()
    return _LEARNER


def reset_action_learner() -> ActionLearner:
    global _LEARNER
    _LEARNER = ActionLearner()
    return _LEARNER


def explorer_agent_learning(state: dict[str, Any] | None) -> list[dict[str, Any]]:
    data = state if isinstance(state, dict) else get_action_learner().state
    by_agent = data.get("by_agent") or {}
    rows = []
    for name in ("GOD", "NED", "FRED", "PEDRO"):
        row = by_agent.get(name) or {}
        rows.append(
            {
                "name": name,
                "learned": int(row.get("learned") or 0),
                "lastLine": str(row.get("lastLine") or "—"),
            }
        )
    return rows
