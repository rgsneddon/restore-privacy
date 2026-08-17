"""Dedicated god.restoreprivacy.online[:1474] rpAI page and learn-from-input."""

from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
import html as html_mod
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT))

SCRATCH = Path(
    "/var/folders/qb/tz4y4zts04z4846pbq95l6kw0000gp/T/grok-goal-fe6a0861d1b3/implementer"
)

GNFP_MARKERS = (
    'id="gnfp-what"',
    'id="gnfp-mining"',
    'id="gnfp-wallet"',
    'id="gnfp-explorer"',
    'id="gnfp-official-links"',
    'id="gnfp-community"',
)
ORACLE_MARKERS = (
    'id="god-support-box"',
    'id="goal-builder-box"',
    'id="god-cli-box"',
    'id="god-input-box"',
    "data-agent-learned",
)
SUPPORT_FORM_MARKERS = (
    "god-ticket-box",
    "god-ticket-form",
    'id="support-email"',
    'id="support-subject"',
    'id="support-message"',
    'name="email"',
    'name="subject"',
    'name="message"',
    'action="https://restoreprivacy.online/support"',
    'action="/support"',
)


def _assert_gnfp_first_landing(test: unittest.TestCase, html: str) -> None:
    from god_rpai import (
        GNFP_DISCORD_HREF,
        GNFP_EXPLORER_HREF,
        GNFP_POOL_HREF,
        GNFP_REL,
        GNFP_TELEGRAM_HREF,
    )

    low = html.lower()
    for marker in GNFP_MARKERS:
        test.assertIn(marker, html)
    test.assertIn("what it is", low)
    test.assertIn("how mining works", low)
    test.assertIn("beamhash iii", low)
    test.assertIn("gnfp1", low)
    test.assertIn("wallet", low)
    test.assertIn("explorer", low)
    test.assertIn(GNFP_POOL_HREF, html)
    test.assertIn(GNFP_EXPLORER_HREF, html)
    test.assertIn(GNFP_REL, html)
    test.assertIn(GNFP_DISCORD_HREF, html)
    test.assertIn("Discord", html)
    test.assertIn(GNFP_TELEGRAM_HREF, html)
    intro_at = html.index('id="gnfp-intro"')
    for marker in ORACLE_MARKERS:
        test.assertIn(marker, html)
        test.assertLess(intro_at, html.index(marker), marker)
    for marker in SUPPORT_FORM_MARKERS:
        test.assertNotIn(marker, html)
    test.assertNotIn("rus@restoreprivacy.online", html)


class TestGodRpaiPage(unittest.TestCase):
    def setUp(self) -> None:
        from node.rpai_action_learn import reset_action_learner

        reset_action_learner()

    def test_page_is_wholly_rpai_and_boxed(self) -> None:
        from god_rpai import (
            GOD_RPAI_HOST,
            GOD_RPAI_PORT,
            PORT_1474_BENEFITS,
            is_god_host,
            render_god_rpai_page_html,
        )

        self.assertTrue(is_god_host("god.restoreprivacy.online"))
        self.assertTrue(is_god_host("god.restoreprivacy.online:1474"))
        self.assertFalse(is_god_host("restoreprivacy.online"))
        self.assertEqual(GOD_RPAI_HOST, "god.restoreprivacy.online")
        self.assertEqual(GOD_RPAI_PORT, 1474)
        html = render_god_rpai_page_html()
        self.assertNotIn('id="god-main-title"', html)
        self.assertNotIn("God's GNPF crypto-coin", html)
        self.assertNotIn("GOD another AI learning Oracle", html)
        self.assertIn("bannerall.jpg", html)
        self.assertIn("god-hub", html)
        self.assertIn("Restore Privacy VPN", html)
        self.assertIn("GNFP", html)
        self.assertIn("Evolve", html)
        _assert_gnfp_first_landing(self, html)
        self.assertIn("/goal · goalbuilder app", html)
        self.assertNotIn("/goal · Grok Build", html)
        self.assertIn("god-cli-box", html)
        self.assertIn("god_build.js", html)
        self.assertIn("gnfp-tip-height", html)
        self.assertIn("GNFP tip height", html)
        self.assertIn("grok-construe", html)
        self.assertIn("x.com", html)
        self.assertIn("#2b2b2b", html)
        self.assertIn("#00e5ff", html)
        self.assertIn("god-input-box", html)
        self.assertIn("text-align: center", html)
        self.assertNotIn('id="doc-links"', html)
        self.assertNotIn('id="theme-mode-control"', html)
        self.assertIn("linear-gradient(135deg, #2694e8 0%, #00e5ff 100%)", html)
        self.assertIn("chronoflux", html.lower())
        self.assertIn("#00e5ff", html)
        self.assertIn("god-rpai-main", html)
        self.assertIn("panel-card", html)
        self.assertIn("god-support-box", html)
        self.assertIn("goal-builder-box", html)
        self.assertIn("goal-scs", html)
        self.assertIn("goal-percent", html)
        self.assertIn("god-learn-input", html)
        self.assertIn("data-agent-learned", html)
        self.assertIn("Grokbot", html)
        self.assertIn("1474", html)
        self.assertNotIn("135.181.152.10", html)
        self.assertNotIn("NED leads under GOD", html)
        self.assertNotIn("Send support ticket", html)
        self.assertGreaterEqual(len(PORT_1474_BENEFITS), 4)
        for name in ("GOD", "NED", "FRED", "PEDRO"):
            self.assertIn(name, html)

    def test_god_downloads_map_href_is_apex_restoreprivacy(self) -> None:
        from god_rpai import GOD_DOWNLOADS_MAP_HREF, render_god_rpai_page_html

        self.assertEqual(
            GOD_DOWNLOADS_MAP_HREF,
            "https://restoreprivacy.online/downloads-map",
        )
        html = render_god_rpai_page_html()
        self.assertIn('href="https://restoreprivacy.online/downloads-map"', html)
        self.assertIn('id="site-footer-downloads-map"', html)
        # Same-host relative map 404s on god.
        footer = html[html.index('id="site-footer-downloads-map"') :]
        self.assertNotIn('href="/downloads-map"', footer)
        self.assertNotIn("https://god.restoreprivacy.online/downloads-map", footer)
        scratch = Path(
            __import__("os").environ.get(
                "GROK_GOAL_SCRATCH",
                r"C:\Users\rgsne\AppData\Local\Temp\grok-goal-b3bb74235a15\implementer",
            )
        )
        scratch.mkdir(parents=True, exist_ok=True)
        first = render_god_rpai_page_html()
        second = render_god_rpai_page_html()
        href = GOD_DOWNLOADS_MAP_HREF
        self.assertIn(href, first)
        self.assertIn(href, second)
        (scratch / "god-downloads-map-href.txt").write_text(
            href + "\n", encoding="utf-8"
        )
        (scratch / "god-downloads-map-host.txt").write_text(
            "god.restoreprivacy.online/downloads-map is not the catalog\n"
            f"god_page_href={href}\n",
            encoding="utf-8",
        )

    def test_god_host_downloads_map_is_not_the_catalog(self) -> None:
        from god_port import GodRpaiHandler

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), GodRpaiHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            port = httpd.server_address[1]
            err = None
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/downloads-map", timeout=8
                )
            except urllib.error.HTTPError as exc:
                err = exc
            self.assertIsNotNone(err)
            assert err is not None
            self.assertEqual(err.code, 404)
            body = err.read().decode("utf-8", errors="replace")
            self.assertNotIn("data-downloads-map-page", body)
            self.assertIn("rpAI only", body)
            scratch = Path(
                __import__("os").environ.get(
                    "GROK_GOAL_SCRATCH",
                    r"C:\Users\rgsne\AppData\Local\Temp\grok-goal-b3bb74235a15\implementer",
                )
            )
            scratch.mkdir(parents=True, exist_ok=True)
            (scratch / "god-downloads-map-host.txt").write_text(
                "god.restoreprivacy.online/downloads-map is not the catalog\n"
                f"http_status={err.code}\nbody_has_map_page=false\n",
                encoding="utf-8",
            )
        finally:
            httpd.shutdown()

    def test_learn_from_input_credits_four_agents(self) -> None:
        from god_rpai import learn_from_input, rpai_dashboard_payload

        xai = lambda *a, **k: "noted"
        result = learn_from_input(
            {"input": "open analysis surface", "family": "evolve_suite"},
            xai_fn=xai,
        )
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["grokbot_invoked"])
        names = [r["name"] for r in result["agents"]]
        self.assertEqual(names, ["GOD", "NED", "FRED", "PEDRO"])
        for row in result["agents"]:
            self.assertGreaterEqual(int(row["learned"]), 1)
        dash = rpai_dashboard_payload()
        self.assertEqual(dash["host"], "god.restoreprivacy.online")
        self.assertEqual(dash["port"], 1474)
        self.assertEqual(dash["chaperone"], "Grokbot")
        self.assertTrue(dash["agents"])

    def test_port_1474_handler_serves_page_and_api(self) -> None:
        from god_port import GodRpaiHandler

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), GodRpaiHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            page = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/", timeout=5
            ).read().decode("utf-8")
            self.assertNotIn('id="god-main-title"', page)
            self.assertNotIn("GNPF", page)
            self.assertIn("bannerall.jpg", page)
            self.assertIn("1474", page)
            self.assertIn("god-hub", page)
            _assert_gnfp_first_landing(self, page)
            api = json.loads(
                urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/rpai", timeout=5
                ).read().decode("utf-8")
            )
            self.assertEqual(api["identity"], "GOD · rpAI")
            health = json.loads(
                urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=5
                ).read().decode("utf-8")
            )
            self.assertTrue(health["ok"])
            self.assertEqual(health.get("who"), "GOD")
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_suite_build_learns_and_offers_device_download(self) -> None:
        from god_build import BRIEF_LINE, detect_device, run_suite_build
        from node.rpai_action_learn import reset_action_learner

        reset_action_learner()
        self.assertEqual(detect_device("Mozilla/5.0 (Macintosh)"), "macos")
        job = run_suite_build(
            device="macos",
            brief=BRIEF_LINE,
            xai_fn=lambda *a, **k: BRIEF_LINE,
        )
        self.assertTrue(job["done"], job)
        self.assertIn("macos", job["download"])
        blob = "\n".join(job["lines"])
        self.assertIn("GOD", blob)
        self.assertIn("NED", blob)
        self.assertIn("FRED", blob)
        self.assertIn("PEDRO", blob)
        self.assertIn("Evolve Suite is the surface", blob)
        self.assertTrue(job["download"].endswith(".zip"))

    def test_nginx_and_service_pin_helsinki_god_record(self) -> None:
        nginx = (
            ROOT / "perc_chain" / "deploy" / "nginx-god.restoreprivacy.online.conf"
        ).read_text(encoding="utf-8")
        unit = (ROOT / "perc_chain" / "deploy" / "rpt-god-rpai.service").read_text(
            encoding="utf-8"
        )
        gnfp_unit = (ROOT / "perc_chain" / "deploy" / "rpt-gnfp-pool.service").read_text(
            encoding="utf-8"
        )
        self.assertIn("server_name god.restoreprivacy.online", nginx)
        self.assertIn("1474", nginx)
        self.assertIn("8013", nginx)
        self.assertIn("8014", nginx)
        self.assertIn("135.181.152.10", nginx)
        self.assertIn("god_port.py", unit)
        self.assertIn("8013", unit)
        self.assertIn("1474", gnfp_unit)
        self.assertIn("gnfp_pool.js", gnfp_unit)
        app = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/god", app)
        self.assertIn("/api/learn", app)
        self.assertIn("god_rpai.js", app)

    def test_hub_uses_bannerall_and_current_installers(self) -> None:
        from god_rpai import (
            EVOLVE_PIN,
            GNFP_WALLET_PIN,
            GOD_BANNER_FILE,
            GOD_BANNER_SRC,
            VPN_CATALOG_VERSION,
            hub_products,
            render_god_hub_html,
            render_god_rpai_page_html,
        )

        banner = ROOT / "status_page" / "static" / GOD_BANNER_FILE
        replaced = ROOT / "status_page" / "static" / "god_banner.jpg"
        self.assertTrue(banner.is_file(), banner)
        self.assertTrue(replaced.is_file(), replaced)
        self.assertEqual(banner.read_bytes(), replaced.read_bytes())
        self.assertGreater(banner.stat().st_size, 1000)
        self.assertEqual(GOD_BANNER_SRC, "/bannerall.jpg")

        products = hub_products()
        self.assertEqual([p["name"] for p in products], ["Restore Privacy VPN", "GNFP", "Evolve"])
        self.assertEqual(products[0]["version"], VPN_CATALOG_VERSION)
        self.assertEqual(products[1]["version"], GNFP_WALLET_PIN)
        self.assertEqual(products[2]["version"], EVOLVE_PIN)
        self.assertEqual(VPN_CATALOG_VERSION, "1.2.7")
        self.assertEqual(GNFP_WALLET_PIN, "0.0.5")
        self.assertEqual(EVOLVE_PIN, "4.2.1")

        html = render_god_rpai_page_html()
        hub = render_god_hub_html()
        self.assertIn(hub, html)
        self.assertIn(GOD_BANNER_SRC, html)
        self.assertNotIn('id="god-main-title"', html)
        self.assertNotIn("0.1.13", html)
        self.assertIn("gnfp-wallet-0.0.5-windows.zip", html)
        self.assertIn("gnfp-wallet-0.0.5-linux.zip", html)
        gnfp_labels = [label for label, _href in products[1]["hrefs"]]
        self.assertEqual(gnfp_labels[0], "Windows")
        for product in products:
            self.assertIn(product["name"], html)
            self.assertIn(product["version"], html)
            self.assertIn(product["release"], html)
            for _label, href in product["hrefs"]:
                self.assertIn(html_mod.escape(href, quote=True), html)
        self.assertIn("Grokbot", html)
        self.assertIn("GOD", html)
        self.assertIn("NED", html)
        self.assertIn("FRED", html)
        self.assertIn("PEDRO", html)
        self.assertIn("god-learn-input", html)
        self.assertIn("/goal · goalbuilder app", html)
        self.assertIn("Session address is perpetual in your wallet", html)
        self.assertNotIn("Developer ID", html)
        self.assertNotIn("Windows and Linux are not on this pin", html)
        self.assertNotIn("GOD is the rpAI agent and overall leader", html)
        self.assertNotIn("Grokbot reports to GOD and chaperones", html)

    def test_hub_menu_bar_sits_above_installer_boxes(self) -> None:
        from god_rpai import (
            hub_menu_links,
            hub_products,
            render_god_hub_html,
            render_god_hub_menu_html,
            render_god_rpai_page_html,
        )

        links = hub_menu_links()
        self.assertEqual(len(links), 4)
        html = render_god_rpai_page_html()
        menu = render_god_hub_menu_html()
        hub = render_god_hub_html()
        self.assertIn(menu, html)
        self.assertIn(menu, hub)
        menu_at = html.index('id="god-hub-menu"')
        start_at = html.index('id="god-hub-title"')
        grid_at = html.index('id="god-hub-grid"')
        self.assertLess(menu_at, start_at)
        self.assertLess(start_at, grid_at)
        self.assertNotIn(
            "GOD sits at the top of rpAI",
            html,
        )
        self.assertNotIn('id="god-rpai-lead"', html)
        self.assertIn("justify-content: center", html)
        self.assertEqual(
            [label for label, _href in links],
            ["GNFP POOL", "GNFP EXPLORER", "RESTORE PRIVACY VPN", "EVOLVE"],
        )
        for label, href in links:
            self.assertIn(label, html)
            self.assertIn(html_mod.escape(href, quote=True), html)
        for product in hub_products():
            self.assertIn(f'id="god-hub-{product["id"]}"', html)
        scratch = Path(
            __import__("os").environ.get(
                "GROK_GOAL_SCRATCH",
                "/var/folders/qb/tz4y4zts04z4846pbq95l6kw0000gp/T/grok-goal-8b39b622cbc6/implementer",
            )
        )
        scratch.mkdir(parents=True, exist_ok=True)
        (scratch / "god-menubar.html").write_text(html, encoding="utf-8")

    def test_gnfp_intro_precedes_oracle_and_has_no_ticket_form(self) -> None:
        from god_rpai import (
            GNFP_BOOK,
            gnfp_community_links,
            gnfp_official_links,
            render_gnfp_intro_html,
            render_god_rpai_page_html,
        )

        intro = render_gnfp_intro_html()
        html = render_god_rpai_page_html()
        self.assertIn(intro, html)
        self.assertIn(GNFP_BOOK, intro)
        self.assertIn('data-gnfp-section="what"', intro)
        self.assertIn('data-gnfp-section="mining"', intro)
        self.assertIn('data-gnfp-section="wallet"', intro)
        self.assertIn('data-gnfp-section="explorer"', intro)
        for label, href in gnfp_official_links():
            self.assertIn(label, intro)
            self.assertIn(html_mod.escape(href, quote=True), intro)
        for label, href in gnfp_community_links():
            self.assertIn(label, intro)
            self.assertIn(html_mod.escape(href, quote=True), intro)
        _assert_gnfp_first_landing(self, html)
        self.assertNotIn("telegram.me/fake", html)
        self.assertNotIn("discord.gg/fake", html)
        SCRATCH.mkdir(parents=True, exist_ok=True)
        (SCRATCH / "god-page.html").write_text(html, encoding="utf-8")

    def test_god_handler_serves_gnfp_first_twice(self) -> None:
        from god_port import GodRpaiHandler

        bodies: list[str] = []
        for run in (1, 2):
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), GodRpaiHandler)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                port = httpd.server_address[1]
                resp = urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/", timeout=8
                )
                self.assertEqual(resp.status, 200)
                body = resp.read().decode("utf-8")
            finally:
                httpd.shutdown()
                httpd.server_close()
            _assert_gnfp_first_landing(self, body)
            bodies.append(body)
            SCRATCH.mkdir(parents=True, exist_ok=True)
            (SCRATCH / f"god-launch-{run}.html").write_text(body, encoding="utf-8")
        self.assertEqual(len(bodies), 2)
        _assert_gnfp_first_landing(self, bodies[0])
        _assert_gnfp_first_landing(self, bodies[1])


if __name__ == "__main__":
    unittest.main()
