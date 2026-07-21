"""Public docs + how-to-buy served on the status host (Render)."""

from __future__ import annotations

import os
import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import app as status_app  # noqa: E402
import public_docs  # noqa: E402


class TestPublicDocsRegistry(unittest.TestCase):
    def test_catalog_paths_and_absolute_urls(self):
        cat = public_docs.public_docs_catalog()
        ids = {d["id"] for d in cat}
        self.assertTrue(
            {"readme", "licence", "privacy", "audit", "how-to-buy"}.issubset(ids)
        )
        for d in cat:
            self.assertTrue(d["path"].startswith("/"), d)
            self.assertIn("restore-privacy-status.onrender.com", d["url"])
            self.assertTrue(d["url"].endswith(d["path"]), d)

    def test_load_each_document_bytes(self):
        for name in (
            "README.md",
            "LICENSE",
            "PRIVACY_POLICY.md",
            "AUDIT.md",
            "CREDITS.md",
        ):
            data = public_docs.load_public_document_bytes(name)
            self.assertIsNotNone(data, name)
            assert data is not None
            self.assertGreater(len(data), 50, name)

    def test_document_bytes_for_path_registry(self):
        for path in (
            "/README.md",
            "/LICENSE",
            "/PRIVACY_POLICY.md",
            "/AUDIT.md",
            "/audit.md",
            "/CREDITS.md",
        ):
            got = public_docs.document_bytes_for_path(path)
            self.assertIsNotNone(got, path)
            assert got is not None
            body, ctype, title = got
            self.assertGreater(len(body), 50)
            self.assertTrue(ctype.startswith("text/"))
            self.assertTrue(title)


class TestHowToBuyAndHttp(unittest.TestCase):
    def test_how_to_buy_html_has_payment_and_docs(self):
        html = public_docs.render_how_to_buy_html().decode("utf-8")
        self.assertIn("how-to-buy-heading", html)
        self.assertIn("donate.stripe.com", html)
        self.assertIn("how-to-buy-payment-page", html)
        self.assertIn("/LICENSE", html)
        self.assertIn("/PRIVACY_POLICY.md", html)
        self.assertIn("/AUDIT.md", html)
        self.assertIn("/README.md", html)
        self.assertIn("checkout.session.completed", html)

    def test_handler_serves_docs_and_how_to_buy(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            for path in (
                "/how-to-buy",
                "/README.md",
                "/LICENSE",
                "/PRIVACY_POLICY.md",
                "/AUDIT.md",
                "/CREDITS.md",
            ):
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}{path}", timeout=10
                ) as resp:
                    body = resp.read()
                    self.assertEqual(resp.status, 200, path)
                    self.assertGreater(len(body), 40, path)
        finally:
            httpd.shutdown()
            httpd.server_close()


class TestPublicStatusLinks(unittest.TestCase):
    def test_status_html_links_are_same_origin_paths(self):
        html = status_app.render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn('id="licence-link" href="/LICENSE"', html)
        self.assertIn('id="privacy-link" href="/PRIVACY_POLICY.md"', html)
        self.assertIn('id="audit-link" href="/AUDIT.md"', html)
        self.assertIn('id="readme-link" href="/README.md"', html)
        self.assertIn('id="how-to-buy-link" href="/how-to-buy"', html)
        # Must not force private GitHub-only licence/privacy for public nav
        self.assertNotIn(
            'id="licence-link" href="https://github.com/rgsneddon/RUST-IN-PRIVACY',
            html,
        )

    def test_absolute_url_constants_use_status_origin(self):
        self.assertTrue(
            status_app.LICENCE_URL.endswith("/LICENSE")
            or status_app.LICENCE_URL.endswith("/LICENSE")
        )
        self.assertIn("restore-privacy-status.onrender.com", status_app.LICENCE_URL)
        self.assertIn("restore-privacy-status.onrender.com", status_app.SECURITY_AUDIT_URL)
        self.assertIn("/how-to-buy", status_app.HOW_TO_BUY_URL)


class TestClientLegalLinksStatusOrigin(unittest.TestCase):
    def test_legal_links_point_at_status_host(self):
        # Drive real client helper (repo root on path)
        sys.path.insert(0, str(ROOT))
        from client import legal_links

        os.environ.pop("RPT_PUBLIC_BASE_URL", None)
        urls = legal_links.legal_doc_urls()
        self.assertIn(legal_links.AUDIT_LABEL, urls)
        for u in urls.values():
            self.assertIn("restore-privacy-status.onrender.com", u)
            self.assertNotIn("github.com", u)
        self.assertTrue(legal_links.audit_url().endswith("/AUDIT.md"))
        self.assertTrue(legal_links.privacy_policy_url().endswith("/PRIVACY_POLICY.md"))
        self.assertTrue(legal_links.end_user_licence_url().endswith("/LICENSE"))
        self.assertTrue(legal_links.how_to_buy_url().endswith("/how-to-buy"))
        self.assertTrue(legal_links.readme_url().endswith("/README.md"))


if __name__ == "__main__":
    unittest.main()
