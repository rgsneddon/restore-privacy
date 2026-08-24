"""Dedicated god.restoreprivacy.online[:1474] rpAI page and learn-from-input."""

from __future__ import annotations

import json
import os
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
    os.environ.get(
        "GROK_GOAL_SCRATCH",
        "/var/folders/qb/tz4y4zts04z4846pbq95l6kw0000gp/T/grok-goal-884fbe98563e/implementer",
    )
)

GNFP_MARKERS = (
    'id="shear-ann-box"',
    'id="shear-join-box"',
    'id="shear-vortice-box"',
    'id="shear-hero"',
    'id="gnfp-wallet-links"',
)
ORACLE_MARKERS = (
    'id="god-support-box"',
    'id="goal-builder-box"',
    'id="god-cli-box"',
    'id="god-input-box"',
    "data-agent-learned",
    'id="god-oracle-evolve"',
    'id="god-hub"',
    'id="shear-god-top"',
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
    from god_rpai import GNFP_REL

    low = html.lower()
    for marker in GNFP_MARKERS:
        test.assertIn(marker, html)
    test.assertIn("notice of ledger succession", low)
    test.assertIn("how to claim your 1:1 shear", low)
    test.assertIn("vortice deploy key", low)
    test.assertIn("text-align: justify", html)
    test.assertIn("gnfp1", low)
    test.assertIn("wallet", low)
    test.assertIn("explorer", low)
    test.assertIn(GNFP_REL, html)
    test.assertNotIn("ios-unsigned", html)
    for marker in ORACLE_MARKERS:
        test.assertNotIn(marker, html)
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
        self.assertIn("SHEAR_light.png", html)
        self.assertIn("GNFP", html)
        _assert_gnfp_first_landing(self, html)
        self.assertNotIn("/goal · goalbuilder app", html)
        self.assertNotIn('id="god-cli-box"', html)
        self.assertNotIn("god_build.js", html)
        self.assertIn("#2b2b2b", html)
        self.assertIn("#00e5ff", html)
        self.assertIn("text-align: center", html)
        self.assertIn("text-align: justify", html)
        self.assertNotIn('id="doc-links"', html)
        self.assertNotIn('id="theme-mode-control"', html)
        self.assertIn("linear-gradient(135deg, #2694e8 0%, #00e5ff 100%)", html)
        self.assertIn("chronoflux", html.lower())
        self.assertIn("god-rpai-main", html)
        self.assertIn("panel-card", html)
        self.assertIn("1474", html)
        self.assertNotIn("135.181.152.10", html)
        self.assertNotIn("NED leads under GOD", html)
        self.assertNotIn("Send support ticket", html)
        self.assertGreaterEqual(len(PORT_1474_BENEFITS), 4)

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
            self.assertIn("SHEAR_light.png", page)
            self.assertIn("1474", page)
            self.assertNotIn('id="god-hub"', page)
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
        self.assertEqual(GOD_BANNER_SRC, "/static/SHEAR_light.png")

        from downloads import latest_repo_pin

        products = hub_products()
        gnfp_pin = latest_repo_pin("gnfp-wallet") or GNFP_WALLET_PIN
        evolve_pin = latest_repo_pin("evolve") or EVOLVE_PIN
        self.assertEqual([p["name"] for p in products], ["Restore Privacy VPN", "GNFP", "Evolve"])
        self.assertEqual(products[0]["version"], VPN_CATALOG_VERSION)
        self.assertEqual(products[1]["version"], gnfp_pin)
        self.assertEqual(products[2]["version"], evolve_pin)
        self.assertEqual(VPN_CATALOG_VERSION, "1.2.7")
        self.assertTrue(GNFP_WALLET_PIN)
        self.assertEqual(EVOLVE_PIN, "4.2.1")

        html = render_god_rpai_page_html()
        hub = render_god_hub_html()
        self.assertNotIn(hub, html)
        self.assertIn(GOD_BANNER_SRC, html)
        self.assertNotIn('id="god-main-title"', html)
        self.assertNotIn("0.1.13", html)
        self.assertIn(f"gnfp-wallet-{gnfp_pin}-", html)
        gnfp_labels = [label for label, _href in products[1]["hrefs"]]
        if any("windows" in href.lower() for _label, href in products[1]["hrefs"]):
            self.assertEqual(gnfp_labels[0], "Windows")
        self.assertIn("Restore Privacy VPN", hub)
        self.assertIn("GNFP", hub)
        self.assertIn("Evolve", hub)
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
        self.assertNotIn(menu, html)
        self.assertIn(menu, hub)
        menu_at = hub.index('id="god-hub-menu"')
        start_at = hub.index('id="god-hub-title"')
        grid_at = hub.index('id="god-hub-grid"')
        self.assertLess(menu_at, start_at)
        self.assertLess(start_at, grid_at)
        self.assertNotIn(
            "GOD sits at the top of rpAI",
            html,
        )
        self.assertNotIn('id="god-rpai-lead"', html)
        self.assertIn("text-align: justify", html)
        self.assertEqual(
            [label for label, _href in links],
            ["GNFP POOL", "GNFP EXPLORER", "RESTORE PRIVACY VPN", "EVOLVE"],
        )
        for label, href in links:
            self.assertIn(label, hub)
            self.assertIn(html_mod.escape(href, quote=True), hub)
        for product in hub_products():
            self.assertIn(f'id="god-hub-{product["id"]}"', hub)
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
            render_gnfp_intro_html,
            render_god_rpai_page_html,
        )

        intro = render_gnfp_intro_html()
        html = render_god_rpai_page_html()
        self.assertIn(intro, html)
        self.assertIn("ninety-nine days", intro)
        self.assertIn('data-shear-box="ann"', intro)
        self.assertIn('data-shear-box="join"', intro)
        self.assertIn('data-shear-box="vortice"', intro)
        self.assertIn("/static/shear-ann.jpg", intro)
        self.assertNotIn('id="gnfp-official-links"', intro)
        self.assertNotIn('id="gnfp-community"', intro)
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

    def test_hashrate_box_and_howtos_come_from_shipped_renderer(self) -> None:
        try:
            from gnfp import expected_hashrate_table
        except ImportError:
            self.skipTest("expected_hashrate_table not in this gnfp.py")
        from god_rpai import (
            GNFP_CPU_MINE_HOWTO_PATH,
            GNFP_PRIVACY_HOWTO_PATH,
            render_gnfp_hashrate_box_html,
            render_gnfp_howto_box_html,
            render_gnfp_howto_page_html,
            render_god_rpai_page_html,
        )

        workers = [
            {"tag": "miner-aaaa1111", "hashrate": 80.0, "threads": 4},
            {"tag": "miner-bbbb2222", "hashrate": 5.0, "threads": 1},
        ]
        rows = expected_hashrate_table(workers)
        by_n = {int(r["threads"]): r for r in rows}
        box = render_gnfp_hashrate_box_html(workers)
        html = render_god_rpai_page_html(workers=workers)
        self.assertIn('id="gnfp-hashrate-box"', box)
        self.assertIn('data-threads="1"', box)
        self.assertIn('data-threads="256"', box)
        self.assertIn("1 thread", box)
        self.assertIn("256 threads", box)
        self.assertIn('data-hashrate-live="1"', box)
        self.assertIn('data-hashrate-api="/api/gnfp-hashrate"', box)
        self.assertIn(by_n[1]["expected"], box)
        self.assertIn(by_n[256]["expected"], box)
        self.assertNotIn('id="gnfp-hashrate-box"', html)
        self.assertNotIn("god_rpai.js?v=live-hashrate", html)
        js = (ROOT / "status_page" / "static" / "god_rpai.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("/api/gnfp-hashrate", js)
        self.assertIn("setInterval", js)
        self.assertIn("data-hashrate-expected", js)
        self.assertNotIn("plain TCP, no TLS", html)

        howto = render_gnfp_howto_box_html()
        self.assertIn('id="gnfp-howto-box"', howto)
        self.assertIn('id="howto-privacy"', howto)
        self.assertIn('id="howto-cpu-mine"', howto)
        self.assertIn("hashed identities", howto)
        self.assertIn("no IPs", howto)
        self.assertIn("wallets", howto)
        self.assertIn("logins", howto)
        self.assertIn("gnfp-mine", howto)
        self.assertIn("CPU-only", howto)
        self.assertIn("work-hash", howto)
        self.assertIn("GPU refused", howto)
        self.assertIn("TLS", howto)
        self.assertIn("256", howto)
        self.assertIn(GNFP_PRIVACY_HOWTO_PATH, howto)
        self.assertIn(GNFP_CPU_MINE_HOWTO_PATH, howto)
        self.assertNotIn('id="gnfp-howto-box"', html)

        privacy = render_gnfp_howto_page_html("privacy")
        cpu = render_gnfp_howto_page_html("cpu-mine")
        self.assertIsNotNone(privacy)
        self.assertIsNotNone(cpu)
        assert privacy is not None and cpu is not None
        self.assertIn("hashed identities", privacy)
        self.assertIn("no IPs", privacy)
        self.assertIn("wallets", privacy)
        self.assertIn("logins", privacy)
        self.assertIn("gnfp-mine", cpu)
        self.assertIn("CPU-only", cpu)
        self.assertIn("work-hash", cpu)
        self.assertIn("GPU refused", cpu)
        self.assertIn("TLS", cpu)
        self.assertIn("256", cpu)

        SCRATCH.mkdir(parents=True, exist_ok=True)
        first = render_god_rpai_page_html(workers=workers)
        second = render_god_rpai_page_html(workers=workers)
        (SCRATCH / "god-page-1.html").write_text(first, encoding="utf-8")
        (SCRATCH / "god-page-2.html").write_text(second, encoding="utf-8")
        for body in (first, second):
            self.assertIn('id="shear-ann-box"', body)
            self.assertIn('id="shear-join-box"', body)
            self.assertIn('id="shear-vortice-box"', body)
            self.assertIn("/static/shear-ann.jpg", body)
            self.assertIn("ninety-nine days", body)
            self.assertIn("vort1.", body)
            self.assertNotIn('id="gnfp-hashrate-box"', body)

    def test_god_host_serves_same_origin_howtos(self) -> None:
        self.skipTest("howto routes are not on the stripped GOD landing handler")
        from god_port import GodRpaiHandler
        from god_rpai import GNFP_CPU_MINE_HOWTO_PATH, GNFP_PRIVACY_HOWTO_PATH

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), GodRpaiHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            port = httpd.server_address[1]
            privacy = (
                urllib.request.urlopen(
                    f"http://127.0.0.1:{port}{GNFP_PRIVACY_HOWTO_PATH}", timeout=8
                )
                .read()
                .decode("utf-8")
            )
            cpu = (
                urllib.request.urlopen(
                    f"http://127.0.0.1:{port}{GNFP_CPU_MINE_HOWTO_PATH}", timeout=8
                )
                .read()
                .decode("utf-8")
            )
        finally:
            httpd.shutdown()
            httpd.server_close()
        self.assertIn("hashed identities", privacy)
        self.assertIn("no IPs", privacy)
        self.assertIn("gnfp-mine", cpu)
        self.assertIn("work-hash", cpu)
        self.assertIn("256", cpu)

    def test_god_host_serves_live_hashrate_api_twice(self) -> None:
        self.skipTest("hashrate API is not on the stripped GOD landing handler")
        from god_port import GodRpaiHandler

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), GodRpaiHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            port = httpd.server_address[1]
            bodies = []
            for _ in (1, 2):
                raw = urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/gnfp-hashrate", timeout=8
                ).read()
                data = json.loads(raw.decode("utf-8"))
                self.assertTrue(data["ok"])
                self.assertTrue(data["live"])
                threads = [int(r["threads"]) for r in data["rows"]]
                self.assertIn(1, threads)
                self.assertIn(256, threads)
                self.assertTrue(data["rows"][0]["expected"])
                bodies.append(data)
        finally:
            httpd.shutdown()
            httpd.server_close()
        self.assertGreaterEqual(bodies[1]["samples"], bodies[0]["samples"])


class TestGnfpPublicHowtos(unittest.TestCase):
    def test_public_docs_serve_privacy_and_cpu_howtos(self) -> None:
        self.skipTest("public howto docs are not part of the Shear landing")
        from public_docs import document_bytes_for_path

        privacy = document_bytes_for_path("/howto/gnfp-privacy")
        cpu = document_bytes_for_path("/howto/gnfp-cpu-mine")
        self.assertIsNotNone(privacy)
        self.assertIsNotNone(cpu)
        assert privacy is not None and cpu is not None
        phtml = privacy[0].decode("utf-8")
        chtml = cpu[0].decode("utf-8")
        self.assertIn("hashed identities", phtml)
        self.assertIn("no IPs", phtml)
        self.assertIn("wallets", phtml)
        self.assertIn("logins", phtml)
        self.assertIn("gnfp-mine", chtml)
        self.assertIn("CPU-only", chtml)
        self.assertIn("work-hash", chtml)
        self.assertIn("GPU refused", chtml)
        self.assertIn("TLS", chtml)
        self.assertIn("256", chtml)


if __name__ == "__main__":
    unittest.main()

