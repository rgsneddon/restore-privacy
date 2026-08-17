"""Grokbot — Grok Build chaperone under GOD.

GOD leads. Grokbot walks GOD, NED, FRED, and PEDRO through learn and /goal.
"""

from __future__ import annotations

from typing import Any, Callable

GROKBOT_NAME = "Grokbot"
GROKBOT_ROLE = "chaperone"
LEARNERS = ("GOD", "NED", "FRED", "PEDRO")

HIERARCHY = {
    "lead": "GOD",
    "chaperone": GROKBOT_NAME,
    "learners": list(LEARNERS),
    "line": (
        "GOD sits at the top of rpAI. Grokbot is the chaperone: it walks "
        "GOD, NED, FRED, and PEDRO through Grok Build the same way Evolve "
        "leans on Grok to construe a brief."
    ),
}


def standing_order(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    first = raw.split()[0].lower()
    if first in ("/quit", "quit"):
        return "/quit"
    if first in ("/goal", "goal"):
        return "/goal"
    return ""


def grokbot_assist_learn(
    agent: str,
    family: str,
    action: str,
    *,
    xai_fn: Callable[..., str | None] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    try:
        from node.rpai_action_learn import get_action_learner
    except ImportError:  # pragma: no cover
        from rpai_action_learn import get_action_learner  # type: ignore
    who = str(agent or "").strip().upper() or "GOD"
    note = ""
    if xai_fn is not None:
        try:
            note = str(xai_fn(who, family, action) or "")
        except Exception:
            note = ""
    learner = get_action_learner()
    grew = learner.learn(who, family, action, note=note, persist=persist)
    agents = explorer_rows(learner)
    return {
        "ok": True,
        "agent": who,
        "family": family,
        "action": action,
        "grew": grew,
        "duplicate": not grew,
        "agents": agents,
        "hierarchy": HIERARCHY["line"],
        "note": note,
    }


def grokbot_build_goal(
    text: str,
    *,
    family: str = "evolve_suite",
    scs: float | None = None,
    percent_chance: float | None = None,
    xai_fn: Callable[..., str | None] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    if standing_order(text) == "/quit":
        return {
            "ok": True,
            "who": GROKBOT_NAME,
            "standing": "/quit",
            "answer": "quit",
            "agents": [],
        }
    action = (text or "").strip() or "/goal build a thing"
    rows = []
    for agent in LEARNERS:
        rows.append(
            grokbot_assist_learn(
                agent, family, action, xai_fn=xai_fn, persist=persist
            )
        )
    last = rows[-1] if rows else {"ok": False}
    return {
        "ok": bool(last.get("ok")),
        "who": GROKBOT_NAME,
        "standing": "/goal",
        "family": family,
        "action": action,
        "scs": scs,
        "percent_chance": percent_chance,
        "learned_rows": [
            {"agent": r.get("agent"), "grew": r.get("grew"), "duplicate": r.get("duplicate")}
            for r in rows
        ],
        "agents": last.get("agents") or [],
        "hierarchy": HIERARCHY["line"],
        "grokbot_invoked": True,
        "answer": "The four agents have that brief.",
    }


def explorer_rows(learner: Any) -> list[dict[str, Any]]:
    try:
        from node.rpai_action_learn import explorer_agent_learning
    except ImportError:  # pragma: no cover
        from rpai_action_learn import explorer_agent_learning  # type: ignore
    return explorer_agent_learning(learner.state)
