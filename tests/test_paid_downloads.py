"""Paid download: Stripe checkout fields, webhook grant, single-use tokens, admin auth."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
import unittest
import urllib.parse
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import admin_panel  # noqa: E402
import app as status_app  # noqa: E402
import payments  # noqa: E402
from downloads import (  # noqa: E402
    BMC_TIP_URL,
    PRICE_LABEL,
    available_downloads,
    render_download_section_html,
)


class TestPaidDownloadUI(unittest.TestCase):
    def test_buttons_are_paid_not_free_github_href(self):
        html = render_download_section_html()
        self.assertIn("£2.45", html)
        self.assertIn("GBP", html)
        self.assertIn(PRICE_LABEL, html)
        self.assertIn("data-price-pence=\"245\"", html)
        self.assertIn(BMC_TIP_URL, html)
        self.assertIn("buymeacoffee.com/rgsneddon", html)
        self.assertIn("Tip / support", html)
        for a in available_downloads():
            self.assertIn(f'href="/pay?platform={a.platform}"', html)
            # Must not be free permanent release download on the button
            self.assertNotIn(f'href="{a.url}"', html)
        self.assertNotIn('href="#"', html)
        # Page still cites the release as package source (not free button target)
        self.assertIn("releases/tag/v1.0.0", html)

    def test_status_page_html_paid_flow(self):
        page = status_app.render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn("/pay?platform=windows", page)
        self.assertIn("£2.45", page)
        self.assertIn(BMC_TIP_URL, page)
        self.assertNotIn(
            'href="https://github.com/rgsneddon/RUST-IN-PRIVACY/releases/download/v1.0.0/restore-privacy-rust-1.0.0-windows-x64.zip"',
            page,
        )


class TestCheckoutAmount(unittest.TestCase):
    def test_pricing_constants(self):
        fields = payments.checkout_amount_fields_for_tests()
        self.assertEqual(fields["amount_pence"], 245)
        self.assertEqual(fields["currency"], "gbp")
        self.assertEqual(fields["label"], "£2.45")

    def test_checkout_form_body_includes_245_gbp_and_platform(self):
        creq = payments.CheckoutRequest(
            platform="windows",
            filename="restore-privacy-rust-1.0.0-windows-x64.zip",
            success_url="https://example.test/success",
            cancel_url="https://example.test/cancel",
        )
        with mock.patch.dict(os.environ, {"STRIPE_PRICE_ID": ""}, clear=False):
            body = payments.build_checkout_form_body(creq).decode("utf-8")
        parsed = urllib.parse.parse_qs(body)
        self.assertEqual(parsed["line_items[0][price_data][unit_amount]"], ["245"])
        self.assertEqual(parsed["line_items[0][price_data][currency]"], ["gbp"])
        self.assertEqual(parsed["metadata[platform]"], ["windows"])
        self.assertEqual(
            parsed["metadata[filename]"],
            ["restore-privacy-rust-1.0.0-windows-x64.zip"],
        )
        self.assertEqual(parsed["metadata[amount_pence]"], ["245"])

    def test_create_checkout_session_drives_http_with_secret(self):
        captured: dict = {}

        def fake_post(url: str, headers: dict, body: bytes):
            captured["url"] = url
            captured["headers"] = headers
            captured["body"] = body
            return (
                200,
                json.dumps(
                    {
                        "id": "cs_test_123",
                        "url": "https://checkout.stripe.com/c/pay/cs_test_123",
                    }
                ).encode("utf-8"),
            )

        with mock.patch.dict(
            os.environ,
            {
                "STRIPE_SECRET_KEY": "sk_test_unit",
                "STRIPE_PRICE_ID": "",
                "RPT_PUBLIC_BASE_URL": "https://status.example",
            },
            clear=False,
        ):
            out = payments.create_checkout_session(
                "android", http_post=fake_post
            )
        self.assertEqual(out["amount_pence"], 245)
        self.assertEqual(out["currency"], "gbp")
        self.assertEqual(out["platform"], "android")
        self.assertTrue(out["filename"].endswith("android.apk"))
        self.assertIn("checkout.stripe.com", out["url"])
        self.assertEqual(captured["url"], "https://api.stripe.com/v1/checkout/sessions")
        self.assertIn("Bearer sk_test_unit", captured["headers"]["Authorization"])
        body = captured["body"].decode("utf-8")
        parsed = urllib.parse.parse_qs(body)
        self.assertEqual(parsed["line_items[0][price_data][unit_amount]"], ["245"])
        self.assertEqual(parsed["line_items[0][price_data][currency]"], ["gbp"])


class TestWebhookAndTokens(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._td.cleanup)
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        payments.init_db()

    def _sign(self, payload: bytes, secret: str, ts: int | None = None) -> str:
        t = int(ts if ts is not None else time.time())
        signed = f"{t}.".encode("utf-8") + payload
        sig = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
        return f"t={t},v1={sig}"

    def test_invalid_signature_does_not_grant(self):
        payload = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_x",
                        "metadata": {
                            "platform": "linux",
                            "filename": "restore-privacy-rust-1.0.0-linux-x64.tar.gz",
                            "amount_pence": "245",
                            "currency": "gbp",
                        },
                    }
                },
            }
        ).encode("utf-8")
        result = payments.handle_stripe_webhook(
            payload, "t=1,v1=deadbeef", secret="whsec_test"
        )
        self.assertFalse(result["ok"])
        self.assertFalse(result["granted"])
        self.assertEqual(result.get("error"), "invalid_signature")
        self.assertEqual(payments.list_recent_grants(), [])

    def test_valid_signature_grants_token_and_single_use(self):
        secret = "whsec_unit_secret"
        payload = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_paid_1",
                        "currency": "gbp",
                        "metadata": {
                            "platform": "windows",
                            "filename": "restore-privacy-rust-1.0.0-windows-x64.zip",
                            "amount_pence": "245",
                            "currency": "gbp",
                        },
                    }
                },
            }
        ).encode("utf-8")
        header = self._sign(payload, secret)
        result = payments.handle_stripe_webhook(
            payload, header, secret=secret, now=time.time()
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["granted"])
        token = result["token"]
        self.assertTrue(token)

        first = payments.redeem_download_token(token)
        self.assertIsNotNone(first)
        assert first is not None
        self.assertTrue(first["url"].endswith("windows-x64.zip"))
        self.assertEqual(first["amount_pence"], 245)

        second = payments.redeem_download_token(token)
        self.assertIsNone(second, "token must be single-use")

    def test_wrong_amount_metadata_refuses_grant(self):
        secret = "whsec_amt"
        payload = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_bad_amt",
                        "metadata": {
                            "platform": "ios",
                            "filename": "restore-privacy-rust-1.0.0-ios.zip",
                            "amount_pence": "999",
                            "currency": "gbp",
                        },
                    }
                },
            }
        ).encode("utf-8")
        header = self._sign(payload, secret)
        result = payments.handle_stripe_webhook(payload, header, secret=secret)
        self.assertTrue(result["ok"])
        self.assertFalse(result["granted"])


class TestAdminAuth(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._td.cleanup)
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        os.environ["RPT_ADMIN_USER"] = "ops"
        os.environ["RPT_ADMIN_PASSWORD"] = "correct-horse"
        os.environ["RPT_ADMIN_SESSION_SECRET"] = "session-secret-unit"

    def tearDown(self):
        for k in (
            "RPT_ADMIN_USER",
            "RPT_ADMIN_PASSWORD",
            "RPT_ADMIN_SESSION_SECRET",
        ):
            os.environ.pop(k, None)

    def test_wrong_password_denied(self):
        self.assertFalse(admin_panel.verify_credentials("ops", "wrong"))
        self.assertFalse(admin_panel.verify_credentials("nope", "correct-horse"))

    def test_correct_credentials_and_session(self):
        self.assertTrue(admin_panel.verify_credentials("ops", "correct-horse"))
        tok = admin_panel.mint_session_token()
        self.assertTrue(admin_panel.verify_session_token(tok))
        self.assertFalse(admin_panel.verify_session_token("0:x:fakesig"))

    def test_admin_html_lists_grants_callable(self):
        payments.init_db()
        payments.mint_download_token(
            filename="restore-privacy-rust-1.0.0-macos.zip",
            platform="macos",
            session_id="cs_admin",
        )
        html = admin_panel.render_admin_html().decode("utf-8")
        self.assertIn("admin-grants-table", html)
        self.assertIn("macos", html)
        self.assertIn("245", html)


class TestAdminHttpUnauthenticated(unittest.TestCase):
    def test_admin_get_without_session_shows_login_not_grants(self):
        os.environ["RPT_ADMIN_PASSWORD"] = "temp-admin-pass"
        os.environ["RPT_ADMIN_SESSION_SECRET"] = "temp-sess"
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
            port = httpd.server_address[1]
            import threading
            import urllib.request

            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/admin", timeout=5
                ) as resp:
                    body = resp.read().decode("utf-8")
                    code = resp.status
                self.assertEqual(code, 200)
                self.assertIn("admin-login-form", body)
                self.assertNotIn("admin-grants-table", body)
            finally:
                httpd.shutdown()
                httpd.server_close()
        finally:
            os.environ.pop("RPT_ADMIN_PASSWORD", None)
            os.environ.pop("RPT_ADMIN_SESSION_SECRET", None)


class TestHowtoDoc(unittest.TestCase):
    def test_howto_exists_and_names_gateway(self):
        doc = ROOT / "status_page" / "docs" / "PAID_DOWNLOADS_HOWTO.md"
        self.assertTrue(doc.is_file(), f"missing {doc}")
        text = doc.read_text(encoding="utf-8")
        self.assertIn("Stripe", text)
        self.assertIn("webhook", text.lower())
        self.assertIn("2.45", text)
        self.assertIn("245", text)
        self.assertIn("buymeacoffee.com/rgsneddon", text)
        self.assertIn("STRIPE_SECRET_KEY", text)
        self.assertIn("STRIPE_WEBHOOK_SECRET", text)
        self.assertIn("RPT_ADMIN_PASSWORD", text)


class TestBuyerSuccessFulfilment(unittest.TestCase):
    """After pay, /download/success?session_id=… must surface the real one-time link."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._td.cleanup)
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        payments.init_db()

    def _sign(self, payload: bytes, secret: str, ts: int | None = None) -> str:
        t = int(ts if ts is not None else time.time())
        signed = f"{t}.".encode("utf-8") + payload
        sig = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
        return f"t={t},v1={sig}"

    def test_find_grant_by_session_after_webhook(self):
        secret = "whsec_success"
        session_id = "cs_test_success_abc"
        payload = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": session_id,
                        "currency": "gbp",
                        "metadata": {
                            "platform": "linux",
                            "filename": "restore-privacy-rust-1.0.0-linux-x64.tar.gz",
                            "amount_pence": "245",
                            "currency": "gbp",
                        },
                    }
                },
            }
        ).encode("utf-8")
        result = payments.handle_stripe_webhook(
            payload, self._sign(payload, secret), secret=secret
        )
        self.assertTrue(result["granted"])
        token = result["token"]
        found = payments.find_grant_by_session(session_id)
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found["token"], token)
        self.assertEqual(found["download_path"], f"/download?token={token}")

    def test_success_page_shows_download_link_for_session_id(self):
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer

        secret = "whsec_page"
        session_id = "cs_test_page_xyz"
        payload = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": session_id,
                        "currency": "gbp",
                        "metadata": {
                            "platform": "windows",
                            "filename": "restore-privacy-rust-1.0.0-windows-x64.zip",
                            "amount_pence": "245",
                            "currency": "gbp",
                        },
                    }
                },
            }
        ).encode("utf-8")
        result = payments.handle_stripe_webhook(
            payload, self._sign(payload, secret), secret=secret
        )
        self.assertTrue(result["granted"])
        token = result["token"]

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            url = (
                f"http://127.0.0.1:{port}/download/success?"
                f"session_id={urllib.parse.quote(session_id)}&platform=windows"
            )
            with urllib.request.urlopen(url, timeout=15) as resp:
                body = resp.read().decode("utf-8")
                self.assertEqual(resp.status, 200)
            self.assertIn("pay-success", body)
            self.assertIn("success-download-link", body)
            self.assertIn(f"/download?token={token}", body)
            self.assertNotIn("pay-success-pending", body)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
