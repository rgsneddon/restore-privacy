"""Under-title legal/audit links on the public status downloads page."""

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


class TestTitleLegalLinks(unittest.TestCase):
    def test_render_legal_links_below_headline(self):
        """Drive shipped render_html — legal/audit links sit after h1."""
        html = status_app.render_html(
            {"title": "RESTORE PRIVACY"}
        ).decode("utf-8")
        self.assertIn("RESTORE PRIVACY", html)
        # Old under-title copy removed
        self.assertNotIn("BETA - test phase - please report any bugs to", html)
        self.assertNotIn(
            "Download the client for your platform. No public live session counter",
            html,
        )
        self.assertNotIn('id="beta-note"', html)
        self.assertNotIn('class="tagline"', html)
        # New links
        frag = status_app.render_legal_links_html()
        self.assertIn(frag.strip(), html)
        self.assertIn("LICENCE", html)
        self.assertIn("PRIVACY POLICY", html)
        self.assertIn("SECURITY AUDIT", html)
        self.assertIn(status_app.LICENCE_URL, html)
        self.assertIn(status_app.PRIVACY_POLICY_URL, html)
        self.assertIn(status_app.SECURITY_AUDIT_URL, html)
        self.assertIn('id="doc-links"', html)
        self.assertIn('id="licence-link"', html)
        self.assertIn('id="privacy-link"', html)
        self.assertIn('id="audit-link"', html)
        # Order: h1 then doc-links
        h1_pos = html.find("<h1>")
        if h1_pos < 0:
            h1_pos = html.find("<h1 ")
        links_pos = html.find('id="doc-links"')
        self.assertGreater(h1_pos, 0)
        self.assertGreater(links_pos, h1_pos)
        # Downloads remain; live client count removed
        self.assertNotIn("clients-connected", html)
        self.assertNotIn("fetch('/api/status'", html)
        self.assertIn("Download client", html)

    def test_legal_url_constants_point_at_shipped_docs(self):
        self.assertTrue(
            status_app.LICENCE_URL.endswith("/LICENSE")
            or status_app.LICENCE_URL.endswith("/LICENSE/")
        )
        self.assertIn("PRIVACY_POLICY.md", status_app.PRIVACY_POLICY_URL)
        self.assertIn("audit.md", status_app.SECURITY_AUDIT_URL)
        self.assertIn("github.com/rgsneddon/restore-privacy", status_app.LICENCE_URL)
        # Labels
        self.assertEqual(status_app.LICENCE_LABEL, "LICENCE")
        self.assertEqual(status_app.PRIVACY_POLICY_LABEL, "PRIVACY POLICY")
        self.assertEqual(status_app.SECURITY_AUDIT_LABEL, "SECURITY AUDIT")

    def test_handler_twice_includes_legal_links(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with mock.patch.object(
                status_app,
                "fetch_upstream_status",
                return_value={"title": "RESTORE PRIVACY", "upstream_ok": True},
            ):
                for _ in range(2):
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/", timeout=5
                    ) as resp:
                        html = resp.read().decode("utf-8")
                    self.assertIn("RESTORE PRIVACY", html)
                    self.assertIn("LICENCE", html)
                    self.assertIn("PRIVACY POLICY", html)
                    self.assertIn("SECURITY AUDIT", html)
                    self.assertNotIn("BETA - test phase", html)
                    self.assertNotIn("clients-connected", html)
                    self.assertNotIn("fetch('/api/status'", html)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
