"""Tests drive shipped status_page helpers (current count + dynamic poll)."""

from __future__ import annotations

import json
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


class TestCurrentCountOnly(unittest.TestCase):
    def test_normalize_uses_current_not_lifetime_total(self):
        # When both present, current session field wins — not a cumulative total
        out = status_app.normalize_status(
            {
                "title": "RESTORE PRIVACY",
                "clients_connected": 3,
                "total": 999,
                "lifetime_clients": 5000,
                "clients_total": 100,
            }
        )
        self.assertEqual(out["clients_connected"], 3)
        self.assertNotIn("total", out)
        self.assertNotIn("lifetime_clients", out)

    def test_public_payload_strips_identity_and_totals(self):
        safe = status_app.public_status_payload(
            {
                "title": "RESTORE PRIVACY",
                "clients_connected": 2,
                "ip": "1.2.3.4",
                "total": 50,
                "clients": [{"id": "x"}],
            }
        )
        self.assertEqual(set(safe.keys()), {"title", "clients_connected"})
        self.assertEqual(safe["clients_connected"], 2)

    def test_fetch_upstream_filters_fields(self):
        payload = json.dumps(
            {
                "title": "RESTORE PRIVACY",
                "clients_connected": 2,
                "ip": "should-not-appear",
                "total": 99,
            }
        ).encode("utf-8")

        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return payload

        with mock.patch("urllib.request.urlopen", return_value=Resp()):
            out = status_app.fetch_upstream_status()
        self.assertEqual(out["title"], "RESTORE PRIVACY")
        self.assertEqual(out["clients_connected"], 2)
        self.assertNotIn("ip", out)
        self.assertNotIn("total", out)

    def test_fetch_upstream_fallback_on_error(self):
        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError("down")):
            out = status_app.fetch_upstream_status()
        self.assertEqual(out["title"], "RESTORE PRIVACY")
        self.assertEqual(out["clients_connected"], 0)


class TestDynamicHtml(unittest.TestCase):
    def test_render_html_no_meta_refresh_has_poll(self):
        html = status_app.render_html(
            {"title": "RESTORE PRIVACY", "clients_connected": 7},
            poll_ms=3000,
        ).decode("utf-8")
        self.assertIn("RESTORE PRIVACY", html)
        self.assertIn("Currently connected clients", html)
        self.assertNotIn("total clients", html.lower())
        self.assertNotIn("lifetime clients", html.lower())
        self.assertNotIn("cumulative", html.lower())
        # No full-page reload as update mechanism
        self.assertNotIn('http-equiv="refresh"', html.lower())
        self.assertNotIn("http-equiv='refresh'", html.lower())
        # Client-side poll of status API + DOM update
        self.assertIn("fetch('/api/status'", html)
        self.assertIn("setInterval(poll", html)
        self.assertIn("clients_connected", html)
        self.assertIn('id="clients-connected"', html)
        self.assertIn("el.textContent", html)
        self.assertIn(">7<", html)

    def test_render_html_uses_shipped_poll_interval(self):
        html = status_app.render_html(
            {"title": "RESTORE PRIVACY", "clients_connected": 0},
            poll_ms=2500,
        ).decode("utf-8")
        self.assertIn("var pollMs = 2500;", html)


class TestHttpHandlers(unittest.TestCase):
    def setUp(self):
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        self._port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def tearDown(self):
        self._httpd.shutdown()
        self._httpd.server_close()

    def _get(self, path: str) -> tuple[int, str, str]:
        url = f"http://127.0.0.1:{self._port}{path}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, resp.headers.get("Content-Type", ""), body

    def test_api_and_html_twice(self):
        with mock.patch.object(
            status_app,
            "fetch_upstream_status",
            return_value={"title": "RESTORE PRIVACY", "clients_connected": 4},
        ):
            for _ in range(2):
                code, ctype, body = self._get("/api/status")
                self.assertEqual(code, 200)
                self.assertIn("json", ctype)
                data = json.loads(body)
                self.assertEqual(data["clients_connected"], 4)
                self.assertEqual(set(data.keys()), {"title", "clients_connected"})
                self.assertNotIn("total", data)

                code, ctype, html = self._get("/")
                self.assertEqual(code, 200)
                self.assertIn("html", ctype)
                self.assertIn("Currently connected clients", html)
                self.assertIn("fetch('/api/status'", html)
                self.assertNotIn('http-equiv="refresh"', html.lower())


if __name__ == "__main__":
    unittest.main()
