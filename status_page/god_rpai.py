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
GOD_PAGE_TITLE = "GOD · Restore Privacy"
GOD_BANNER_SRC = "/bannerall.jpg"
GOD_BANNER_FILE = "bannerall.jpg"

VPN_CATALOG_VERSION = "1.2.7"
GNFP_WALLET_PIN = "0.0.5"
EVOLVE_PIN = "4.2.1"

VPN_FREE = "https://restoreprivacy.online/suite/download?platform={platform}&free_direct=1"
GNFP_REL = "https://github.com/rgsneddon/gnfp-wallet/releases"
EVOLVE_REL = "https://github.com/rgsneddon/evolve/releases"


def _vpn_href(platform: str) -> str:
    return VPN_FREE.format(platform=platform)


def _gnfp_href(filename: str) -> str:
    return f"{GNFP_REL}/download/v{GNFP_WALLET_PIN}/{filename}"


def _evolve_href(filename: str) -> str:
    return f"{EVOLVE_REL}/download/v{EVOLVE_PIN}/{filename}"


def hub_menu_links() -> tuple[tuple[str, str], ...]:
    """Visitor menu above the installer boxes. Evolve href is as specified."""
    return (
        ("GNFP POOL", "https://gnfp.restoreprivacy.online"),
        ("GNFP EXPLORER", "https://explorer.restoreprivacy.online"),
        ("RESTORE PRIVACY VPN", "https://www.restoreprivacy.online"),
        ("EVOLVE", "https://evolve.restorepirvacy.online"),
    )


def hub_products() -> tuple[dict[str, Any], ...]:
    """Current public installer set. Missing GNFP 0.0.5 Windows/Linux stay off."""
    return (
        {
            "id": "vpn",
            "name": "Restore Privacy VPN",
            "version": VPN_CATALOG_VERSION,
            "blurb": (
                "Residual VPN client, catalog "
                f"{VPN_CATALOG_VERSION}. Download is free; Connect uses a "
                "three-day device trial, then a KEYGEN."
            ),
            "release": "https://restoreprivacy.online/downloads-map",
            "hrefs": (
                ("Windows", _vpn_href("windows")),
                ("macOS", _vpn_href("macos")),
                ("Linux", _vpn_href("linux")),
                ("Android", _vpn_href("android")),
                ("iOS", _vpn_href("ios")),
            ),
        },
        {
            "id": "gnfp",
            "name": "GNFP",
            "version": GNFP_WALLET_PIN,
            "blurb": (
                f"$GNFP privacy wallet {GNFP_WALLET_PIN} on a chronoflux book. "
                "Session address is perpetual in your wallet."
            ),
            "release": f"{GNFP_REL}/tag/v{GNFP_WALLET_PIN}",
            "hrefs": (
                ("macOS", _gnfp_href(f"gnfp-wallet-{GNFP_WALLET_PIN}-macos.zip")),
                ("iPhone", _gnfp_href(f"gnfp-wallet-{GNFP_WALLET_PIN}-ios.ipa")),
                ("iPad", _gnfp_href(f"gnfp-wallet-{GNFP_WALLET_PIN}-ipad.ipa")),
                ("Arch", _gnfp_href(f"gnfp-wallet-{GNFP_WALLET_PIN}-archlinux.zip")),
            ),
        },
        {
            "id": "evolve",
            "name": "Evolve",
            "version": EVOLVE_PIN,
            "blurb": (
                f"Evolve {EVOLVE_PIN} — the suite that builds. Installers for "
                "every desktop and phone we currently ship."
            ),
            "release": f"{EVOLVE_REL}/tag/v{EVOLVE_PIN}",
            "hrefs": (
                ("Windows", _evolve_href(f"evolve-v{EVOLVE_PIN}-windows-x64-setup.exe")),
                ("macOS", _evolve_href(f"evolve-v{EVOLVE_PIN}-macos-x64.zip")),
                ("Linux", _evolve_href(f"evolve-v{EVOLVE_PIN}-linux-x64.tar.gz")),
                ("Android", _evolve_href(f"evolve-v{EVOLVE_PIN}-android-setup.apk")),
                ("iOS", _evolve_href(f"evolve-v{EVOLVE_PIN}-ios-setup.ipa")),
                ("Arch", _evolve_href(f"evolve-v{EVOLVE_PIN}-archlinux-x86_64.pkg.tar.zst")),
            ),
        },
    )


PORT_1474_BENEFITS: tuple[tuple[str, str], ...] = (
    (
        "rpAI control plane",
        "This host talks only to GOD, Grokbot, NED, FRED, and PEDRO. No shop "
        "checkout, no KEYGEN form, no ticket queue on this surface.",
    ),
    (
        "Learn-from-input ingest",
        "Questions, /goal briefs, and observe lines land here. Each agent "
        "gets its own part. The same product plus action does not grow twice.",
    ),
    (
        "Output feed",
        "GET /api/rpai lists learned counts, last lines, and recent parts so "
        "evolve.restoreprivacy.online can stay in step.",
    ),
    (
        "Beside mineperc, not mining",
        "Perc BeamHash lives on 1466. GOD is this page plus the $GNFP "
        "stratum on 1474. Opening 1474 does not read tunnel payloads.",
    ),
    (
        "Grok Build channel",
        "Press Build after a brief. The four agents take that brief; the "
        "CLI box stays on this page until an installer is sealed.",
    ),
    (
        "Quiet when closed",
        "If the stratum port is shut, HTTPS still serves this page. Opening "
        "the port adds ingest — it is not a second chatbot.",
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
  <p class="hint">Need a human? Mail <strong>{html.escape(inbox)}</strong>. We will not ask for KEYGENs, cards, or passwords.</p>
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
#god-hub { margin: 0 0 1.2rem; }
#god-hub-title { margin: 0 0 0.4rem; color: #00e5ff; letter-spacing: 0.04em; }
.god-hub-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
  gap: 0.85rem;
  margin: 0.75rem 0 0;
}
.god-hub-card h3 { margin: 0 0 0.35rem; color: #00e5ff; }
.god-hub-card .god-hub-ver { color: #00e5ff; font-weight: 750; }
.god-hub-links { display: flex; flex-wrap: wrap; gap: 0.4rem 0.65rem; margin: 0.55rem 0 0; padding: 0; list-style: none; }
.god-hub-links a { color: #00e5ff; font-weight: 700; }
#god-hub-menu {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem 1rem;
  margin: 0 0 0.85rem;
  padding: 0.55rem 0.75rem;
  list-style: none;
  border: 1px solid #2694e8;
  background: #14171c;
}
#god-hub-menu a {
  color: #00e5ff;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-decoration: none;
  text-transform: uppercase;
}
#god-hub-menu a:hover { text-decoration: underline; }
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


def render_god_hub_menu_html() -> str:
    items = "".join(
        f'<li><a href="{html.escape(href, quote=True)}" '
        f'data-hub-menu="{html.escape(label, quote=True)}">'
        f"{html.escape(label)}</a></li>"
        for label, href in hub_menu_links()
    )
    return (
        f'<nav class="god-hub-menu" id="god-hub-menu" aria-label="Restore Privacy">'
        f"{items}</nav>"
    )


def render_god_hub_html() -> str:
    """Prominent VPN / GNFP / Evolve installer block."""
    cards = []
    for product in hub_products():
        links = "".join(
            f'<li><a href="{html.escape(href, quote=True)}" '
            f'data-hub-installer="{html.escape(product["id"], quote=True)}" '
            f'data-hub-platform="{html.escape(label, quote=True)}">'
            f"{html.escape(label)}</a></li>"
            for label, href in product["hrefs"]
        )
        cards.append(
            f'<article class="panel-card god-hub-card" id="god-hub-{html.escape(product["id"])}" '
            f'data-hub-product="{html.escape(product["id"])}">'
            f'<h3>{html.escape(product["name"])}</h3>'
            f'<p class="god-hub-ver">v{html.escape(product["version"])}</p>'
            f'<p class="hint">{html.escape(product["blurb"])}</p>'
            f'<p class="hint"><a href="{html.escape(product["release"], quote=True)}">'
            f"All current packages</a></p>"
            f'<ul class="god-hub-links">{links}</ul></article>'
        )
    return (
        '<section class="panel-card" id="god-hub" data-god-hub="1">'
        "<h2 id=\"god-hub-title\">Start here</h2>"
        '<p class="hint" id="god-hub-lead">Three Restore Privacy products, '
        "current installers. Pick the package for the machine you are on.</p>"
        f"{render_god_hub_menu_html()}"
        f'<div class="god-hub-grid" id="god-hub-grid">{"".join(cards)}</div>'
        "</section>"
    )


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
        title=GOD_PAGE_TITLE,
        extra_css=god_rpai_css(),
    )
    header = public_brand_header_html(
        active=None,
        include_site_nav=False,
        include_theme_picker=False,
        banner_src=GOD_BANNER_SRC,
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
        recent = '<li class="ned-learned-empty">Nothing learned yet.</li>'
    hub = render_god_hub_html()
    return f"""{head}
  <div class="page-shell" id="god-rpai-shell" data-page="god-rpai" data-god-port="{GOD_RPAI_PORT}">
{header}
<main class="support-wrap panel-card" id="god-rpai-main" data-chrome="pro" data-rpai-surface="1">
  <p class="support-lead" id="god-rpai-lead">{html.escape(HIERARCHY["line"])}</p>
  {hub}
  <section class="panel-card" id="god-port-box">
    <h3>god.restoreprivacy.online:{GOD_RPAI_PORT}</h3>
    <p class="hint">HTTPS is this page. Port {GOD_RPAI_PORT} is the $GNFP BeamHash III
    CPU stratum — proof of work only, miner tags hashed, no public user info.
    <a href="/gnfp">$GNFP pool</a> ·
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
    <pre id="god-cli" aria-live="polite">idle — press Build. Remain here until the installer is sealed.</pre>
    <p class="hint" id="god-cli-stay">Evolve Suite is the surface. The four agents have the brief.</p>
    <a id="god-cli-download" class="btn" href="#">Download installer</a>
  </section>
  <section class="panel-card" id="god-input-box">
    <h3>Learn from input</h3>
    <p class="hint">A public observation becomes a distinct action. Secrets are refused.</p>
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
