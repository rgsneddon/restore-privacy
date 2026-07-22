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
            {"readme", "licence", "privacy", "audit"}.issubset(ids)
        )
        self.assertNotIn("how-to-buy", ids)
        for d in cat:
            self.assertTrue(d["path"].startswith("/"), d)
            self.assertIn("restoreprivacy.online", d["url"])
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
            self.assertTrue(ctype.startswith("text/html"), f"{path} -> {ctype}")
            self.assertTrue(title)
            html = body.decode("utf-8", errors="replace")
            self.assertIn("<!DOCTYPE html>", html)
            self.assertIn('id="doc-body"', html)
            self.assertIn("doc-top", html)

    def test_docs_are_readable_html_with_content(self):
        """Shipped renderer wraps privacy/audit/licence in a browser-friendly shell."""
        privacy = public_docs.document_bytes_for_path("/PRIVACY_POLICY.md")
        assert privacy is not None
        body, ctype, title = privacy
        self.assertIn("text/html", ctype)
        html = body.decode("utf-8")
        self.assertIn("Privacy", html)
        self.assertIn("0.3.7", html)
        self.assertIn("restoreprivacy.online", html)
        # No raw markdown dump as the sole body
        self.assertIn("<h1>", html.lower() + html)  # headings rendered
        self.assertIn("max-width", html)  # shell CSS for readability

        licence = public_docs.document_bytes_for_path("/LICENSE")
        assert licence is not None
        lhtml = licence[0].decode("utf-8")
        self.assertNotIn("MIT License", lhtml)
        self.assertIn("FULL COPYRIGHT", lhtml.upper())
        self.assertIn("ARCHITECTURE", lhtml.upper())
        self.assertIn("AS IS", lhtml)
        self.assertIn("doc-plain", lhtml)

        audit = public_docs.document_bytes_for_path("/AUDIT.md")
        assert audit is not None
        ahtml = audit[0].decode("utf-8")
        self.assertIn("Audit", ahtml)
        self.assertIn("0.3.7", ahtml)
        self.assertIn("doc-table", ahtml)  # tables rendered


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
                    ctype = resp.headers.get("Content-Type", "")
                    self.assertIn("text/html", ctype, f"{path} {ctype}")
                    html = body.decode("utf-8", errors="replace")
                    self.assertIn("<html", html.lower())
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
        self.assertNotIn("how-to-buy-link", html)
        self.assertNotIn('href="/how-to-buy"', html)
        self.assertNotIn("How to buy", html)
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
        self.assertIn("restoreprivacy.online", status_app.LICENCE_URL)
        self.assertIn("restoreprivacy.online", status_app.SECURITY_AUDIT_URL)


class TestClientLegalLinksStatusOrigin(unittest.TestCase):
    def test_legal_links_point_at_status_host(self):
        # Drive real client helper (repo root on path)
        sys.path.insert(0, str(ROOT))
        from client import legal_links

        os.environ.pop("RPT_PUBLIC_BASE_URL", None)
        urls = legal_links.legal_doc_urls()
        self.assertIn(legal_links.AUDIT_LABEL, urls)
        self.assertNotIn("How to buy", urls)
        for label, u in urls.items():
            self.assertIn("restoreprivacy.online", u)
            self.assertNotIn("github.com", u)
            self.assertNotIn("/how-to-buy", u, msg=label)
        self.assertTrue(legal_links.audit_url().endswith("/AUDIT.md"))
        self.assertTrue(legal_links.privacy_policy_url().endswith("/PRIVACY_POLICY.md"))
        self.assertTrue(legal_links.end_user_licence_url().endswith("/LICENSE"))
        self.assertTrue(legal_links.readme_url().endswith("/README.md"))
        self.assertFalse(hasattr(legal_links, "how_to_buy_url"))


if __name__ == "__main__":
    unittest.main()
