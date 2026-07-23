"""Security: no unpaid path to catalog installer bytes on the status host.

Drives the *shipped* download HTML builder, grant helpers, and HTTP handler —
not a re-implemented access oracle.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import app as status_app  # noqa: E402
import payments as pay  # noqa: E402
from downloads import available_downloads, render_download_section_html  # noqa: E402


def _paid_event(session_id: str = "cs_sec_paid", platform: str = "windows") -> dict:
    return {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "payment_status": "paid",
                "amount_total": pay.PRICE_PENCE,
                "currency": pay.PRICE_CURRENCY,
                "client_reference_id": platform,
                "metadata": {
                    "platform": platform,
                    "amount_pence": str(pay.PRICE_PENCE),
                    "currency": pay.PRICE_CURRENCY,
                },
            }
        },
    }


class _FakeHandler(status_app.Handler):
    """Minimal handler for in-process do_GET without real sockets."""

    def __init__(self, path: str):
        self.path = path
        self.headers = {}
        self.wfile = BytesIO()
        self.rfile = BytesIO()
        self.code: int | None = None
        self.sent_headers: dict[str, str] = {}

    def send_response(self, code: int, message: str | None = None) -> None:
        self.code = code

    def send_header(self, key: str, value: str) -> None:
        self.sent_headers[key] = value

    def end_headers(self) -> None:
        return

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _send(self, code: int, content_type: str, body: bytes) -> None:
        self.code = code
        self.sent_headers["Content-Type"] = content_type
        if isinstance(body, (bytes, bytearray)):
            self.wfile.write(body)
        else:
            self.wfile.write(bytes(body))

    def _redirect(self, url: str) -> None:
        self.code = 302
        self.sent_headers["Location"] = url

    def body_text(self) -> str:
        return self.wfile.getvalue().decode("utf-8", errors="replace")


class TestPublicHtmlNoFreeInstallerHrefs(unittest.TestCase):
    def test_homepage_downloads_html_is_paid_only(self):
        html = render_download_section_html()
        self.assertIn("data-pay-via", html)
        # Live catalog: Pay buttons (Stripe Payment Link); never free GitHub installers
        self.assertIn("BUY - 0.4.0", html)
        self.assertIn('data-buy-mode="stripe-live"', html)
        self.assertIn("buy.stripe.com", html)
        self.assertIn("client_reference_id=", html)
        self.assertNotIn("Coming soon", html)
        self.assertNotIn("releases/download/", html)
        for a in available_downloads():
            self.assertNotIn(f'href="{a.url}"', html)
            # Package basename may appear in data-filename; must not be free href
            self.assertNotIn(
                f'href="https://github.com/rgsneddon/restore-privacy/releases/download/',
                html,
            )
        page = status_app.render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertNotIn("releases/download/", page)
        self.assertIn("BUY - 0.4.0", page)
        self.assertIn("buy.stripe.com", page)
        self.assertNotIn("Coming soon", page)


class TestDownloadTokenDeniesUnpaid(unittest.TestCase):
    def test_lookup_consume_and_unpaid_mint(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["RPT_PAYMENT_DATA_DIR"] = td
            pay.init_db()
            self.assertIsNone(pay.lookup_download_token(""))
            self.assertIsNone(pay.lookup_download_token("forged-token-xyz"))
            self.assertFalse(pay.consume_download_token("forged-token-xyz"))

            # Underpay / unpaid must not mint
            unpaid = _paid_event("cs_unpaid", "linux")
            unpaid["data"]["object"]["payment_status"] = "unpaid"
            self.assertIsNone(pay.process_checkout_completed_event(unpaid))
            under = _paid_event("cs_under", "linux")
            under["data"]["object"]["amount_total"] = 1
            under["data"]["object"]["metadata"]["amount_pence"] = "1"
            self.assertIsNone(pay.process_checkout_completed_event(under))

            # Paid mints; single-use
            tok = pay.process_checkout_completed_event(_paid_event())
            self.assertTrue(tok)
            g = pay.lookup_download_token(tok)
            self.assertIsNotNone(g)
            self.assertIn(g["filename"], pay.catalog_filenames())
            self.assertTrue(pay.consume_download_token(tok))
            self.assertIsNone(pay.lookup_download_token(tok))
            self.assertFalse(pay.consume_download_token(tok))

            # Revoke blocks remaining grants
            tok2 = pay.process_checkout_completed_event(
                _paid_event("cs_rev", "android")
            )
            pay.revoke_connect_entitlement("cs_rev", reason="test", status="revoked")
            # grant status set to revoked for session
            g2 = pay.lookup_download_token(tok2)
            # revoke_connect updates grants with status='revoked'
            self.assertIsNone(g2)

            del os.environ["RPT_PAYMENT_DATA_DIR"]


class TestOpenReleaseAssetFilenameGuard(unittest.TestCase):
    def test_rejects_traversal_and_non_catalog(self):
        self.assertIsNone(pay._safe_catalog_filename("../etc/passwd"))
        self.assertIsNone(pay._safe_catalog_filename("foo/bar.exe"))
        self.assertIsNone(pay._safe_catalog_filename("not-a-package.exe"))
        self.assertIsNone(pay.open_release_asset("../../../etc/passwd"))
        self.assertIsNone(pay.open_release_asset("not-catalog.zip"))
        # Catalog names are accepted by the guard (open may still fail if not staged)
        name = available_downloads()[0].filename
        self.assertEqual(pay._safe_catalog_filename(name), name)


class TestHttpDownloadHandlerDeniesUnpaid(unittest.TestCase):
    def test_download_without_token_is_403(self):
        h = _FakeHandler("/download")
        h.do_GET()
        self.assertEqual(h.code, 403)
        self.assertIn("download-denied", h.body_text())

    def test_download_forged_token_is_403(self):
        h = _FakeHandler("/download?token=not-a-paid-grant")
        h.do_GET()
        self.assertEqual(h.code, 403)
        self.assertIn("download-denied", h.body_text())

    def test_public_assets_path_not_served(self):
        """Staged status_page/assets must not be reachable by bare URL."""
        name = available_downloads()[0].filename
        for path in (
            f"/assets/0.4.0/{name}",
            f"/static/../assets/0.4.0/{name}",
            f"/assets/{name}",
            f"/releases/0.4.0/{name}",
        ):
            h = _FakeHandler(path)
            h.do_GET()
            self.assertNotEqual(
                h.code,
                200,
                msg=f"unpaid path must not stream package: {path} -> {h.code}",
            )
            # Brand static is allow-listed only; package paths 404
            if h.code == 200:
                self.fail(f"unexpected 200 for {path}")

    def test_success_page_does_not_invent_download_for_forged_token(self):
        """Invalid token must not render auto-download iframe for packages."""
        h = _FakeHandler("/download/success?token=forged&platform=windows")
        h.do_GET()
        body = h.body_text()
        self.assertEqual(h.code, 200)
        self.assertNotIn("auto-download-frame", body)
        self.assertNotIn("success-download-link", body)
        self.assertIn("pay-success-invalid-token", body)
        # Must not link /download?token=forged as a fulfilment path
        self.assertNotIn("/download?token=forged", body)

    def test_paid_grant_still_redeems_once(self):
        """Happy path undisturbed: paid mint → /download streams once."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["RPT_PAYMENT_DATA_DIR"] = td
            tok = pay.process_checkout_completed_event(_paid_event("cs_happy"))
            self.assertTrue(tok)
            g = pay.lookup_download_token(tok)
            self.assertIsNotNone(g)
            fname = g["filename"]

            # Mock asset open so we do not depend on huge staged binaries
            fake_body = BytesIO(b"FAKE-INSTALLER-BYTES")

            def fake_open(name, **kwargs):
                self.assertEqual(name, fname)
                return {
                    "filename": fname,
                    "content_type": "application/octet-stream",
                    "content_length": 19,
                    "body": fake_body,
                    "source": "test",
                }

            with mock.patch.object(status_app, "open_release_asset", side_effect=fake_open):
                with mock.patch.object(pay, "open_release_asset", side_effect=fake_open):
                    # Handler imports open_release_asset from payments at module level
                    with mock.patch(
                        "app.open_release_asset", side_effect=fake_open
                    ):
                        h = _FakeHandler(f"/download?token={tok}")
                        h.do_GET()
            self.assertEqual(h.code, 200)
            self.assertEqual(h.wfile.getvalue(), b"FAKE-INSTALLER-BYTES")
            # Second redeem denied
            h2 = _FakeHandler(f"/download?token={tok}")
            with mock.patch("app.open_release_asset", side_effect=fake_open):
                h2.do_GET()
            self.assertEqual(h2.code, 403)

            del os.environ["RPT_PAYMENT_DATA_DIR"]


class TestServePaidAssetsRequiresToken(unittest.TestCase):
    def test_vps_handler_source_requires_token_and_safe_path(self):
        src = (ROOT / "node" / "serve_paid_assets.py").read_text(encoding="utf-8")
        self.assertIn("X-RPT-Asset-Token", src)
        self.assertIn("unauthorized", src)
        self.assertIn("relative_to", src)
        self.assertIn("paid-assets", src)


if __name__ == "__main__":
    unittest.main()
