"""Public footer copyright + residual BMC admin helpers."""

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
    SITE_COPYRIGHT_TEXT,
    coffee_link_css,
    coffee_tip_url,
    render_coffee_link_html,
    render_site_copyright_footer_html,
)


class TestCoffeeLinkBuilder(unittest.TestCase):
    def test_admin_bmc_constants_still_defined(self):
        """Admin inventory may still know the BMC URL; public footer does not use it."""
        self.assertEqual(COFFEE_LINK_TEXT, "buy rus a coffee")
        self.assertEqual(COFFEE_LINK_URL, "https://buymeacoffee.com/rgsneddon")
        self.assertIn("buymeacoffee.com", coffee_tip_url())

    def test_public_footer_is_raskul_copyright(self):
        self.assertEqual(SITE_COPYRIGHT_TEXT, "© Raskul - all rights reserved")
        html = render_site_copyright_footer_html()
        self.assertIn("Raskul", html)
        self.assertIn("all rights reserved", html)
        self.assertIn("©", html)
        self.assertNotIn("(c)", html)
        self.assertIn('id="site-footer"', html)
        self.assertIn("download map", html)
        self.assertIn("/downloads-map", html)
        self.assertNotIn("buymeacoffee.com", html)
        self.assertNotIn("bmc-tip-link", html)
        # render_coffee_link_html is back-compat alias → copyright + map
        alias = render_coffee_link_html()
        self.assertIn("Raskul", alias)
        self.assertNotIn("buymeacoffee.com", alias)
        css = coffee_link_css()
        self.assertIn("site-footer", css)
        self.assertIn("margin-top: auto", css)
        self.assertIn("space-between", css)
        # Narrow footer stays one row: copyright left, download map right
        self.assertIn("flex-wrap: nowrap", css)
        self.assertNotIn("flex-direction: column", css)
        self.assertIn("site-footer-inner", html)
        self.assertIn("site-footer-copyright", html)
        self.assertIn("site-footer-downloads-map", html)

    def test_public_page_footer_copyright_no_bmc(self):
        page = status_app.render_html(
            {"title": "RESTORE PRIVACY"}
        ).decode("utf-8")
        self.assertNotIn("buy rus a coffee", page)
        self.assertNotIn("buymeacoffee.com", page)
        self.assertNotIn("bmc-tip-link", page)
        self.assertIn("Raskul", page)
        self.assertIn("all rights reserved", page)
        self.assertIn('id="site-footer"', page)
        self.assertIn("download map", page)
        self.assertNotIn("fetch('/api/status'", page)
        self.assertNotIn("clients_connected", page)
        self.assertIn("RESTORE PRIVACY", page)
        self.assertIn("Download", page)


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
            return_value={"title": "RESTORE PRIVACY", "upstream_ok": True},
        ):
            for _ in range(2):
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{self._port}/", timeout=5
                ) as resp:
                    html = resp.read().decode("utf-8")
                self.assertNotIn("fetch('/api/status'", html)
                self.assertNotIn("buy rus a coffee", html)
                self.assertNotIn("buymeacoffee.com", html)
                self.assertIn("Raskul", html)
                self.assertIn("Download", html)
                self.assertIn("download map", html)


if __name__ == "__main__":
    unittest.main()
