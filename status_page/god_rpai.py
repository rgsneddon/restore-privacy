"""Dedicated GOD · rpAI page (god.restoreprivacy.online[:1474]).

Wholly rpAI: hierarchy, four-agent learning, outputs, and learn-from-input.
Not the shop, not the ticket form, not Perc mining. Grokbot (Grok Build)
chaperones; GOD leads.

Port 1474 sits beside mineperc :1466 as the GOD control plane — it is not
Beam :1974 and not a VPN dataplane.
"""

from __future__ import annotations

import html
import json
from typing import Any, Callable

GOD_RPAI_HOST = "god.restoreprivacy.online"
GOD_RPAI_PORT = 1474  # public: $GNFP BeamHash III stratum (perc miner)
GOD_HTTP_PORT = 8013  # loopback: dedicated GOD · rpAI page
GOD_RPAI_PATH = "/god"
GOD_LEARN_PATH = "/api/learn"
GOD_RPAI_API = "/api/rpai"
# Only apex restoreprivacy.online map href allowed on this host (god. /downloads-map 404s).
GOD_DOWNLOADS_MAP_HREF = "https://restoreprivacy.online/downloads-map"
GOD_MAIN_TITLE = (
    "God's GNPF crypto-coin. Private by default on a chronoflux "
    "blockchain architecture."
)

PORT_1474_BENEFITS: tuple[tuple[str, str], ...] = (
    (
        "rpAI control plane",
        "A host and port that only speak GOD, Grokbot, NED, FRED, and PEDRO — "
        "no shop, no KEYGEN form, no ticket queue.",
    ),
    (
        "Learn-from-input ingest",
        "Ask GOD, /goal builds, and observe fields POST here. Grokbot writes "
        "a distinct part for each agent. Same product+action does not grow twice.",
    ),
    (
        "Output feed",
        "GET /api/rpai returns each agent's learned count, last line, and "
        "recent parts so evolve.restoreprivacy.online can stay current.",
    ),
    (
        "Beside mineperc, not mining",
        "1466 is Perc BeamHash. 1474 is GOD. 1690/1974 stay on Beam. "
        "Opening 1474 does not open a miner and does not read tunnel payloads.",
    ),
    (
        "Grok Build channel",
        "Grokbot chaperones /goal the way Evolve Grok construe uses Grok — "
        "build a thing, then the four agents learn the brief.",
    ),
    (
        "Quiet when closed",
        "If 1474 is not open, HTTPS /god on the main host still serves the "
        "same page. Opening the port is extra ingest, not a second chatbot.",
    ),
)


def is_god_host(host: str) -> bool:
    raw = (host or "").strip().lower().split(":")[0]
    return raw == GOD_RPAI_HOST or raw.startswith("god.")


def _learn_surface(state: Any = None, **hints: Any) -> dict[str, Any]:
    try:
        from node.rpai_learn_surface import explorer_surface_stats
    except ImportError:  # pragma: no cover
        from rpai_learn_surface import explorer_surface_stats  # type: ignore
    return explorer_surface_stats(
        state,
        region=str(hints.get("region") or ""),
        country=str(hints.get("country") or ""),
    )


def rpai_dashboard_payload() -> dict[str, Any]:
    try:
        from grokbot import GROKBOT_NAME, GROKBOT_ROLE, HIERARCHY, LEARNERS
        from node.rpai_action_learn import (
            explorer_agent_learning,
            get_action_learner,
        )
    except ImportError:  # pragma: no cover
        from status_page.grokbot import (  # type: ignore
            GROKBOT_NAME,
            GROKBOT_ROLE,
            HIERARCHY,
            LEARNERS,
        )
        from node.rpai_action_learn import (  # type: ignore
            explorer_agent_learning,
            get_action_learner,
        )
    try:
        from god_support import learned_count, load_scenarios
    except ImportError:  # pragma: no cover
        from status_page.god_support import learned_count, load_scenarios  # type: ignore

    learner = get_action_learner()
    agents = explorer_agent_learning(learner.state)
    sc = load_scenarios()
    try:
        from gnfp import GNFP_TICKER, gnfp_tip_height
    except ImportError:  # pragma: no cover
        from status_page.gnfp import GNFP_TICKER, gnfp_tip_height  # type: ignore
    tip = int(gnfp_tip_height())
    return {
        "identity": "GOD · rpAI",
        "host": GOD_RPAI_HOST,
        "port": GOD_RPAI_PORT,
        "hierarchy": HIERARCHY,
        "chaperone": GROKBOT_NAME,
        "chaperone_role": GROKBOT_ROLE,
        "learners": list(LEARNERS),
        "agents": agents,
        "god_topics": learned_count(),
        "fred": sc.get("FRED") or {},
        "god_scenario": sc.get("GOD") or {},
        "benefits": [{"id": k, "text": v} for k, v in PORT_1474_BENEFITS],
        "parts": list((learner.state.get("parts") or [])[-24:]),
        "gnfp": {
            "ticker": GNFP_TICKER,
            "height": tip,
            "tip": tip,
            "label": "GNFP tip height",
        },
        "gnfpHeight": tip,
        "gnfp_height": tip,
        "surface": _learn_surface(learner.state),
    }


def learn_from_input(
    payload: dict[str, Any] | None,
    *,
    xai_fn: Callable[..., str | None] | None = None,
) -> dict[str, Any]:
    """Any public input on the GOD page becomes a learned part (all four agents)."""
    try:
        from grokbot import LEARNERS, grokbot_assist_learn, grokbot_build_goal, standing_order
        from node.rpai_action_learn import PRODUCT_FAMILIES
    except ImportError:  # pragma: no cover
        from status_page.grokbot import (  # type: ignore
            LEARNERS,
            grokbot_assist_learn,
            grokbot_build_goal,
            standing_order,
        )
        from node.rpai_action_learn import PRODUCT_FAMILIES  # type: ignore

    data = payload if isinstance(payload, dict) else {}
    text = str(
        data.get("input")
        or data.get("action")
        or data.get("brief")
        or data.get("question")
        or ""
    ).strip()
    if standing_order(text) == "/quit" or str(data.get("quit") or "") in ("1", "true"):
        return grokbot_build_goal("/quit", xai_fn=xai_fn, persist=False)
    if standing_order(text) == "/goal" or str(data.get("standing") or "") == "/goal":
        return grokbot_build_goal(
            text or "/goal build a thing",
            family=str(data.get("family") or "evolve_suite"),
            scs=_opt_float(data.get("scs")),
            percent_chance=_opt_float(data.get("percent_chance") or data.get("percent")),
            xai_fn=xai_fn,
            persist=True,
        )
    fam = str(data.get("family") or "").strip().lower()
    if fam not in PRODUCT_FAMILIES:
        fam = _family_from_text(text)
    action = text or str(data.get("action") or "observe input")
    who = str(data.get("agent") or "").strip().upper()
    targets = [who] if who in LEARNERS else list(LEARNERS)
    rows = []
    for agent in targets:
        rows.append(
            grokbot_assist_learn(
                agent, fam, action, xai_fn=xai_fn, persist=True
            )
        )
    last = rows[-1] if rows else {"ok": False}
    return {
        "ok": bool(last.get("ok")),
        "who": "Grokbot",
        "family": fam,
        "action": action,
        "learned_rows": [
            {"agent": r.get("agent"), "grew": r.get("grew"), "duplicate": r.get("duplicate")}
            for r in rows
        ],
        "agents": last.get("agents") or [],
        "hierarchy": last.get("hierarchy") or "",
        "grokbot_invoked": True,
        "answer": "The four agents have that input.",
        "surface": _learn_surface(
            None,
            region=str(data.get("region") or ""),
            country=str(data.get("country") or ""),
        ),
    }


def _opt_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, n))


def _family_from_text(text: str) -> str:
    low = (text or "").lower()
    if "mail" in low or "rpmail" in low:
        return "rpmail"
    if "office" in low or "rpoffice" in low:
        return "rpoffice"
    if "wallet" in low or "perc" in low:
        return "perc_wallet"
    if "beam" in low or "addon" in low:
        return "beam_addons"
    if "vpn" in low or "residual" in low or "connect" in low:
        return "restore_privacy_vpn"
    return "evolve_suite"


def render_god_ticket_box_html() -> str:
    """Bottom box: email rus@restoreprivacy.online via the public support form."""
    inbox = "rus@restoreprivacy.online"
    return f"""
<section class="panel-card" id="god-ticket-box" data-god-ticket="1">
  <h3 id="god-ticket-title">Support</h3>
  <p class="hint">Write to <strong>{html.escape(inbox)}</strong>. We never ask for KEYGENs, cards, or passwords.</p>
  <form class="support-form" method="post" action="https://restoreprivacy.online/support" id="god-ticket-form">
    <label for="support-email">Your email *</label>
    <input id="support-email" name="email" type="email" required autocomplete="email" placeholder="you@example.com"/>
    <label for="support-subject">Subject *</label>
    <input id="support-subject" name="subject" type="text" required maxlength="200" placeholder="Short summary"/>
    <label for="support-message">Message *</label>
    <textarea id="support-message" name="message" required maxlength="8000" placeholder="How can we help?"></textarea>
    <p class="hint">Please allow up to 48 hours.</p>
    <button type="submit" id="god-ticket-submit">Email {html.escape(inbox)}</button>
  </form>
</section>
"""


def god_rpai_css() -> str:
    try:
        from god_support import god_support_css
        from goal_builder import goal_builder_css
    except ImportError:  # pragma: no cover
        from status_page.god_support import god_support_css  # type: ignore
        from status_page.goal_builder import goal_builder_css  # type: ignore
    extra = """
#god-rpai-main.support-wrap { max-width: 72rem; }
.god-agent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: 0.75rem;
  margin: 0 0 1.2rem;
}
.god-agent-card .value { font-size: 1.45rem; font-weight: 750; }
.god-port-benefits li { margin: 0.35rem 0; line-height: 1.45; }
.god-output-list { margin: 0.4rem 0 0; padding-left: 1.2rem; }
#god-main-title {
  margin: 0 0 0.85rem;
  color: #00e5ff;
  font-size: clamp(1.2rem, 3.1vw, 1.85rem);
  font-weight: 750;
  letter-spacing: 0.03em;
  line-height: 1.25;
  text-shadow:
    0 0 8px rgba(0, 229, 255, 0.9),
    0 0 18px rgba(38, 148, 232, 0.55),
    0 0 32px rgba(0, 229, 255, 0.35);
}
#god-input-box { text-align: center; }
#god-input-box h3, #god-input-box .hint, #god-input-box label { text-align: center; }
#god-input-box textarea, #god-input-box label {
  display: block;
  margin-left: auto;
  margin-right: auto;
  max-width: 36rem;
}
#god-input-box button { display: inline-block; margin: 0.55rem auto 0; }
#god-ticket-box { margin-top: 1.2rem; }
#theme-mode-control, .theme-mode-control { display: none !important; }
#god-cli-box {
  margin: 1rem 0 1.2rem;
  padding: 0.75rem 0.9rem 0.85rem;
  background: #1a1d22;
  border: 1px solid #2694e8;
  box-shadow: 0 0 14px rgba(0, 229, 255, 0.18);
}
#god-cli-box h3 {
  margin: 0 0 0.45rem;
  color: #00e5ff;
  font-weight: 800;
  letter-spacing: 0.06em;
}
#god-cli, .goal-cli, #goal-cli {
  margin: 0;
  min-height: 12rem;
  max-height: 22rem;
  overflow-y: auto;
  background: #2b2b2b;
  color: #00e5ff;
  font-weight: 700;
  font-family: ui-monospace, Consolas, "Cascadia Code", monospace;
  font-size: 0.82rem;
  line-height: 1.35;
  white-space: pre-wrap;
  padding: 0.65rem 0.75rem;
}
#grok-construe, #goal-grok-construe {
  appearance: none; cursor: pointer; font: inherit; font-weight: 800;
  padding: 0.55rem 1rem; border-radius: 0;
  border: 1px solid #00e5ff;
  background: #14171c;
  color: #00e5ff;
  text-decoration: none; display: inline-block;
  text-shadow: 0 0 8px rgba(0, 229, 255, 0.85);
}
#gnfp-tip-card .value { color: #00e5ff; font-weight: 800; }
#god-cli-stay { color: #00e5ff; font-weight: 700; margin: 0.45rem 0 0; }
#god-cli-download { display: none; margin-top: 0.65rem; }
#god-cli-download.is-ready { display: inline-block; }
#god-rpai-shell #doc-links, #god-rpai-shell .nav-btn { display: none !important; }
html, html[data-theme="light"], html[data-theme="dark"], body.site-public {
  --rb-navy: #1a1d22;
  --rb-navy-mid: #22262c;
  --rb-card: #2a2f36;
  --rb-cream: #e8eef5;
  --rb-soft: #c8d4de;
  --rb-muted: #9aa8b5;
  --rb-body-bg1: #1a1d22;
  --rb-body-bg2: #14171c;
  --rb-body-bg3: #101217;
  --rb-body-bg4: #0c0e12;
  --rb-neon-cyan: #00e5ff;
  --rb-neon-blue: #2694e8;
  --rb-neon-border: linear-gradient(135deg, #2694e8 0%, #00e5ff 100%);
  color-scheme: dark;
}
body.site-public {
  background: linear-gradient(180deg, #1a1d22 0%, #14171c 50%, #0c0e12 100%) !important;
  color: #e8eef5 !important;
}
#god-rpai-main, .god-support-box, .goal-builder-box, .panel-card {
  color: #e8eef5;
}
.hint, .support-lead, .god-support-lead, .goal-builder-lead, .label {
  color: #9aa8b5;
}
"""
    return god_support_css() + goal_builder_css() + extra


def _learn_surface_html(dash: dict[str, Any]) -> str:
    try:
        from node.rpai_learn_surface import render_explorer_agent_stats_html
    except ImportError:  # pragma: no cover
        from rpai_learn_surface import render_explorer_agent_stats_html  # type: ignore
    return render_explorer_agent_stats_html(dash.get("surface"))


def render_god_rpai_page_html() -> str:
    try:
        from public_chrome import (
            PUBLIC_BRAND_TITLE,
            public_brand_header_html,
            public_head_open,
            public_page_close,
        )
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import (  # type: ignore
            PUBLIC_BRAND_TITLE,
            public_brand_header_html,
            public_head_open,
            public_page_close,
        )
    try:
        from god_support import render_god_support_box_html
        from goal_builder import render_goal_builder_box_html
        from grokbot import HIERARCHY
    except ImportError:  # pragma: no cover
        from status_page.god_support import render_god_support_box_html  # type: ignore
        from status_page.goal_builder import render_goal_builder_box_html  # type: ignore
        from status_page.grokbot import HIERARCHY  # type: ignore

    dash = rpai_dashboard_payload()
    head = public_head_open(
        title=GOD_MAIN_TITLE,
        extra_css=god_rpai_css(),
    )
    header = public_brand_header_html(
        active=None,
        include_site_nav=False,
        include_theme_picker=False,
        banner_src="/god_banner.jpg",
    )
    close = public_page_close(downloads_map_href=GOD_DOWNLOADS_MAP_HREF)
    god_box = render_god_support_box_html()
    goal_box = render_goal_builder_box_html()
    ticket_box = render_god_ticket_box_html()
    agent_cards = []
    for row in dash["agents"]:
        name = html.escape(str(row.get("name") or ""))
        learned = html.escape(str(row.get("learned") or 0))
        last = html.escape(str(row.get("lastLine") or "—"))
        agent_cards.append(
            f'<article class="panel-card god-agent-card" data-agent="{name}">'
            f'<div class="label">{name}</div>'
            f'<div class="value" data-agent-learned="{name}">{learned}</div>'
            f'<p class="hint" data-agent-last="{name}">{last}</p></article>'
        )
    tip = int(dash.get("gnfpHeight") or dash.get("gnfp_height") or 0)
    agent_cards.append(
        '<article class="panel-card god-agent-card" id="gnfp-tip-card" data-gnfp-tip="1">'
        '<div class="label">GNFP tip height</div>'
        f'<div class="value" id="gnfp-tip-height" data-gnfp-height="1">{tip}</div>'
        '<p class="hint">Most recent $GNFP block</p></article>'
    )
    benefits = "".join(
        f"<li><strong>{html.escape(item['id'])}.</strong> {html.escape(item['text'])}</li>"
        for item in dash["benefits"]
    )
    parts = dash.get("parts") or []
    if parts:
        recent = "".join(
            f'<li data-part-key="{html.escape(str(p.get("key") or ""))}">'
            f'{html.escape(str(p.get("family_label") or p.get("family") or ""))}: '
            f'{html.escape(str(p.get("action") or ""))}</li>'
            for p in reversed(parts)
        )
    else:
        recent = '<li class="ned-learned-empty">No learned parts yet.</li>'
    return f"""{head}
  <div class="page-shell" id="god-rpai-shell" data-page="god-rpai" data-god-port="{GOD_RPAI_PORT}">
{header}
<main class="support-wrap panel-card" id="god-rpai-main" data-chrome="pro" data-rpai-surface="1">
  <h1 id="god-main-title">{html.escape(GOD_MAIN_TITLE)}</h1>
  <p class="support-lead" id="god-rpai-lead">{html.escape(HIERARCHY["line"])}</p>
  <section class="panel-card" id="god-port-box">
    <h3>god.restoreprivacy.online:{GOD_RPAI_PORT}</h3>
    <p class="hint">Dedicated rpAI host at 135.181.152.10. HTTPS is this page.
    Port {GOD_RPAI_PORT} is the $GNFP BeamHash III CPU stratum — same perc miner
    as mineperc:1466, proof of work only. Miner tags are hashed; no public
    user info. <a href="/gnfp">$GNFP pool</a> ·
    <a href="/gnfp/explorer">explorer</a> ·
    <a href="/gnfp/api/network">network</a>.</p>
    <ul class="god-port-benefits" id="god-port-benefits">{benefits}</ul>
  </section>
  <div class="god-agent-grid" id="god-agent-grid">
    {''.join(agent_cards)}
  </div>
  {_learn_surface_html(dash)}
  <div class="rpai-support-row" id="rpai-support-row">
  {god_box}
  {goal_box}
  </div>
  <section class="panel-card" id="god-cli-box" data-god-cli="1">
    <h3>Grok Build · CLI</h3>
    <pre id="god-cli" aria-live="polite">idle — press Build. Stay on this page until the installer is sealed.</pre>
    <p class="hint" id="god-cli-stay">Evolve Suite is the surface. The four agents have the brief.</p>
    <a id="god-cli-download" class="btn" href="#">Download installer</a>
  </section>
  <section class="panel-card" id="god-input-box">
    <h3>Learn from input</h3>
    <p class="hint">Any public line here is a distinct action. Secrets are refused.</p>
    <label for="god-learn-input">Input</label>
    <textarea id="god-learn-input" maxlength="800" placeholder="observe: open analysis surface"></textarea>
    <button type="button" id="god-learn-submit">Teach the four agents</button>
    <pre class="goal-builder-answer" id="god-learn-answer" hidden></pre>
  </section>
  <section class="panel-card rpai-agent-learn" id="rpai-agent-learn">
    <h3>Outputs · recently learned</h3>
    <ol class="god-output-list" id="god-output-list">{recent}</ol>
  </section>
  {ticket_box}
</main>
  </div>
<script src="/static/god_rpai.js" defer></script>
<script src="/static/god_build.js" defer></script>
{close}
"""
