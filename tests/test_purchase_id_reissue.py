"""Unique product purchase identifier + admin secondary download reissue."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestPurchaseIdStoreAndReissue(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        import payments

        self.pay = payments
        self.pay.init_db()

    def tearDown(self):
        self._td.cleanup()
        os.environ.pop("RPT_PAYMENT_DATA_DIR", None)

    def test_two_purchases_get_distinct_purchase_ids(self):
        t1 = self.pay.mint_download_token(
            filename="restore-privacy-client-0.3.4-windows-x64-setup.exe",
            platform="windows",
            session_id="cs_test_1",
        )
        t2 = self.pay.mint_download_token(
            filename="restore-privacy-client-0.3.4-linux-x64.tar.gz",
            platform="linux",
            session_id="cs_test_2",
        )
        p1 = self.pay.purchase_id_for_token(t1)
        p2 = self.pay.purchase_id_for_token(t2)
        self.assertIsNotNone(p1)
        self.assertIsNotNone(p2)
        self.assertNotEqual(p1, p2)
        self.assertTrue(str(p1).startswith("RPT-"))
        self.assertTrue(str(p2).startswith("RPT-"))
        self.assertRegex(str(p1), r"^RPT-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}$")

    def test_reissue_mints_new_token_same_purchase_id(self):
        tok = self.pay.mint_download_token(
            filename="restore-privacy-client-0.3.4-android.apk",
            platform="android",
            session_id="cs_test_android",
        )
        pid = self.pay.purchase_id_for_token(tok)
        self.assertIsNotNone(pid)
        # Consume original token
        self.assertTrue(self.pay.consume_download_token(tok))
        self.assertIsNone(self.pay.lookup_download_token(tok))
        # Reissue secondary link
        issued = self.pay.reissue_download_for_purchase_id(
            str(pid), base_url="https://restoreprivacy.online"
        )
        self.assertIsNotNone(issued)
        assert issued is not None
        self.assertEqual(issued["purchase_id"], pid)
        self.assertEqual(issued["platform"], "android")
        self.assertNotEqual(issued["token"], tok)
        self.assertTrue(issued["download_path"].startswith("/download?token="))
        self.assertTrue(
            issued["download_url"].startswith(
                "https://restoreprivacy.online/download?token="
            )
        )
        self.assertNotIn("github.com", issued["download_url"])
        self.assertNotIn("releases/download", issued["download_url"])
        # New token redeemable
        g = self.pay.lookup_download_token(issued["token"])
        self.assertIsNotNone(g)
        self.assertEqual(g and g.get("platform"), "android")

    def test_unknown_purchase_id_fails_closed(self):
        self.assertIsNone(
            self.pay.reissue_download_for_purchase_id("RPT-DEAD-BEEF-0000")
        )
        self.assertIsNone(self.pay.find_paid_purchase_by_id(""))
        self.assertIsNone(self.pay.find_paid_purchase_by_id("not-an-id"))

    def test_checkout_webhook_stores_purchase_id(self):
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_live_purchase_id_test",
                    "payment_status": "paid",
                    "amount_total": 245,
                    "currency": "gbp",
                    "client_reference_id": "windows",
                    "metadata": {},
                }
            },
        }
        token = self.pay.process_checkout_completed_event(event)
        self.assertIsNotNone(token)
        pid = self.pay.purchase_id_for_token(str(token))
        self.assertIsNotNone(pid)
        found = self.pay.find_grant_by_session("cs_live_purchase_id_test")
        self.assertIsNotNone(found)
        self.assertEqual(found and found.get("purchase_id"), pid)


class TestPurchaseIdBuyerUi(unittest.TestCase):
    def test_thankyou_shows_purchase_id_and_strong_advice(self):
        from payments import render_post_payment_thankyou_html

        html = render_post_payment_thankyou_html(
            download_path="/download?token=abcTOKEN123",
            filename="restore-privacy-client-0.3.4-linux-x64.tar.gz",
            platform="linux",
            session_id="cs_test_ty",
            purchase_id="RPT-A1B2-C3D4-E5F6",
        )
        self.assertIn("product-purchase-id", html)
        self.assertIn("RPT-A1B2-C3D4-E5F6", html)
        self.assertIn("purchase-id-advice", html)
        self.assertIn("STRONG ADVICE", html)
        self.assertIn("SAVE THIS IDENTIFIER", html)
        self.assertIn("secondary download", html.lower())
        self.assertIn("/download?token=abcTOKEN123", html)
        self.assertNotIn("releases/download/", html)
        self.assertNotIn("github.com/rgsneddon", html)


class TestAdminReissueUi(unittest.TestCase):
    def test_reissue_form_is_top_of_admin_page(self):
        from admin_panel import render_admin_html, render_purchase_reissue_section_html

        page = render_admin_html().decode("utf-8")
        self.assertIn("admin-reissue", page)
        self.assertIn("admin-reissue-form", page)
        self.assertIn("purchase_id", page)
        self.assertIn("Re-issue download by purchase identifier", page)
        # Top of page: reissue section card before grants and processor settings sections
        reissue_at = page.find('id="admin-reissue"')
        grants_at = page.find('id="admin-grants"')
        # Prefer the processor settings section marker if present (not only nav href)
        proc_at = page.find('id="admin-processor-settings"')
        self.assertGreater(reissue_at, 0)
        self.assertGreater(grants_at, reissue_at)
        # Nav may mention processor settings before the reissue card; body order is
        # reissue HTML then settings_html — ensure reissue appears before grants card.
        self.assertLess(reissue_at, grants_at)
        # Reissue form is first card after nav (settings_html follows reissue_html)
        body_after_nav = page[page.find('id="admin-nav"') :]
        self.assertLess(
            body_after_nav.find("admin-reissue"),
            body_after_nav.find("admin-grants"),
        )
        # Success path fragment
        frag = render_purchase_reissue_section_html(
            result={
                "purchase_id": "RPT-1111-2222-3333",
                "download_url": "https://restoreprivacy.online/download?token=xyz",
                "download_path": "/download?token=xyz",
                "platform": "windows",
                "filename": "restore-privacy-client-0.3.4-windows-x64-setup.exe",
            }
        )
        self.assertIn("reissue-download-link", frag)
        self.assertIn("https://restoreprivacy.online/download?token=xyz", frag)
        self.assertNotIn("releases/download/", frag)
        # Failure fragment
        bad = render_purchase_reissue_section_html(error="No paid purchase found")
        self.assertIn("reissue-error", bad)
        self.assertIn("No paid purchase found", bad)

    def test_admin_post_reissue_handler(self):
        """Drive real app Handler POST /admin/reissue-download with auth."""
        import io
        from http.server import BaseHTTPRequestHandler

        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        os.environ["RPT_PAYMENT_DATA_DIR"] = td.name
        os.environ["RPT_ADMIN_PASSWORD"] = "test-admin-pass-xyz"
        os.environ["RPT_ADMIN_USERNAME"] = "admin"
        try:
            import payments
            from admin_panel import mint_session_token, SESSION_COOKIE
            import app as status_app

            payments.init_db()
            tok = payments.mint_download_token(
                filename="restore-privacy-client-0.3.4-macos.zip",
                platform="macos",
                session_id="cs_admin_reissue",
            )
            pid = payments.purchase_id_for_token(tok)
            self.assertIsNotNone(pid)

            session = mint_session_token()
            body = f"purchase_id={pid}".encode("utf-8")

            class FakeHandler(status_app.Handler):
                def __init__(self):
                    self.headers = {
                        "Content-Length": str(len(body)),
                        "Cookie": f"{SESSION_COOKIE}={session}",
                    }
                    self.rfile = io.BytesIO(body)
                    self.wfile = io.BytesIO()
                    self.requestline = "POST /admin/reissue-download HTTP/1.1"
                    self.command = "POST"
                    self.path = "/admin/reissue-download"
                    self.request_version = "HTTP/1.1"
                    self.client_address = ("127.0.0.1", 0)
                    self._code = None
                    self._headers_out: list[tuple[str, str]] = []

                def send_response(self, code, message=None):
                    self._code = code

                def send_header(self, keyword, value):
                    self._headers_out.append((keyword, value))

                def end_headers(self):
                    pass

                def log_message(self, *args):
                    return

            # Patch is_authenticated / admin_enabled
            with mock.patch.object(status_app, "admin_enabled", return_value=True):
                with mock.patch.object(
                    status_app, "is_authenticated", return_value=True
                ):
                    h = FakeHandler()
                    # Minimal do_POST path: call the reissue branch via do_POST
                    h.do_POST()
            out = h.wfile.getvalue().decode("utf-8", errors="replace")
            self.assertEqual(h._code, 200)
            self.assertIn("reissue-download-link", out)
            self.assertIn("/download?token=", out)
            self.assertIn(str(pid), out)
            self.assertNotIn("releases/download/", out)
        finally:
            os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
            os.environ.pop("RPT_ADMIN_PASSWORD", None)
            os.environ.pop("RPT_ADMIN_USERNAME", None)


if __name__ == "__main__":
    unittest.main()
