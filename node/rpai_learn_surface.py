"""Public agent-intelligence table for the GOD page."""

from __future__ import annotations

import html
from typing import Any


def explorer_surface_stats(
    state: Any = None,
    *,
    region: str = "",
    country: str = "",
) -> dict[str, Any]:
    try:
        from node.rpai_action_learn import explorer_agent_learning, get_action_learner
    except ImportError:  # pragma: no cover
        from rpai_action_learn import explorer_agent_learning, get_action_learner  # type: ignore
    data = state if isinstance(state, dict) else get_action_learner().state
    agents = explorer_agent_learning(data)
    pin = (region or "Helsinki").strip() or "Helsinki"
    loc = (country or pin).strip() or pin
    return {
        "agents": agents,
        "pin": pin,
        "country": loc,
        "label": f"{pin} ({loc})",
    }


def render_explorer_agent_stats_html(surface: dict[str, Any] | None) -> str:
    data = surface if isinstance(surface, dict) else explorer_surface_stats()
    pin = html.escape(str(data.get("label") or "Helsinki"))
    rows = []
    for agent in data.get("agents") or []:
        name = html.escape(str(agent.get("name") or ""))
        learned = html.escape(str(agent.get("learned") or 0))
        last = html.escape(str(agent.get("lastLine") or "—"))
        rows.append(
            f"<tr><td>{name}</td><td>{learned}</td><td>{learned}</td>"
            f"<td>{learned}</td><td>{last}</td></tr>"
        )
    body = "".join(rows) or "<tr><td colspan='5'>—</td></tr>"
    return f"""
<section class="panel-card" id="god-agent-intelligence" data-agent-intelligence="1">
  <h2>Agent intelligence</h2>
  <p class="hint">Each agent's own learned parts. Multihop learn pin: <strong>{pin}</strong>.</p>
  <table class="god-intel-table">
    <thead><tr><th>Agent</th><th>Learned</th><th>Height</th><th>Intelligence</th><th>Last</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</section>
"""
