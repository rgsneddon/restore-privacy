"""Dedicated GOD · rpAI page (god.restoreprivacy.online[:1474]).

GNFP coin landing first (what / mine / wallet / explorer / links /
community), then the AI Oracle and Evolve dashboard. Not the shop, not a
ticket form, not Perc mining. Grokbot (Grok Build) chaperones; GOD leads.

Port 1474 sits beside mineperc :1466 as the $GNFP BeamHash III stratum —
it is not Beam :1974 and not a VPN dataplane.
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
GNFP_WALLET_PIN = "0.0.6"
EVOLVE_PIN = "4.2.1"

VPN_FREE = "https://restoreprivacy.online/suite/download?platform={platform}&free_direct=1"
GNFP_REL = "https://github.com/rgsneddon/gnfp-wallet/releases"
GNFP_POOL_HREF = "https://gnfp.restoreprivacy.online"
GNFP_EXPLORER_HREF = "https://explorer.restoreprivacy.online"
GNFP_MINE_HREF = "https://github.com/rgsneddon/gnfp-mine"
GNFP_BOOK = "de.restoreprivacy.online:1474"
GNFP_FRONT_SG = "sg.restoreprivacy.online:1474"
GNFP_FRONT_HEL = "hel.restoreprivacy.online:1474"
GNFP_DISCORD_HREF = "https://discord.gg/H9TdGyCUCa"
GNFP_TELEGRAM_HREF = "https://t.me/gnfp1"
GNFP_ANN_HREF = "https://bitcointalk.org/index.php?topic=5591310.0"
EVOLVE_REL = "https://github.com/rgsneddon/evolve/releases"


def _vpn_href(platform: str) -> str:
    return VPN_FREE.format(platform=platform)


def _gnfp_href(filename: str, pin: str | None = None) -> str:
    ver = str(pin or GNFP_WALLET_PIN).strip().lstrip("v")
    return f"{GNFP_REL}/download/v{ver}/{filename}"


def _evolve_href(filename: str) -> str:
    return f"{EVOLVE_REL}/download/v{EVOLVE_PIN}/{filename}"


def _gnfp_publisher():
    try:
        from downloads import (
            GNFP_WALLET_RELEASES,
            gnfp_wallet_asset_href,
            latest_gnfp_wallet_pin_with_windows,
            list_gnfp_wallet_hub_hrefs,
        )
    except ImportError:  # pragma: no cover
        from status_page.downloads import (  # type: ignore
            GNFP_WALLET_RELEASES,
            gnfp_wallet_asset_href,
            latest_gnfp_wallet_pin_with_windows,
            list_gnfp_wallet_hub_hrefs,
        )
    return (
        GNFP_WALLET_RELEASES,
        gnfp_wallet_asset_href,
        latest_gnfp_wallet_pin_with_windows,
        list_gnfp_wallet_hub_hrefs,
    )


def gnfp_wallet_hub_product(
    *, inventory_path: Any = None, releases: list | None = None
) -> dict[str, Any]:
    """GOD hub card for $GNFP privacy wallet — Windows href from shipped pin."""
    _rel, asset_href, latest_pin, list_hrefs = _gnfp_publisher()
    pin = latest_pin(releases, inventory_path=inventory_path) or GNFP_WALLET_PIN
    hrefs = list_hrefs(releases, inventory_path=inventory_path)
    if not hrefs:
        hrefs = [
            ("Windows", asset_href(pin, f"gnfp-wallet-{pin}-windows.zip")),
            ("macOS", asset_href(pin, f"gnfp-wallet-{pin}-macos.zip")),
            ("Linux", asset_href(pin, f"gnfp-wallet-{pin}-linux.zip")),
            ("iPhone", asset_href(pin, f"gnfp-wallet-{pin}-ios.ipa")),
            ("iPad", asset_href(pin, f"gnfp-wallet-{pin}-ipad.ipa")),
            ("Arch", asset_href(pin, f"gnfp-wallet-{pin}-archlinux.zip")),
        ]
    return {
        "id": "gnfp",
        "name": "GNFP",
        "version": pin,
        "blurb": (
            f"$GNFP privacy wallet {pin} on a chronoflux book. "
            "Session address is perpetual in your wallet."
        ),
        "release": f"{_rel}/tag/v{pin}",
        "hrefs": tuple(hrefs),
    }


def render_god_wallet_hub_html(
    *, inventory_path: Any = None, releases: list | None = None
) -> str:
    product = gnfp_wallet_hub_product(
        inventory_path=inventory_path, releases=releases
    )
    links = "".join(
        f'<li><a href="{html.escape(href, quote=True)}" '
        f'data-hub-installer="gnfp" '
        f'data-hub-platform="{html.escape(label, quote=True)}">'
        f"{html.escape(label)}</a></li>"
        for label, href in product["hrefs"]
    )
    return (
        f'<article class="panel-card god-hub-card" id="god-hub-gnfp" '
        f'data-hub-product="gnfp">'
        f'<h3>{html.escape(product["name"])}</h3>'
        f'<p class="god-hub-ver">v{html.escape(product["version"])}</p>'
        f'<p class="hint">{html.escape(product["blurb"])}</p>'
        f'<ul class="god-hub-links">{links}</ul></article>'
    )


def hub_menu_links() -> tuple[tuple[str, str], ...]:
    """Visitor menu above the installer boxes. Evolve href is as specified."""
    return (
        ("GNFP POOL", GNFP_POOL_HREF),
        ("GNFP EXPLORER", GNFP_EXPLORER_HREF),
        ("RESTORE PRIVACY VPN", "https://www.restoreprivacy.online"),
        ("EVOLVE", "https://evolve.restoreprivacy.online"),
    )


def gnfp_official_links() -> tuple[tuple[str, str], ...]:
    """Live public GNFP destinations — pool, explorer, wallet first."""
    return (
        ("Pool", GNFP_POOL_HREF),
        ("Explorer", GNFP_EXPLORER_HREF),
        ("Wallet", GNFP_REL),
        ("Miner", GNFP_MINE_HREF),
        ("Bitcointalk ANN", GNFP_ANN_HREF),
    )


def gnfp_community_links() -> tuple[tuple[str, str], ...]:
    """Real invites from the live Bitcointalk ANN. Do not invent extras."""
    return (
        ("Discord", GNFP_DISCORD_HREF),
        ("Telegram", GNFP_TELEGRAM_HREF),
    )


def hub_products() -> tuple[dict[str, Any], ...]:
    """Current public installer set. GNFP lists Windows when that zip exists."""
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
        gnfp_wallet_hub_product(),
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


def render_gnfp_intro_html(
    *, inventory_path: Any = None, releases: list | None = None
) -> str:
    """GNFP coin landing: what / mine / wallet / explorer / links / community."""
    product = gnfp_wallet_hub_product(
        inventory_path=inventory_path, releases=releases
    )
    wallet_links = "".join(
        f'<li><a href="{html.escape(href, quote=True)}" '
        f'data-gnfp-wallet="{html.escape(label, quote=True)}">'
        f"{html.escape(label)}</a></li>"
        for label, href in product["hrefs"]
    )
    official = "".join(
        f'<li><a href="{html.escape(href, quote=True)}" '
        f'data-gnfp-official="{html.escape(label, quote=True)}">'
        f"{html.escape(label)}</a></li>"
        for label, href in gnfp_official_links()
    )
    community = "".join(
        f'<li><a href="{html.escape(href, quote=True)}" '
        f'data-gnfp-community="{html.escape(label, quote=True)}">'
        f"{html.escape(label)}</a></li>"
        for label, href in gnfp_community_links()
    )
    pin = html.escape(str(product["version"]))
    book = html.escape(GNFP_BOOK)
    front_sg = html.escape(GNFP_FRONT_SG)
    front_hel = html.escape(GNFP_FRONT_HEL)
    mine_href = html.escape(GNFP_MINE_HREF, quote=True)
    wallet_rel = html.escape(GNFP_REL, quote=True)
    explorer_href = html.escape(GNFP_EXPLORER_HREF, quote=True)
    pool_href = html.escape(GNFP_POOL_HREF, quote=True)
    return f"""
<section class="gnfp-intro" id="gnfp-intro" data-gnfp-intro="1">
  <p class="gnfp-skip"><a href="#god-oracle-evolve">Skip to AI Oracle · Evolve</a></p>
  <header class="gnfp-hero" id="gnfp-hero">
    <p class="gnfp-kicker" id="gnfp-kicker"><span class="gnfp-pulse" aria-hidden="true"></span>
      $GNFP · BeamHash III · CPU only</p>
    <h1 id="gnfp-intro-title">GNFP</h1>
    <p class="gnfp-tagline" id="gnfp-intro-lead">God's coin. Private by default.
      Chronoflux underneath. Proof of work only — no stake, no masternodes,
      no ICO. You hash. You get GNFP. Nobody else needs your name.</p>
  </header>
  <div class="gnfp-section-grid" id="gnfp-section-grid">
    <article class="gnfp-card" id="gnfp-what" data-gnfp-section="what">
      <p class="gnfp-step">01</p>
      <h2>What it is</h2>
      <p><strong>$GNFP</strong> is a CPU-mined privacy coin on
      <strong>BeamHash III</strong>. Addresses start with
      <code>gnfp1</code>. Spendable GNFP lives on those addresses; the
      public pages show hashes, not wallets, IPs, or logins.</p>
      <ul class="gnfp-facts">
        <li><span>Ticker</span> GNFP</li>
        <li><span>Privacy</span> Private by default</li>
        <li><span>Architecture</span> Chronoflux</li>
        <li><span>Consensus</span> PoW only</li>
      </ul>
    </article>
    <article class="gnfp-card" id="gnfp-mining" data-gnfp-section="mining">
      <p class="gnfp-step">02</p>
      <h2>How mining works</h2>
      <p>Point <a href="{mine_href}">gnfp-mine</a> at the Germany book.
      CPU workers only — GPU-shaped 208-hex / 104-byte solutions are
      refused. A valid hash pays 1 micro (0.00000001 GNFP). Each block
      is a 1 GNFP pot, split by who actually hashed.</p>
      <pre class="gnfp-cmd" id="gnfp-mine-cmd">gnfp-mine --pool {book} --user gnfp1YOURADDRESS.worker --threads 8</pre>
      <p class="hint">Book <code>{book}</code> (plain TCP, no TLS).
      Fronts <code>{front_sg}</code> · <code>{front_hel}</code>.</p>
    </article>
    <article class="gnfp-card" id="gnfp-wallet" data-gnfp-section="wallet">
      <p class="gnfp-step">03</p>
      <h2>Wallet</h2>
      <p>You are a seed and a <code>gnfp1</code>. The session address is
      perpetual in your wallet. Current pin <strong>v{pin}</strong> —
      Windows, macOS, Linux, iPhone, iPad.</p>
      <p class="hint"><a href="{wallet_rel}">All wallet releases</a></p>
      <ul class="gnfp-chip-links" id="gnfp-wallet-links">{wallet_links}</ul>
    </article>
    <article class="gnfp-card" id="gnfp-explorer" data-gnfp-section="explorer">
      <p class="gnfp-step">04</p>
      <h2>Explorer</h2>
      <p>Glance, don't decode: height, nodes online, hashrate, difficulty,
      block ETA, last transfers, coins in circulation. Top holders are
      <code>party-xxxxxxxx</code> tags. That is all public. Your
      <code>gnfp1</code> is not.</p>
      <p><a class="gnfp-go" href="{explorer_href}">Open the explorer</a>
      · <a href="{pool_href}">Open the pool</a></p>
    </article>
  </div>
  <nav class="gnfp-official" id="gnfp-official-links" data-gnfp-links="1" aria-label="GNFP official links">
    <h2>Official links</h2>
    <ul class="gnfp-chip-links">{official}</ul>
  </nav>
  <aside class="gnfp-community" id="gnfp-community" data-gnfp-community="1">
    <h2>Community</h2>
    <p>Questions, rants, and miner talk live on Discord. Telegram is
    the same crowd on the other door. No email form on this page.</p>
    <ul class="gnfp-chip-links gnfp-community-links">{community}</ul>
  </aside>
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
  justify-content: center;
  text-align: center;
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
#theme-mode-control, .theme-mode-control { display: none !important; }
#gnfp-intro {
  position: relative;
  overflow: hidden;
  margin: 0 0 1.6rem;
  padding: 1.15rem 1.05rem 1.3rem;
  border: 1px solid #2694e8;
  background:
    radial-gradient(ellipse 80% 50% at 8% -8%, rgba(0,229,255,0.16), transparent 55%),
    radial-gradient(ellipse 46% 36% at 100% 0%, rgba(57,255,106,0.08), transparent 50%),
    linear-gradient(180deg, #161a20 0%, #101217 100%);
  box-shadow: 0 0 28px rgba(0, 229, 255, 0.12);
}
#gnfp-intro::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.16;
  background-image:
    linear-gradient(rgba(0,229,255,0.18) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,229,255,0.18) 1px, transparent 1px);
  background-size: 26px 26px;
  mask-image: linear-gradient(180deg, #000 0%, transparent 80%);
}
#gnfp-intro > * { position: relative; z-index: 1; }
.gnfp-skip { margin: 0 0 0.55rem; }
.gnfp-skip a { color: #9aa8b5; font-size: 0.82rem; font-weight: 700; }
.gnfp-hero { text-align: center; margin: 0 0 1.05rem; }
.gnfp-kicker {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  margin: 0 0 0.55rem;
  padding: 0.28rem 0.7rem;
  border: 1px solid rgba(0,229,255,0.45);
  background: rgba(0,229,255,0.08);
  color: #00e5ff;
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}
.gnfp-pulse {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 50%;
  background: #39ff6a;
  box-shadow: 0 0 10px #39ff6a;
  animation: gnfp-pulse 1.6s ease-in-out infinite;
}
@keyframes gnfp-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.45; transform: scale(0.78); }
}
#gnfp-intro-title {
  margin: 0.15rem 0 0.4rem;
  color: #00e5ff;
  font-size: clamp(2.4rem, 7vw, 4.2rem);
  font-weight: 900;
  letter-spacing: 0.14em;
  text-shadow: 0 0 22px rgba(0,229,255,0.55);
}
.gnfp-tagline {
  margin: 0 auto;
  max-width: 40rem;
  color: #c8d4de;
  line-height: 1.5;
  font-size: 1.02rem;
}
.gnfp-section-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.85rem;
  margin: 0 0 1rem;
}
@media (min-width: 48rem) {
  .gnfp-section-grid { grid-template-columns: 1fr 1fr; }
}
.gnfp-card {
  margin: 0;
  padding: 0.85rem 0.9rem 0.95rem;
  border: 1px solid #2694e8;
  background: rgba(20, 23, 28, 0.82);
  box-shadow: 0 0 16px rgba(0, 229, 255, 0.08);
}
.gnfp-card h2 {
  margin: 0 0 0.4rem;
  color: #00e5ff;
  letter-spacing: 0.04em;
  font-size: 1.08rem;
}
.gnfp-step {
  margin: 0 0 0.2rem;
  color: #39ff6a;
  font-weight: 800;
  letter-spacing: 0.16em;
  font-size: 0.72rem;
}
.gnfp-facts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.35rem 0.6rem;
  margin: 0.7rem 0 0;
  padding: 0;
  list-style: none;
}
.gnfp-facts li {
  padding: 0.35rem 0.45rem;
  border: 1px solid rgba(38,148,232,0.45);
  background: #14171c;
  font-weight: 700;
}
.gnfp-facts span {
  display: block;
  color: #9aa8b5;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.gnfp-cmd {
  margin: 0.65rem 0 0.45rem;
  padding: 0.6rem 0.7rem;
  overflow-x: auto;
  background: #2b2b2b;
  color: #00e5ff;
  font-weight: 700;
  font-family: ui-monospace, Consolas, "Cascadia Code", monospace;
  font-size: 0.78rem;
  line-height: 1.4;
  white-space: pre-wrap;
  box-shadow: 0 0 12px rgba(0, 229, 255, 0.16);
}
.gnfp-chip-links {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 0.55rem;
  margin: 0.55rem 0 0;
  padding: 0;
  list-style: none;
}
.gnfp-chip-links a, .gnfp-go {
  display: inline-block;
  padding: 0.32rem 0.65rem;
  border: 1px solid #00e5ff;
  background: #14171c;
  color: #00e5ff;
  font-weight: 800;
  text-decoration: none;
  letter-spacing: 0.03em;
}
.gnfp-chip-links a:hover, .gnfp-go:hover {
  background: rgba(0,229,255,0.12);
  text-shadow: 0 0 8px rgba(0,229,255,0.85);
}
.gnfp-official, .gnfp-community {
  margin: 0.85rem 0 0;
  padding: 0.75rem 0.85rem;
  border: 1px solid #2694e8;
  background: #14171c;
}
.gnfp-official h2, .gnfp-community h2 {
  margin: 0 0 0.35rem;
  color: #00e5ff;
  letter-spacing: 0.05em;
  font-size: 1.02rem;
}
.gnfp-community-links a[data-gnfp-community="Discord"] {
  border-color: #39ff6a;
  color: #39ff6a;
}
#god-oracle-evolve { margin: 0 0 0.4rem; }
#god-oracle-kicker {
  margin: 0 0 0.35rem;
  color: #00e5ff;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-size: 0.76rem;
}
#god-oracle-title {
  margin: 0 0 0.35rem;
  color: #00e5ff;
  letter-spacing: 0.04em;
}
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
        f"{render_god_hub_menu_html()}"
        "<h2 id=\"god-hub-title\">VPN · Wallet · Evolve</h2>"
        '<p class="hint" id="god-hub-lead">The rest of the Restore Privacy '
        "suite — current installers for the machine you are on.</p>"
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
    except ImportError:  # pragma: no cover
        from status_page.god_support import render_god_support_box_html  # type: ignore
        from status_page.goal_builder import render_goal_builder_box_html  # type: ignore

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
    intro = render_gnfp_intro_html()
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
  {intro}
  <section class="panel-card" id="god-oracle-evolve" data-god-oracle="1">
    <p class="gnfp-kicker" id="god-oracle-kicker">After the coin</p>
    <h2 id="god-oracle-title">AI Oracle · Evolve</h2>
    <p class="hint" id="god-oracle-lead">Ask GOD, build a goal, and watch the
    four agents learn. This is the rpAI dashboard — the coin is above.</p>
  </section>
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
</main>
  </div>
<script src="/static/god_rpai.js" defer></script>
<script src="/static/god_build.js" defer></script>
{close}
"""
