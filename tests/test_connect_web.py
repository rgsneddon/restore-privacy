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
        # Paid status-page paths (not free public GitHub release hrefs)
        for a in available_downloads():
            self.assertIn(a.pay_path, html)
            self.assertTrue(a.pay_path.startswith("/pay?"))
            self.assertNotIn(a.url, html)
        self.assertIn("not a full-device VPN", html)
        self.assertIn("connect-web-probe", html)

    def test_recommended_actions_match_release_catalog(self):
        actions = recommended_download_actions()
        self.assertGreaterEqual(len(actions), 2)
        for a in actions:
            self.assertTrue(a["href"].startswith("/pay?platform="))
            self.assertNotIn("github.com", a["href"])

    def test_public_page_excludes_connect_section_and_count(self):
        page = status_app.render_html(
            {"title": "RESTORE PRIVACY"}
        ).decode("utf-8")
        # Connect-via-web is not on the public minimal page
        self.assertNotIn("Connect via web", page)
        self.assertNotIn("connect-via-web", page)
        # No live client count poll
        self.assertNotIn("fetch('/api/status'", page)
        self.assertNotIn("setInterval(poll", page)
        self.assertNotIn("Currently connected clients", page)
        self.assertNotIn('http-equiv="refresh"', page.lower())


class TestConnectViaWebHttp(unittest.TestCase):
    def setUp(self):
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        self._port = self._httpd.server_address[1]
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self._httpd.shutdown()
        self._httpd.server_close()

    def test_handler_serves_minimal_page_twice(self):
        with mock.patch.object(
            status_app,
            "fetch_upstream_status",
            return_value={"title": "RESTORE PRIVACY", "upstream_ok": True},
        ):
            for _ in range(2):
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{self._port}/", timeout=5
                ) as resp:
                    html = resp.read().decode("utf-8")
                self.assertIn("RESTORE PRIVACY", html)
                self.assertNotIn("fetch('/api/status'", html)
                self.assertNotIn("Connect via web", html)
                # Downloads present; connect-via-web section remains off
                self.assertTrue(
                    "releases/tag/0.3.0" in html
                    or "releases/download/0.3.0/" in html
                    or "restore-privacy-client-0.3.0-" in html,
                    html[:500],
                )


if __name__ == "__main__":
    unittest.main()
