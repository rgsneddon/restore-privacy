"""Tests drive shipped coffee-link builder / status-page render."""

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
from coffee_link import (  # noqa: E402
    COFFEE_LINK_TEXT,
    COFFEE_LINK_URL,
    coffee_link_css,
    render_coffee_link_html,
)


class TestCoffeeLinkBuilder(unittest.TestCase):
    def test_exact_text_and_url(self):
        self.assertEqual(COFFEE_LINK_TEXT, "buy rus a coffee")
        self.assertEqual(COFFEE_LINK_URL, "https://buymeacoffee.com/rgsneddon")
        html = render_coffee_link_html()
        self.assertIn("buy rus a coffee", html)
        self.assertIn('href="https://buymeacoffee.com/rgsneddon"', html)
        self.assertIn("coffee-footer", html)
        self.assertIn("coffee-link", html)
        self.assertNotIn('href="#"', html)
        css = coffee_link_css()
        self.assertIn("text-align: center", css)
        self.assertIn("coffee-footer", css)
        self.assertIn("margin-top: auto", css)

    def test_public_page_excludes_coffee_keeps_count(self):
        page = status_app.render_html(
            {"title": "RESTORE PRIVACY", "clients_connected": 0}
        ).decode("utf-8")
        self.assertNotIn("buy rus a coffee", page)
        self.assertNotIn("buymeacoffee.com", page)
        self.assertIn("fetch('/api/status'", page)
        self.assertIn("setInterval(poll", page)
        self.assertIn("RESTORE PRIVACY", page)


class TestCoffeeLinkHttp(unittest.TestCase):
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
            return_value={"title": "RESTORE PRIVACY", "clients_connected": 1},
        ):
            for _ in range(2):
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{self._port}/", timeout=5
                ) as resp:
                    html = resp.read().decode("utf-8")
                self.assertIn("fetch('/api/status'", html)
                self.assertNotIn("buy rus a coffee", html)
                self.assertIn("Download client v0.1.7", html)


if __name__ == "__main__":
    unittest.main()
