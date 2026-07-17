"""Tests for the Render status page app (real module paths)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import app as status_app  # noqa: E402


class TestStatusPage(unittest.TestCase):
    def test_render_html_contains_title_and_count(self):
        html = status_app.render_html(
            {"title": "RESTORE PRIVACY", "clients_connected": 7}
        ).decode("utf-8")
        self.assertIn("RESTORE PRIVACY", html)
        self.assertIn("Clients connected", html)
        self.assertIn(">7<", html)

    def test_fetch_upstream_filters_fields(self):
        payload = json.dumps(
            {
                "title": "RESTORE PRIVACY",
                "clients_connected": 2,
                "ip": "should-not-appear",
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

    def test_fetch_upstream_fallback_on_error(self):
        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError("down")):
            out = status_app.fetch_upstream_status()
        self.assertEqual(out["title"], "RESTORE PRIVACY")
        self.assertEqual(out["clients_connected"], 0)


if __name__ == "__main__":
    unittest.main()
