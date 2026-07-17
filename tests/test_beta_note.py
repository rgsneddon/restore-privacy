"""BETA note under RESTORE PRIVACY on the public status page."""

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


class TestBetaNote(unittest.TestCase):
    def test_render_beta_note_below_headline(self):
        """Drive shipped render_html — note sits after h1 with objective wording."""
        html = status_app.render_html(
            {"title": "RESTORE PRIVACY", "clients_connected": 1}
        ).decode("utf-8")
        self.assertIn("RESTORE PRIVACY", html)
        # Shipped fragment
        note = status_app.render_beta_note_html()
        self.assertIn(note.strip(), html)
        self.assertIn(
            "BETA - test phase - please report any bugs to",
            html,
        )
        self.assertIn("https://x.com/rgsneddon", html)
        self.assertIn('href="https://x.com/rgsneddon"', html)
        self.assertIn('id="beta-note"', html)
        # Immediately below headline: h1 then beta-note in body order
        h1_pos = html.find("<h1>")
        if h1_pos < 0:
            h1_pos = html.find("<h1 ")
        note_pos = html.find('id="beta-note"')
        self.assertGreater(h1_pos, 0)
        self.assertGreater(note_pos, h1_pos)
        # Existing surface still present
        self.assertIn("clients-connected", html)
        self.assertIn("fetch('/api/status'", html)
        self.assertIn("Download client", html)

    def test_beta_constants_match_objective(self):
        self.assertIn(
            "BETA - test phase - please report any bugs to",
            status_app.BETA_NOTE_TEXT,
        )
        self.assertEqual(status_app.BETA_NOTE_URL, "https://x.com/rgsneddon")
        self.assertIn(status_app.BETA_NOTE_URL, status_app.BETA_NOTE_TEXT)

    def test_handler_twice_includes_beta_note(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with mock.patch.object(
                status_app,
                "fetch_upstream_status",
                return_value={"title": "RESTORE PRIVACY", "clients_connected": 0},
            ):
                for _ in range(2):
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/", timeout=5
                    ) as resp:
                        html = resp.read().decode("utf-8")
                    self.assertIn("RESTORE PRIVACY", html)
                    self.assertIn(
                        "BETA - test phase - please report any bugs to",
                        html,
                    )
                    self.assertIn("https://x.com/rgsneddon", html)
                    self.assertIn("clients-connected", html)
                    self.assertIn("fetch('/api/status'", html)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
