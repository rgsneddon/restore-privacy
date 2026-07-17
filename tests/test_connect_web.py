"""Tests drive shipped connect-via-web builders (honest web path + real downloads)."""

from __future__ import annotations

import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import app as status_app  # noqa: E402
from connect_web import (  # noqa: E402
    ACTION_LINE,
    CONNECT_HEADING,
    HONESTY_LINE,
    recommended_download_actions,
    render_connect_via_web_html,
)
from downloads import available_downloads  # noqa: E402


class TestConnectViaWebBuilder(unittest.TestCase):
    def test_section_has_heading_honesty_and_real_hrefs(self):
        html = render_connect_via_web_html()
        self.assertIn(CONNECT_HEADING, html)
        self.assertIn("Connect via web", html)
        self.assertIn(HONESTY_LINE[:40], html)
        # Must not claim full system VPN runs inside the page alone
        lower = html.lower()
        self.assertIn("cannot", lower)
        self.assertIn("system-wide vpn", lower)
        self.assertNotIn("full system vpn is now active in this tab", lower)
        self.assertNotIn('href="#"', html)
        # Real release download actions
        for a in available_downloads():
            self.assertIn(a.url, html)
            self.assertTrue(a.url.startswith("https://"))
        self.assertIn("not a full-device VPN", html)
        self.assertIn("connect-web-probe", html)

    def test_recommended_actions_match_release_catalog(self):
        actions = recommended_download_actions()
        self.assertGreaterEqual(len(actions), 2)
        for a in actions:
            self.assertIn("/releases/download/", a["href"])
            self.assertTrue(a["href"].startswith("https://"))

    def test_render_html_includes_connect_and_downloads_and_poll(self):
        page = status_app.render_html(
            {"title": "RESTORE PRIVACY", "clients_connected": 1}
        ).decode("utf-8")
        self.assertIn("Connect via web", page)
        self.assertIn("id=\"connect-via-web\"", page)
        self.assertIn(HONESTY_LINE.split("(")[0].strip()[:20], page)
        self.assertIn("Download client v0.0.1", page)
        self.assertIn("fetch('/api/status'", page)
        self.assertIn("setInterval(poll", page)
        self.assertNotIn('http-equiv="refresh"', page.lower())
        # Honesty: no false full-VPN-in-browser claim
        self.assertNotIn("your full device vpn is running in this browser tab", page.lower())


class TestConnectViaWebHttp(unittest.TestCase):
    def setUp(self):
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        self._port = self._httpd.server_address[1]
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self._httpd.shutdown()
        self._httpd.server_close()

    def test_handler_serves_connect_section_twice(self):
        with mock.patch.object(
            status_app,
            "fetch_upstream_status",
            return_value={"title": "RESTORE PRIVACY", "clients_connected": 2},
        ):
            for _ in range(2):
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{self._port}/", timeout=5
                ) as resp:
                    html = resp.read().decode("utf-8")
                self.assertEqual(resp.status if hasattr(resp, "status") else 200, 200)
                self.assertIn("Connect via web", html)
                self.assertIn("connect-via-web", html)
                self.assertIn("releases/download/0.0.1/", html)
                self.assertIn("fetch('/api/status'", html)
                self.assertIn("cannot install a full system-wide vpn", html.lower())


if __name__ == "__main__":
    unittest.main()
