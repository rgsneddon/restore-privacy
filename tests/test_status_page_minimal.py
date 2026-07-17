"""Public status page is title + live client count only (no download links)."""

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


class TestMinimalPublicPage(unittest.TestCase):
    def test_render_has_title_and_count_poll_only(self):
        html = status_app.render_html(
            {"title": "RESTORE PRIVACY", "clients_connected": 3}
        ).decode("utf-8")
        self.assertIn("RESTORE PRIVACY", html)
        self.assertIn("Currently connected clients", html)
        self.assertIn('id="clients-connected"', html)
        self.assertIn(">3<", html)
        self.assertIn("fetch('/api/status'", html)
        self.assertIn("setInterval(poll", html)
        # No installer / download surfaces
        self.assertNotIn("releases/download/", html)
        self.assertNotIn("Download client", html)
        self.assertNotIn("connect-via-web", html)
        self.assertNotIn("Connect via web", html)
        self.assertNotIn("buymeacoffee.com", html)
        self.assertNotIn("buy rus a coffee", html)
        self.assertNotIn(".apk", html)
        self.assertNotIn(".zip", html)

    def test_handler_twice_minimal(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with mock.patch.object(
                status_app,
                "fetch_upstream_status",
                return_value={"title": "RESTORE PRIVACY", "clients_connected": 2},
            ):
                for _ in range(2):
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/", timeout=5
                    ) as resp:
                        html = resp.read().decode("utf-8")
                    self.assertIn("RESTORE PRIVACY", html)
                    self.assertIn("clients-connected", html)
                    self.assertIn("fetch('/api/status'", html)
                    self.assertNotIn("releases/download/", html)
                    self.assertNotIn("Download client", html)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
