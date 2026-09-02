"""Dedicated GOD · rpAI page (god.restoreprivacy.online[:1474]).

GNFP-only landing: wallet, CPU mining, pool and explorer. Not Shear.
Not the shop, not a ticket form, not Perc mining.

Port 1474 sits beside mineperc :1466 as the $GNFP book stratum —
it is not Beam :1974 and not a VPN dataplane.
"""

from __future__ import annotations

import html
import json
from typing import Any, Callable

GOD_RPAI_HOST = "god.restoreprivacy.online"
GOD_MIRROR_HOSTS = ()
GOD_RPAI_PORT = 1474  # public: $GNFP BeamHash III stratum (perc miner)
GOD_HTTP_PORT = 8013  # loopback: dedicated GOD · rpAI page
GOD_RPAI_PATH = "/god"
GOD_LEARN_PATH = "/api/learn"
GOD_RPAI_API = "/api/rpai"
# Only apex restoreprivacy.online map href allowed on this host (god. /downloads-map 404s).
GOD_DOWNLOADS_MAP_HREF = "https://restoreprivacy.online/downloads-map"
GOD_PAGE_TITLE = "GOD · Restore Privacy"
GOD_BANNER_SRC = "/static/bannerall.jpg"
GOD_BANNER_FILE = "bannerall.jpg"
SHEAR_BANNER_LIGHT = "/static/bannerall.jpg"
SHEAR_BANNER_DARK = "/static/bannerall.jpg"
SHEAR_WORDMARK_LIGHT = "/static/shear-wordmark-light.png"
SHEAR_WORDMARK_DARK = "/static/shear-wordmark-dark.png"
SHEAR_SITE_HREF = "https://shear.digital"
SHEAR_POOL_HREF = "https://pool.shear.digital"
SHEAR_EXPLORER_HREF = "https://explorer.shear.digital"
SHEAR_WALLET_REL = "https://github.com/rgsneddon/shear-testnet/releases"
SHEAR_WALLET_PIN = "0.11"
SHEAR_WALLET_TAG = "0.11"

VPN_CATALOG_VERSION = "1.2.7"
GNFP_WALLET_PIN = "0.2.6"
EVOLVE_PIN = "4.2.1"

VPN_FREE = "https://restoreprivacy.online/suite/download?platform={platform}&free_direct=1"
GNFP_REL = "https://github.com/rgsneddon/gnfp-wallet/releases"
GNFP_POOL_HREF = "https://gnfp.restoreprivacy.online"
GNFP_EXPLORER_HREF = "https://explorer.restoreprivacy.online"
GNFP_MINE_HREF = "https://github.com/rgsneddon/GNFPHash"
GNFP_BOOK = "de.restoreprivacy.online:1474"
GNFP_FRONT_SG = "sg.restoreprivacy.online:1474"
GNFP_FRONT_HEL = "hel.restoreprivacy.online:1474"
GNFP_DISCORD_HREF = "https://discord.gg/H9TdGyCUCa"
GNFP_TELEGRAM_HREF = "https://t.me/gnfp1"
GNFP_ANN_HREF = "https://bitcointalk.org/index.php?topic=5591310.0"
EVOLVE_REL = "https://github.com/rgsneddon/evolve/releases"

# Same-origin how-to paths served on the GOD host (and mirrored as public docs).
GNFP_PRIVACY_HOWTO_PATH = "/howto/gnfp-privacy"
GNFP_CPU_MINE_HOWTO_PATH = "/howto/gnfp-cpu-mine"

GNFP_HOWTO_GUIDES: tuple[dict[str, Any], ...] = (
    {
        "id": "privacy",
        "path": GNFP_PRIVACY_HOWTO_PATH,
        "title": "How to keep miner identity hashed",
        "lead": (
            "Recent book commits keep miner identities hashed. Public glance "
            "pages never publish IPs, wallets, or logins."
        ),
        "steps": (
            "Point gnfp-mine at the book. The pool stores a hashed miner tag "
            "(miner-xxxxxxxx), not your name and not your gnfp1.",
            "Public pages — this GOD surface, the pool, the explorer — show "
            "hashed identities only. Holder rows are party-xxxxxxxx tags.",
            "There are no IPs, wallets, or logins on public pages. Do not "
            "paste a gnfp1 or a login into a public form; this page has none.",
            "Keep the seed and session address in the wallet. Spendable GNFP "
            "stays on gnfp1; the book never lists that address in the open.",
        ),
    },
    {
        "id": "cpu-mine",
        "path": GNFP_CPU_MINE_HOWTO_PATH,
        "title": "How to CPU-mine with gnfp-mine",
        "lead": (
            "The book credits only the gnfp-mine CPU work-hash path. GPU-shaped "
            "solutions are refused. TLS is the default. --threads is capped at 256."
        ),
        "steps": (
            "Install gnfp-mine and run it against the Germany book. TLS by "
            "default — do not switch the book to plain TCP: "
            "gnfp-mine --pool de.restoreprivacy.online:1474 "
            "--user gnfp1YOURADDRESS.worker --threads 8",
            "Stay on the CPU-only gnfp-mine work-hash path. A valid CPU hash "
            "pays 1 micro (0.00000001 GNFP).",
            "GPU-shaped 208-hex / 104-byte solutions are refused. GPU solvers "
            "are not credited (GPU refused).",
            "--threads starts real CPU workers and is capped at 256. Use the "
            "hashrate box on this page to read expected H/s from 1 to 256 threads.",
        ),
    },
)


def _vpn_href(platform: str) -> str:
    return VPN_FREE.format(platform=platform)


def _gnfp_href(filename: str, pin: str | None = None) -> str:
    ver = str(pin or GNFP_WALLET_PIN).strip().lstrip("v")
    return f"{GNFP_REL}/download/v{ver}/{filename}"


def _shear_wallet_href(filename: str, pin: str | None = None) -> str:
    ver = str(pin or SHEAR_WALLET_PIN).strip().lstrip("v")
    tag = SHEAR_WALLET_TAG if ver == SHEAR_WALLET_PIN else f"v{ver}"
    return f"{SHEAR_WALLET_REL}/download/{tag}/{filename}"


def _public_join_wallet_hrefs(hrefs: list | tuple) -> list[tuple[str, str]]:
    """Wallet chips: current pin, macOS dmg over zip, no iOS."""
    rows = [(str(label), str(href)) for label, href in hrefs]
    has_dmg = any(href.lower().endswith("-macos.dmg") for _label, href in rows)
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for label, href in rows:
        low = href.lower()
        if "ios.ipa" in low or "ipad.ipa" in low:
            continue
        if has_dmg and low.endswith("-macos.zip"):
            continue
        key = low.rsplit("/", 1)[-1]
        if key in seen:
            continue
        seen.add(key)
        if low.endswith("-macos.dmg"):
            label = "macOS"
        out.append((label, href))
    return out


def _evolve_href(filename: str) -> str:
    return f"{EVOLVE_REL}/download/v{EVOLVE_PIN}/{filename}"


def _inventory_publisher():
    try:
        from downloads import (
            EVOLVE_REPO,
            GNFP_WALLET_RELEASES,
            GNFP_WALLET_REPO,
            RELEASE_VERSION,
            gnfp_wallet_asset_href,
            github_release_href,
            latest_repo_pin,
            list_gnfp_wallet_hub_hrefs,
            list_repo_hub_hrefs,
        )
    except ImportError:  # pragma: no cover
        from status_page.downloads import (  # type: ignore
            EVOLVE_REPO,
            GNFP_WALLET_RELEASES,
            GNFP_WALLET_REPO,
            RELEASE_VERSION,
            gnfp_wallet_asset_href,
            github_release_href,
            latest_repo_pin,
            list_gnfp_wallet_hub_hrefs,
            list_repo_hub_hrefs,
        )
    return {
        "evolve_repo": EVOLVE_REPO,
        "gnfp_rel": GNFP_WALLET_RELEASES,
        "gnfp_repo": GNFP_WALLET_REPO,
        "catalog": RELEASE_VERSION,
        "gnfp_href": gnfp_wallet_asset_href,
        "asset_href": github_release_href,
        "latest_pin": latest_repo_pin,
        "gnfp_hrefs": list_gnfp_wallet_hub_hrefs,
        "repo_hrefs": list_repo_hub_hrefs,
    }


def vpn_hub_product() -> dict[str, Any]:
    """VPN card — version follows the live suite catalog, not a GitHub tag."""
    pub = _inventory_publisher()
    ver = str(pub["catalog"] or VPN_CATALOG_VERSION)
    return {
        "id": "vpn",
        "name": "Restore Privacy VPN",
        "version": ver,
        "blurb": (
            "Residual VPN client, catalog "
            f"{ver}. Download is free; Connect uses a "
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
    }


def gnfp_wallet_hub_product(
    *, inventory_path: Any = None, releases: list | None = None
) -> dict[str, Any]:
    """GOD hub card for $GNFP privacy wallet — latest published pin."""
    pub = _inventory_publisher()
    pin = (
        pub["latest_pin"](
            pub["gnfp_repo"], releases, inventory_path=inventory_path
        )
        or GNFP_WALLET_PIN
    )
    hrefs = pub["gnfp_hrefs"](releases, inventory_path=inventory_path)
    if not hrefs:
        hrefs = [
            ("macOS", pub["gnfp_href"](pin, f"gnfp-wallet-{pin}-macos.dmg")),
            ("Android", pub["gnfp_href"](pin, f"gnfp-wallet-{pin}-android.apk")),
            ("Windows", pub["gnfp_href"](pin, f"gnfp-wallet-{pin}-windows.zip")),
            ("Linux", pub["gnfp_href"](pin, f"gnfp-wallet-{pin}-linux.zip")),
        ]
    return {
        "id": "gnfp",
        "name": "GNFP",
        "version": pin,
        "blurb": (
            f"$GNFP privacy wallet {pin} on a chronoflux book. "
            "Session address is perpetual in your wallet."
        ),
        "release": f"{pub['gnfp_rel']}/tag/v{pin}",
        "hrefs": tuple(hrefs),
    }


def evolve_hub_product(
    *, inventory_path: Any = None, releases: list | None = None
) -> dict[str, Any]:
    """GOD hub card for Evolve — latest published pin from inventory."""
    pub = _inventory_publisher()
    pin = (
        pub["latest_pin"](
            pub["evolve_repo"], releases, inventory_path=inventory_path
        )
        or EVOLVE_PIN
    )
    hrefs = pub["repo_hrefs"](
        pub["evolve_repo"], releases, inventory_path=inventory_path, pin=pin
    )
    if not hrefs:
        hrefs = [
            ("Windows", _evolve_href(f"evolve-v{pin}-windows-x64-setup.exe")),
            ("macOS", _evolve_href(f"evolve-v{pin}-macos-x64.zip")),
            ("Linux", _evolve_href(f"evolve-v{pin}-linux-x64.tar.gz")),
            ("Android", _evolve_href(f"evolve-v{pin}-android-setup.apk")),
            ("iOS", _evolve_href(f"evolve-v{pin}-ios-setup.ipa")),
            ("Arch", _evolve_href(f"evolve-v{pin}-archlinux-x86_64.pkg.tar.zst")),
        ]
    return {
        "id": "evolve",
        "name": "Evolve",
        "version": pin,
        "blurb": (
            f"Evolve {pin} — the suite that builds. Installers for "
            "every desktop and phone we currently ship."
        ),
        "release": f"{EVOLVE_REL}/tag/v{pin}",
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
    """Current public installer set from live inventory / suite catalog."""
    return (
        vpn_hub_product(),
        gnfp_wallet_hub_product(),
        evolve_hub_product(),
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
    return (
        raw == GOD_RPAI_HOST
        or raw.startswith("god.")
        or raw in GOD_MIRROR_HOSTS
    )


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


def render_shear_god_header_html() -> str:
    """GOD / GNFP banner. Not a Shear surface."""
    src = html.escape(GOD_BANNER_SRC, quote=True)
    return f"""
<div class="gnfp-hero" id="gnfp-hero" data-gnfp-banner="1">
  <img class="theme-img-light" alt="$GNFP" src="{src}"/>
  <img class="theme-img-dark" alt="" src="{src}"/>
</div>
"""


def render_gnfp_intro_html(
    *, inventory_path: Any = None, releases: list | None = None
) -> str:
    """GNFP-only landing: wallet, CPU mining, pool, explorer."""
    product = gnfp_wallet_hub_product(
        inventory_path=inventory_path, releases=releases
    )
    wallet_links = "".join(
        f'<li><a href="{html.escape(href, quote=True)}" '
        f'data-gnfp-wallet="{html.escape(label, quote=True)}">'
        f"{html.escape(label)}</a></li>"
        for label, href in _public_join_wallet_hrefs(product["hrefs"])
    )
    pin = html.escape(str(product["version"]))
    pool = html.escape(GNFP_POOL_HREF, quote=True)
    explorer = html.escape(GNFP_EXPLORER_HREF, quote=True)
    mine = html.escape(GNFP_MINE_HREF, quote=True)
    wallet_rel = html.escape(GNFP_REL, quote=True)
    book = html.escape(GNFP_BOOK)
    sg = html.escape(GNFP_FRONT_SG)
    discord = html.escape(GNFP_DISCORD_HREF, quote=True)
    telegram = html.escape(GNFP_TELEGRAM_HREF, quote=True)
    return f"""
<section class="gnfp-intro" id="gnfp-intro" data-gnfp-intro="1">
  <div class="gnfp-box-stack" id="gnfp-box-stack">
    <article class="gnfp-box" id="gnfp-ann-box" data-gnfp-box="ann">
      <p class="gnfp-kicker"><span class="gnfp-pulse" aria-hidden="true"></span>
        $GNFP</p>
      <h1 id="gnfp-intro-title">GNFP — God's coin</h1>
      <p class="gnfp-lede">Private by default. CPU work. One chain. Addresses start with <code>gnfp1</code>. You hash, or you are paid by someone who already holds coin.</p>
      <p>Each valid hash pays <strong>1 micro</strong> (0.00000001 GNFP). Each block closes a <strong>1 GNFP</strong> pot, split by who actually hashed that round. GPU-shaped solutions mint nothing.</p>
      <p><strong>Official places:</strong> <a href="{pool}">gnfp.restoreprivacy.online</a> · <a href="{explorer}">explorer.restoreprivacy.online</a> · book <code>{book}</code> (TLS)</p>
      <p>Discord <a href="{discord}">discord.gg/H9TdGyCUCa</a> · Telegram <a href="{telegram}">t.me/gnfp1</a></p>
    </article>
    <article class="gnfp-box" id="gnfp-wallet-box" data-gnfp-box="wallet">
      <p class="gnfp-kicker"><span class="gnfp-pulse" aria-hidden="true"></span>
        Wallet</p>
      <h2 id="gnfp-wallet-title">Install the GNFP wallet</h2>
      <p class="gnfp-lede">Current pin is <strong>v{pin}</strong>. Same <code>gnfp1</code> as before. Keep your twelve-word backup offline. This app does not mine.</p>
      <ol class="gnfp-howto-steps">
        <li>Download from <a href="{wallet_rel}">the official GNFP wallet releases</a> only. macOS: open the disk image, drag the app onto Applications, eject, then launch from Applications.</li>
        <li>Windows or Linux: unzip and open the app. Android: install the APK. Uninstall an older debug-signed build first if the phone already has one.</li>
        <li>Create or restore from your twelve English words. Your spendable address is a <code>gnfp1</code>. That is the login the miner uses.</li>
        <li>Receive and send on the live book. Do not send BEAM, PERC, or any other coin to a <code>gnfp1</code>.</li>
      </ol>
      <p class="hint"><a href="{wallet_rel}">GNFP wallet</a> · v{pin}</p>
      <ul class="gnfp-chip-links" id="gnfp-wallet-links">{wallet_links}</ul>
    </article>
    <article class="gnfp-box" id="gnfp-mine-box" data-gnfp-box="mine">
      <p class="gnfp-kicker"><span class="gnfp-pulse" aria-hidden="true"></span>
        Mine</p>
      <h2 id="gnfp-mine-title">CPU mine GNFP</h2>
      <p class="gnfp-lede">Official miner is <strong>GNFPHash</strong> / gnfp-cminer. Point it at Germany or Singapore. Leave TLS on. GPU and old miners earn nothing.</p>
      <ol class="gnfp-howto-steps">
        <li>Get the miner from <a href="{mine}">github.com/rgsneddon/GNFPHash</a>.</li>
        <li>Login is your <code>gnfp1</code>, a dot, then a worker name: <code>gnfp1YOURADDRESS.worker</code>.</li>
        <li>Germany: <code>{book}</code>. Singapore: <code>{sg}</code>. TLS is the default.</li>
        <li><code>--threads</code> starts real CPU workers. Cap is this machine’s threads, hard stop 256.</li>
      </ol>
      <p>Pool <a href="{pool}">gnfp.restoreprivacy.online</a> · Explorer <a href="{explorer}">explorer.restoreprivacy.online</a></p>
    </article>
  </div>
</section>
"""


def gnfp_howto_guides() -> tuple[dict[str, Any], ...]:
    """How-to copy the GOD renderer emits — privacy hash path + CPU harden."""
    return GNFP_HOWTO_GUIDES


def render_gnfp_hashrate_box_html(workers: Any = None) -> str:
    """Distinct GOD box: expected GNFP hashrate from 1 thread through 256."""
    try:
        from gnfp import (
            GNFP_HASHRATE_API,
            expected_hashrate_table,
            hashrate_table_payload,
            load_snapshot_workers,
        )
    except ImportError:  # pragma: no cover
        from status_page.gnfp import (  # type: ignore
            GNFP_HASHRATE_API,
            expected_hashrate_table,
            hashrate_table_payload,
            load_snapshot_workers,
        )
    if workers is not None:
        payload = hashrate_table_payload(
            workers=workers, store={}, record=True, persist=False
        )
    else:
        payload = hashrate_table_payload(record=True, persist=True)
    rows = list(payload.get("rows") or [])
    if not rows:
        rows = expected_hashrate_table(load_snapshot_workers())
    body = "".join(
        f'<tr data-threads="{int(row["threads"])}">'
        f'<td>{int(row["threads"])} '
        f'{"thread" if int(row["threads"]) == 1 else "threads"}</td>'
        f'<td data-hashrate-expected="{int(row["threads"])}">'
        f'{html.escape(str(row["expected"]))}</td></tr>'
        for row in rows
    )
    api = html.escape(GNFP_HASHRATE_API, quote=True)
    return f"""
<section class="panel-card gnfp-hashrate-box" id="gnfp-hashrate-box" data-gnfp-hashrate="1" data-hashrate-live="1" data-hashrate-api="{api}">
  <h2 id="gnfp-hashrate-title">Expected GNFP hashrate by thread count</h2>
  <p class="gnfp-kicker" id="gnfp-hashrate-live"><span class="gnfp-pulse" aria-hidden="true"></span>
    <span id="gnfp-hashrate-live-label">Live · updates from the book</span></p>
  <p class="hint" id="gnfp-hashrate-lead">Observed from a selection of computers
  already hashing on the book (hashed miner tags only — no IPs, wallets, or
  logins). Values move as hashrates fluctuate. The range tightens as more
  samples settle (idle/startup noise drops; EMAs track the live machines).</p>
  <div class="gnfp-hashrate-table-wrap" id="gnfp-hashrate-table-wrap">
    <table class="gnfp-hashrate-table" id="gnfp-hashrate-table">
      <thead>
        <tr><th scope="col">Threads</th><th scope="col">Expected hashrate</th></tr>
      </thead>
      <tbody id="gnfp-hashrate-tbody">{body}</tbody>
    </table>
  </div>
</section>
"""


def render_gnfp_howto_box_html() -> str:
    """Front-facing how-tos for hashed-identity privacy and CPU-only mining."""
    articles = []
    for guide in gnfp_howto_guides():
        gid = html.escape(str(guide["id"]))
        title = html.escape(str(guide["title"]))
        lead = html.escape(str(guide["lead"]))
        path = html.escape(str(guide["path"]), quote=True)
        steps = "".join(
            f"<li>{html.escape(str(step))}</li>" for step in guide["steps"]
        )
        articles.append(
            f'<article class="gnfp-howto" id="howto-{gid}" data-howto="{gid}">'
            f"<h3>{title}</h3>"
            f'<p class="hint">{lead}</p>'
            f'<ol class="gnfp-howto-steps">{steps}</ol>'
            f'<p class="hint"><a href="{path}" data-howto-link="{gid}">'
            f"Open this how-to</a></p>"
            f"</article>"
        )
    return (
        '<section class="panel-card gnfp-howto-box" id="gnfp-howto-box" '
        'data-gnfp-howto="1">'
        '<h2 id="gnfp-howto-title">How-to guides · privacy and CPU mining</h2>'
        '<p class="hint" id="gnfp-howto-lead">The recent book and miner commits '
        "preserve user privacy (hashed identities; no IPs, wallets, or logins "
        "on public pages) and harden CPU mining (CPU-only gnfp-mine work-hash, "
        "GPU refused, TLS by default, --threads capped at 256).</p>"
        f'{"".join(articles)}'
        "</section>"
    )


def render_gnfp_howto_page_html(howto_id: str) -> str | None:
    """Same-origin standalone how-to the GOD page points at."""
    guide = next((g for g in gnfp_howto_guides() if g["id"] == howto_id), None)
    if guide is None:
        return None
    try:
        from public_chrome import (
            public_brand_header_html,
            public_head_open,
            public_page_close,
        )
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import (  # type: ignore
            public_brand_header_html,
            public_head_open,
            public_page_close,
        )
    steps = "".join(
        f"<li>{html.escape(str(step))}</li>" for step in guide["steps"]
    )
    title = html.escape(str(guide["title"]))
    lead = html.escape(str(guide["lead"]))
    gid = html.escape(str(guide["id"]))
    head = public_head_open(title=f"{guide['title']} · GOD", extra_css=god_rpai_css())
    header = public_brand_header_html(
        active=None,
        include_site_nav=False,
        include_theme_picker=False,
        banner_src=GOD_BANNER_SRC,
    )
    close = public_page_close(downloads_map_href=GOD_DOWNLOADS_MAP_HREF)
    return f"""{head}
  <div class="page-shell" id="god-howto-shell" data-page="god-howto" data-howto="{gid}">
{header}
<main class="support-wrap panel-card" id="god-howto-main">
  <p class="hint"><a href="/">Back to GOD</a></p>
  <article class="gnfp-howto" id="howto-{gid}" data-howto="{gid}">
    <h1 id="howto-{gid}-title">{title}</h1>
    <p class="hint">{lead}</p>
    <ol class="gnfp-howto-steps">{steps}</ol>
  </article>
</main>
  </div>
{close}
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
#data-path-layer { display: none; }
.theme-img-dark { display: none; }
html[data-theme="dark"] .theme-img-light { display: none; }
html[data-theme="dark"] .theme-img-dark { display: block; }
@media (prefers-color-scheme: dark) {
  html:not([data-theme="light"]) .theme-img-light { display: none; }
  html:not([data-theme="light"]) .theme-img-dark { display: block; }
}
.shear-hero {
  width: 100%;
  margin: 0 0 1rem;
  overflow: hidden;
  line-height: 0;
  background: #eef3f8;
  text-align: center;
}
html[data-theme="dark"] .shear-hero { background: #0a1628; }
.shear-hero img { width: 100%; height: auto; display: block; object-fit: contain; }
.shear-box-stack { display: flex; flex-direction: column; gap: 1.1rem; margin: 0 0 1rem; }
.shear-box {
  overflow: hidden;
  margin: 0;
  padding: 1.05rem 1.1rem 1.15rem;
  border: 1px solid #2694e8;
  background: rgba(20, 23, 28, 0.92);
  box-shadow: 0 0 18px rgba(0, 229, 255, 0.12);
  font-family: "Segoe UI", system-ui, sans-serif;
  text-align: justify;
  text-justify: inter-word;
  hyphens: auto;
}
.shear-box p, .shear-box li, .shear-lede, .shear-box .hint {
  text-align: justify;
  text-justify: inter-word;
}
.shear-box h1, .shear-box h2, .shear-box h3 {
  color: #00e5ff;
  letter-spacing: 0.03em;
  font-family: "Segoe UI", system-ui, sans-serif;
}
.shear-box h1 { font-size: clamp(1.45rem, 3.4vw, 2.15rem); font-weight: 900; margin: 0 0 0.55rem; line-height: 1.2; }
.shear-box h2 { font-size: 1.18rem; font-weight: 800; margin: 0.85rem 0 0.4rem; }
.shear-box h3 { font-size: 1.02rem; font-weight: 800; margin: 0.75rem 0 0.35rem; }
.shear-lede { font-size: 1.05rem; line-height: 1.55; color: #e8eef5; }
.shear-box p { overflow-wrap: anywhere; }
.shear-box-img {
  width: min(42%, 22rem);
  max-width: 100%;
  height: auto;
  border: 1px solid rgba(38,148,232,0.45);
}
.shear-box-img.float-left { float: left; margin: 0 1.2rem 0.85rem 0; }
.shear-box-img.float-right { float: right; margin: 0 0 0.85rem 1.2rem; }
@media (max-width: 700px) {
  .shear-box-img.float-left, .shear-box-img.float-right {
    float: none; width: 100%; margin: 0 0 1rem;
  }
}
.gnfp-hero {
  width: 100%; margin: 0 0 1rem; overflow: hidden; line-height: 0;
  background: #eef3f8; text-align: center;
}
html[data-theme="dark"] .gnfp-hero { background: #0a1628; }
.gnfp-hero img { width: 100%; height: auto; display: block; object-fit: contain; }
.gnfp-box-stack { display: flex; flex-direction: column; gap: 1.1rem; margin: 0 0 1rem; }
.gnfp-box {
  overflow: hidden; margin: 0; padding: 1.05rem 1.1rem 1.15rem;
  border: 1px solid #2694e8; background: rgba(20, 23, 28, 0.92);
  box-shadow: 0 0 18px rgba(0, 229, 255, 0.12);
  font-family: "Segoe UI", system-ui, sans-serif;
  text-align: justify; text-justify: inter-word; hyphens: auto;
}
.gnfp-box p, .gnfp-box li, .gnfp-lede, .gnfp-box .hint { text-align: justify; text-justify: inter-word; }
.gnfp-box h1, .gnfp-box h2, .gnfp-box h3 { color: #00e5ff; letter-spacing: 0.03em; }
.gnfp-box h1 { font-size: clamp(1.45rem, 3.4vw, 2.15rem); font-weight: 900; margin: 0 0 0.55rem; line-height: 1.2; }
.gnfp-box h2 { font-size: 1.18rem; font-weight: 800; margin: 0.85rem 0 0.4rem; }
.gnfp-lede { font-size: 1.05rem; line-height: 1.55; color: #e8eef5; }
.gnfp-box p { overflow-wrap: anywhere; }
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
  font-size: 1.32rem;
  font-weight: 900;
  letter-spacing: 0.03em;
  line-height: 1.25;
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
#gnfp-hashrate-box, #gnfp-howto-box {
  margin: 0 0 1.2rem;
  padding: 0.95rem 1rem 1.05rem;
  border: 1px solid #2694e8;
  background: #14171c;
  box-shadow: 0 0 18px rgba(0, 229, 255, 0.12);
}
#gnfp-hashrate-title, #gnfp-howto-title {
  margin: 0 0 0.4rem;
  color: #00e5ff;
  letter-spacing: 0.04em;
}
.gnfp-hashrate-table-wrap { overflow-x: auto; margin: 0.7rem 0 0; }
.gnfp-hashrate-table {
  width: 100%;
  border-collapse: collapse;
  font-variant-numeric: tabular-nums;
}
.gnfp-hashrate-table th, .gnfp-hashrate-table td {
  text-align: left;
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid rgba(38,148,232,0.45);
}
.gnfp-hashrate-table th {
  color: #9aa8b5;
  font-size: 0.74rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.gnfp-hashrate-table td { font-weight: 750; color: #e8eef5; }
.gnfp-hashrate-table tr[data-threads="1"] td,
.gnfp-hashrate-table tr[data-threads="256"] td { color: #00e5ff; }
.gnfp-howto { margin: 0.85rem 0 0; padding: 0.75rem 0.8rem; border: 1px solid #2694e8; }
.gnfp-howto h3 { margin: 0 0 0.35rem; color: #00e5ff; }
.gnfp-howto-steps { margin: 0.45rem 0 0; padding-left: 1.2rem; }
.gnfp-howto-steps li { margin: 0.4rem 0; line-height: 1.45; }
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


def render_god_rpai_page_html(*, workers: Any = None) -> str:
    try:
        from public_chrome import public_head_open, public_page_close
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import (  # type: ignore
            public_head_open,
            public_page_close,
        )

    _ = workers
    head = public_head_open(
        title=GOD_PAGE_TITLE,
        extra_css=god_rpai_css(),
    )
    header = render_shear_god_header_html()
    close = public_page_close(downloads_map_href=GOD_DOWNLOADS_MAP_HREF)
    intro = render_gnfp_intro_html()
    return f"""{head}
  <div class="page-shell" id="god-rpai-shell" data-page="god-rpai" data-god-port="{GOD_RPAI_PORT}">
{header}
<main class="support-wrap panel-card" id="god-rpai-main" data-chrome="pro" data-rpai-surface="1">
  {intro}
</main>
  </div>
{close}
"""
