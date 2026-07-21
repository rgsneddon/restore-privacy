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
        pay_base = payments.stripe_payment_page_url()
        self.assertEqual(
            pay_base, "https://donate.stripe.com/cNi7sM4uOeWQ9TBe0q7kc00"
        )
        for a in available_downloads():
            href = payments.stripe_payment_page_href_for_platform(a.platform)
            self.assertIn(f'href="{href}"', html)
            self.assertIn(f"client_reference_id={a.platform}", href)
            self.assertIn("donate.stripe.com", href)
            self.assertNotIn(f'href="{a.url}"', html)
            self.assertNotIn(f'href="/pay?platform={a.platform}"', html)
        self.assertNotIn('href="#"', html)
        self.assertNotIn("catalog-version", html)
        self.assertNotIn("paid download only", html)
        # Version still in section h2; platforms in subtitle
        self.assertIn("Download client v0.3.3", html)
        self.assertIn("Windows | Linux | macOS | iOS | Android", html)
        self.assertIn("data-pay-via=\"stripe-payment-page\"", html)

    def test_status_page_html_paid_flow(self):
        page = status_app.render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn("donate.stripe.com/cNi7sM4uOeWQ9TBe0q7kc00", page)
        self.assertIn("client_reference_id=windows", page)
        self.assertIn("£2.45", page)
        self.assertIn(BMC_TIP_URL, page)
        self.assertNotIn(
            'href="https://github.com/rgsneddon/restore-privacy/releases/download/0.3.3/restore-privacy-client-0.3.3-windows-x64-setup.exe"',
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
            filename="restore-privacy-client-0.3.3-windows-x64-setup.exe",
            success_url="https://example.test/success",
            cancel_url="https://example.test/cancel",
        )
        with mock.patch.dict(os.environ, {"STRIPE_PRICE_ID": ""}, clear=False):
            body = payments.build_checkout_form_body(creq).decode("utf-8")
        parsed = urllib.parse.parse_qs(body)
        self.assertEqual(parsed["mode"], ["payment"])
        self.assertEqual(parsed["line_items[0][price_data][unit_amount]"], ["245"])
        self.assertEqual(parsed["line_items[0][price_data][currency]"], ["gbp"])
        self.assertEqual(parsed["metadata[platform]"], ["windows"])
        self.assertEqual(
            parsed["metadata[filename]"],
            ["restore-privacy-client-0.3.3-windows-x64-setup.exe"],
        )
        self.assertEqual(parsed["metadata[amount_pence]"], ["245"])

    def test_legacy_stripe_price_id_ignored_avoids_recurring_payment_mode_error(self):
        """STRIPE_PRICE_ID often holds a Payment Link recurring price — must not be used."""
        creq = payments.CheckoutRequest(
            platform="windows",
            filename="restore-privacy-client-0.2.3-windows-x64-setup.exe",
            success_url="https://example.test/success",
            cancel_url="https://example.test/cancel",
        )
        recurring = "price_1TvTsaJDavQ2TJW6HZVIG7hg"
        with mock.patch.dict(
            os.environ,
            {
                "STRIPE_PRICE_ID": recurring,
                "STRIPE_CHECKOUT_PRICE_ID": "",
                "STRIPE_ONE_TIME_PRICE_ID": "",
                "STRIPE_ALLOW_LEGACY_PRICE_ID": "",
            },
            clear=False,
        ):
            body = payments.build_checkout_form_body(creq).decode("utf-8")
            self.assertEqual(payments.stripe_price_id(), "")
        parsed = urllib.parse.parse_qs(body)
        self.assertEqual(parsed["mode"], ["payment"])
        self.assertNotIn("line_items[0][price]", parsed)
        self.assertEqual(parsed["line_items[0][price_data][unit_amount]"], ["245"])
        self.assertNotIn(recurring, body)

    def test_explicit_one_time_checkout_price_id_used(self):
        creq = payments.CheckoutRequest(
            platform="linux",
            filename="restore-privacy-client-0.2.3-linux-x64.tar.gz",
            success_url="https://example.test/success",
            cancel_url="https://example.test/cancel",
        )
        with mock.patch.dict(
            os.environ,
            {"STRIPE_CHECKOUT_PRICE_ID": "price_one_time_unit_test"},
            clear=False,
        ):
            body = payments.build_checkout_form_body(creq).decode("utf-8")
        parsed = urllib.parse.parse_qs(body)
        self.assertEqual(parsed["line_items[0][price]"], ["price_one_time_unit_test"])
        self.assertNotIn("line_items[0][price_data][unit_amount]", parsed)

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
        self._td = tempfile.TemporaryDirectory()
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
                            "filename": "restore-privacy-client-0.3.3-linux-x64.tar.gz",
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
                        "payment_status": "paid",
                        "currency": "gbp",
                        "metadata": {
                            "platform": "windows",
                            "filename": "restore-privacy-client-0.3.3-windows-x64-setup.exe",
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
        self.assertTrue(
            first["url"].endswith("windows-x64-setup.exe"),
            first["url"],
        )
        self.assertEqual(first["amount_pence"], 245)

        second = payments.redeem_download_token(token)
        self.assertIsNone(second, "token must be single-use")
        # Grant must embed the live catalog version
        from downloads import RELEASE_VERSION

        self.assertIn(RELEASE_VERSION, first["filename"])
        self.assertIn(RELEASE_VERSION, first["url"])

    def test_stale_metadata_filename_grants_current_catalog_only(self):
        """Webhook metadata with an old package name must still mint the current ship."""
        from downloads import RELEASE_VERSION, WINDOWS_EXE_FILENAME

        secret = "whsec_stale_meta"
        payload = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_stale_meta_1",
                        "payment_status": "paid",
                        "currency": "gbp",
                        "amount_total": 245,
                        "metadata": {
                            "platform": "windows",
                            # Stale prior catalog name — must not be granted as-is
                            "filename": "restore-privacy-client-0.2.9-windows-x64-setup.exe",
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
        self.assertTrue(result["ok"])
        self.assertTrue(result["granted"], result)
        grants = payments.list_recent_grants(5)
        self.assertTrue(grants)
        granted = grants[0]["filename"]
        self.assertEqual(granted, WINDOWS_EXE_FILENAME)
        self.assertIn(RELEASE_VERSION, granted)
        self.assertNotIn("0.2.9", granted)
        self.assertIsNone(
            payments.open_release_asset(
                "restore-privacy-client-0.2.9-windows-x64-setup.exe"
            )
        )

    def test_platform_filename_is_always_current_catalog_version(self):
        from downloads import RELEASE_VERSION, current_catalog_version

        self.assertEqual(current_catalog_version(), RELEASE_VERSION)
        for plat in ("windows", "android", "macos", "ios", "linux"):
            fname = payments.platform_filename(plat)
            self.assertIsNotNone(fname)
            assert fname is not None
            self.assertIn(RELEASE_VERSION, fname)
            self.assertIn(fname, payments.catalog_filenames())

    def test_wrong_amount_metadata_refuses_grant(self):
        secret = "whsec_amt"
        payload = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_bad_amt",
                        "payment_status": "paid",
                        "currency": "gbp",
                        "metadata": {
                            "platform": "ios",
                            "filename": "restore-privacy-client-0.3.3-ios.zip",
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

    def test_payment_link_client_reference_grants_platform_package(self):
        """Payment Link sets client_reference_id=platform; webhook mints that package only."""
        secret = "whsec_plink"
        payload = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_plink_windows_1",
                        "payment_status": "paid",
                        "currency": "gbp",
                        "amount_total": 245,
                        "client_reference_id": "windows",
                        "metadata": {},
                    }
                },
            }
        ).encode("utf-8")
        result = payments.handle_stripe_webhook(
            payload, self._sign(payload, secret), secret=secret
        )
        self.assertTrue(result["granted"], result)
        token = result["token"]
        grant = payments.redeem_download_token(token)
        self.assertIsNotNone(grant)
        assert grant is not None
        self.assertEqual(grant["platform"], "windows")
        self.assertTrue(str(grant["filename"]).endswith("windows-x64-setup.exe"))
        self.assertIsNone(payments.redeem_download_token(token))

    def test_payment_link_zero_amount_or_missing_status_refuses_grant(self):
        """Only if paid at full price — zero amount / blank status must not mint."""
        secret = "whsec_zero"
        # amount_total=0 must not be rewritten to 245
        payload_zero = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_zero_amt",
                        "payment_status": "paid",
                        "currency": "gbp",
                        "amount_total": 0,
                        "client_reference_id": "linux",
                        "metadata": {},
                    }
                },
            }
        ).encode("utf-8")
        r0 = payments.handle_stripe_webhook(
            payload_zero, self._sign(payload_zero, secret), secret=secret
        )
        self.assertTrue(r0["ok"])
        self.assertFalse(r0["granted"])
        self.assertIsNone(
            payments.process_checkout_completed_event(json.loads(payload_zero))
        )
        # missing payment_status must not mint
        payload_nostatus = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_no_status",
                        "currency": "gbp",
                        "amount_total": 245,
                        "client_reference_id": "linux",
                        "metadata": {},
                    }
                },
            }
        ).encode("utf-8")
        r1 = payments.handle_stripe_webhook(
            payload_nostatus, self._sign(payload_nostatus, secret), secret=secret
        )
        self.assertTrue(r1["ok"])
        self.assertFalse(r1["granted"])

    def test_payment_link_underpay_amount_total_refuses_grant(self):
        """amount_total must equal product PRICE_PENCE (245), not a lower paid amount."""
        secret = "whsec_under"
        payload = json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_underpay",
                        "payment_status": "paid",
                        "currency": "gbp",
                        "amount_total": 100,
                        "client_reference_id": "linux",
                        "metadata": {},
                    }
                },
            }
        ).encode("utf-8")
        result = payments.handle_stripe_webhook(
            payload, self._sign(payload, secret), secret=secret
        )
        self.assertTrue(result["ok"])
        self.assertFalse(result["granted"])
        self.assertIsNone(
            payments.process_checkout_completed_event(json.loads(payload))
        )
        self.assertEqual(payments.list_recent_grants(), [])


class TestAdminAuth(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
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
            filename="restore-privacy-client-0.3.3-macos.zip",
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
        self._td = tempfile.TemporaryDirectory()
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
                        "payment_status": "paid",
                        "currency": "gbp",
                        "metadata": {
                            "platform": "linux",
                            "filename": "restore-privacy-client-0.3.3-linux-x64.tar.gz",
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
                        "payment_status": "paid",
                        "currency": "gbp",
                        "metadata": {
                            "platform": "windows",
                            "filename": "restore-privacy-client-0.3.3-windows-x64-setup.exe",
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
            # Thank-you + auto-download + admin instruction
            self.assertIn("Thank you", body)
            self.assertIn("thank-you-heading", body)
            self.assertIn("run-as-admin-instruction", body)
            self.assertIn("run the file as administrator", body.lower())
            self.assertIn("auto-download-frame", body)
            self.assertNotIn("auto-download-script", body)
            self.assertNotIn(".click()", body)
            self.assertIn('id="auto-download-frame"', body)
            self.assertIn(f'src="/download?token={token}"', body)
            self.assertIn('data-manual-download="1"', body)
            self.assertNotIn("github.com/rgsneddon/restore-privacy/releases/download", body)
        finally:
            httpd.shutdown()
            httpd.server_close()


class TestAdminPageAccess(unittest.TestCase):
    def test_access_decision_wrong_and_valid_session(self):
        os.environ["RPT_ADMIN_PASSWORD"] = "gate-pass"
        os.environ["RPT_ADMIN_SESSION_SECRET"] = "gate-sess"
        try:
            self.assertEqual(
                admin_panel.admin_page_access(authenticated=False),
                "login_required",
            )
            self.assertEqual(
                admin_panel.admin_page_access(authenticated=True),
                "granted",
            )
            self.assertEqual(
                admin_panel.admin_page_access(
                    authenticated=True, enabled=False
                ),
                "disabled",
            )
            self.assertFalse(admin_panel.verify_credentials("admin", "wrong"))
            self.assertTrue(admin_panel.verify_credentials("admin", "gate-pass"))
            tok = admin_panel.mint_session_token()
            self.assertTrue(admin_panel.verify_session_token(tok))
            self.assertFalse(admin_panel.verify_session_token("bad:token:x"))
        finally:
            os.environ.pop("RPT_ADMIN_PASSWORD", None)
            os.environ.pop("RPT_ADMIN_SESSION_SECRET", None)


class TestProcessorSettingsView(unittest.TestCase):
    def setUp(self):
        self._saved = {
            k: os.environ.get(k)
            for k in (
                "STRIPE_SECRET_KEY",
                "STRIPE_WEBHOOK_SECRET",
                "STRIPE_PRICE_ID",
                "RPT_PUBLIC_BASE_URL",
            )
        }

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_unconfigured_flags(self):
        os.environ.pop("STRIPE_SECRET_KEY", None)
        os.environ.pop("STRIPE_WEBHOOK_SECRET", None)
        os.environ.pop("STRIPE_PRICE_ID", None)
        view = admin_panel.processor_settings_view()
        self.assertFalse(view["stripe_configured"])
        self.assertFalse(view["stripe_webhook_configured"])
        self.assertFalse(view["stripe_fulfilment_ready"])
        self.assertEqual(view["stripe_mode"], "unconfigured")
        self.assertFalse(view["secrets_in_view"])
        self.assertEqual(view["bmc_tip_url"], "https://buymeacoffee.com/rgsneddon")
        self.assertEqual(view["bmc_role"], "tip_support_only")

    def test_configured_test_mode_no_secret_in_html(self):
        secret = "sk_test_UNIT_FAKE_NOT_A_REAL_KEY_xyz"
        webhook = "whsec_UNIT_FAKE_NOT_A_REAL_SECRET"
        os.environ["STRIPE_SECRET_KEY"] = secret
        os.environ["STRIPE_WEBHOOK_SECRET"] = webhook
        os.environ["RPT_PUBLIC_BASE_URL"] = "https://example-status.test"
        view = admin_panel.processor_settings_view()
        self.assertTrue(view["stripe_configured"])
        self.assertTrue(view["stripe_webhook_configured"])
        self.assertTrue(view["stripe_fulfilment_ready"])
        self.assertEqual(view["stripe_mode"], "test")
        # View model must not carry raw secrets
        blob = json.dumps(view)
        self.assertNotIn(secret, blob)
        self.assertNotIn(webhook, blob)

        html = admin_panel.render_processor_settings_html(view)
        self.assertIn("admin-processor-settings", html)
        self.assertIn("id=\"stripe-key-mode\">test<", html)
        self.assertIn("dashboard.stripe.com", html)
        self.assertIn("buymeacoffee.com", html)
        # Plugin UI uses dashboard links (ids may include hyphenated labels)
        self.assertTrue(
            "link-stripe-apikeys" in html
            or "link-stripe-api-keys" in html
            or "dashboard.stripe.com/apikeys" in html,
            "stripe API keys link missing",
        )
        self.assertTrue(
            "link-bmc-login" in html
            or "link-bmc-creator-login" in html
            or "buymeacoffee.com/login" in html,
            "bmc login link missing",
        )
        self.assertNotIn(secret, html)
        self.assertNotIn(webhook, html)
        self.assertNotIn("sk_test_", html)
        self.assertNotIn("whsec_", html)

    def test_live_mode_label(self):
        os.environ["STRIPE_SECRET_KEY"] = "sk_live_UNIT_FAKE"
        self.assertEqual(admin_panel.stripe_key_mode_label(), "live")


class TestAdminHtmlArchitecture(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        os.environ["RPT_ADMIN_PASSWORD"] = "admin-arch"
        os.environ["RPT_ADMIN_SESSION_SECRET"] = "admin-arch-sess"
        os.environ.pop("STRIPE_SECRET_KEY", None)
        os.environ.pop("STRIPE_WEBHOOK_SECRET", None)

    def tearDown(self):
        for k in (
            "RPT_ADMIN_PASSWORD",
            "RPT_ADMIN_SESSION_SECRET",
            "RPT_PAYMENT_DATA_DIR",
        ):
            os.environ.pop(k, None)

    def test_authenticated_admin_has_settings_and_grants(self):
        payments.init_db()
        payments.mint_download_token(
            filename="restore-privacy-client-0.3.3-android.apk",
            platform="android",
            session_id="cs_arch_1",
        )
        html = admin_panel.render_admin_html().decode("utf-8")
        self.assertIn("admin-processor-settings", html)
        self.assertIn("admin-grants-table", html)
        self.assertIn("Payment administration", html)
        self.assertIn("android", html)
        self.assertIn("245", html)
        self.assertIn("bmc-tip-url", html)
        self.assertIn("stripe-checkout-ready", html)
        # No secret material
        self.assertNotIn("sk_live_", html)
        self.assertNotIn("sk_test_", html)
        self.assertNotIn("whsec_", html)
        self.assertNotIn("admin-arch", html)  # password must not appear

    def test_project_grants_uses_real_store(self):
        payments.init_db()
        tok = payments.mint_download_token(
            filename="restore-privacy-client-0.3.3-linux-x64.tar.gz",
            platform="linux",
            session_id="cs_proj",
        )
        rows = admin_panel.project_grants_for_admin(limit=10)
        self.assertTrue(any(r["token"] == tok and r["platform"] == "linux" for r in rows))


class TestPublicVsAdminSurface(unittest.TestCase):
    def test_public_html_has_no_admin_grants_or_processor_panel(self):
        html = status_app.render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertNotIn("admin-grants-table", html)
        self.assertNotIn("admin-processor-settings", html)
        self.assertNotIn("rpt_admin_session", html)
        self.assertNotIn("STRIPE_SECRET_KEY", html)
        self.assertNotIn("sk_live_", html)
        self.assertNotIn("whsec_", html)
        # Public may still mention paid flow / tip
        self.assertIn("RESTORE PRIVACY", html.upper() if "RESTORE" in html.upper() else html)


class TestAdminThemeAppearance(unittest.TestCase):
    """Device colour scheme + explicit light/dark preference on shipped admin pages."""

    def test_normalize_theme_mode(self):
        self.assertEqual(admin_panel.normalize_theme_mode("light"), "light")
        self.assertEqual(admin_panel.normalize_theme_mode("DARK"), "dark")
        self.assertEqual(admin_panel.normalize_theme_mode("system"), "system")
        self.assertEqual(admin_panel.normalize_theme_mode(None), "system")
        self.assertEqual(admin_panel.normalize_theme_mode("neon"), "system")

    def test_theme_css_follows_prefers_color_scheme(self):
        css = admin_panel.admin_theme_css()
        self.assertIn("prefers-color-scheme: dark", css)
        self.assertIn('[data-theme="light"]', css)
        self.assertIn('[data-theme="dark"]', css)
        self.assertIn("--bg:", css)

    def test_login_and_admin_ship_theme_picker(self):
        login = admin_panel.render_login_html().decode("utf-8")
        admin = admin_panel.render_admin_html(grants=[]).decode("utf-8")
        for html, label in ((login, "login"), (admin, "admin")):
            with self.subTest(page=label):
                self.assertIn("admin-theme-bar", html)
                self.assertIn("admin-theme-ask", html)
                self.assertIn("Prefer light or dark mode?", html)
                self.assertIn("theme-light", html)
                self.assertIn("theme-dark", html)
                self.assertIn("theme-system", html)
                self.assertIn("prefers-color-scheme", html)
                self.assertIn("color-scheme", html)
                self.assertIn(admin_panel.THEME_STORAGE_KEY, html)
                self.assertIn("admin-theme-script", html)
                self.assertIn("localStorage", html)


class TestAdminBootstrapDigest(unittest.TestCase):
    """Admin can enable via password digest without plaintext secret in git."""

    def setUp(self):
        self._saved = {
            k: os.environ.get(k)
            for k in (
                "RPT_ADMIN_PASSWORD",
                "RPT_ADMIN_PASSWORD_DIGEST",
                "RPT_ADMIN_DISABLE_BOOTSTRAP",
                "RPT_ADMIN_SESSION_SECRET",
                "RPT_ADMIN_USER",
            )
        }
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_digest_roundtrip_enables_admin_without_plaintext_env(self):
        # Ephemeral password for the test only — not the production secret fixture
        pw = "unit-bootstrap-password-not-prod"
        dig = admin_panel.make_password_digest(pw)
        os.environ["RPT_ADMIN_PASSWORD_DIGEST"] = dig
        os.environ.pop("RPT_ADMIN_PASSWORD", None)
        self.assertTrue(admin_panel.admin_enabled())
        self.assertTrue(admin_panel.verify_credentials("admin", pw))
        self.assertFalse(admin_panel.verify_credentials("admin", "wrong-password"))
        tok = admin_panel.mint_session_token()
        self.assertTrue(admin_panel.verify_session_token(tok))

    def test_disable_bootstrap_requires_env_password(self):
        os.environ["RPT_ADMIN_DISABLE_BOOTSTRAP"] = "1"
        os.environ.pop("RPT_ADMIN_PASSWORD", None)
        self.assertFalse(admin_panel.admin_enabled())
        os.environ["RPT_ADMIN_PASSWORD"] = "env-only-secret"
        self.assertTrue(admin_panel.admin_enabled())
        self.assertTrue(admin_panel.verify_credentials("admin", "env-only-secret"))

    def test_default_digest_ships_and_enables_without_env_password(self):
        os.environ.pop("RPT_ADMIN_PASSWORD", None)
        os.environ.pop("RPT_ADMIN_PASSWORD_DIGEST", None)
        os.environ.pop("RPT_ADMIN_DISABLE_BOOTSTRAP", None)
        dig = admin_panel.admin_password_digest()
        self.assertTrue(dig.startswith("pbkdf2_sha256$"))
        self.assertTrue(admin_panel.admin_enabled())
        # Digest string must not contain a plaintext password field
        self.assertNotIn("password=", dig.lower())
        html = admin_panel.render_login_html().decode("utf-8")
        self.assertIn("admin-login-form", html)

    def test_http_admin_login_form_when_bootstrap_enabled(self):
        os.environ.pop("RPT_ADMIN_PASSWORD", None)
        os.environ.pop("RPT_ADMIN_DISABLE_BOOTSTRAP", None)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        import threading
        import urllib.request

        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/admin", timeout=5) as resp:
                body = resp.read().decode("utf-8")
                code = resp.status
            self.assertEqual(code, 200)
            self.assertIn("admin-login-form", body)
            self.assertNotIn("admin disabled", body)
            self.assertNotIn("admin-grants-table", body)
        finally:
            httpd.shutdown()
            httpd.server_close()



class TestPrivateRepoProxyFulfilment(unittest.TestCase):
    """Paid redeem must proxy installers (local/API) — not free public GH redirects."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        os.environ["RPT_ASSET_DIR"] = self._td.name
        for k in ("RPT_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
            os.environ.pop(k, None)
        payments.init_db()

    def test_paid_fulfilment_mode_is_proxy(self):
        self.assertEqual(payments.paid_fulfilment_mode(), "proxy")

    def test_open_release_asset_from_local_dir(self):
        fname = "restore-privacy-client-0.3.3-linux-x64.tar.gz"
        payload = b"FAKE-LINUX-PACKAGE-BYTES-FOR-UNIT"
        (Path(self._td.name) / fname).write_bytes(payload)
        asset = payments.open_release_asset(fname)
        self.assertIsNotNone(asset)
        assert asset is not None
        self.assertEqual(asset["source"], "local")
        self.assertEqual(asset["filename"], fname)
        body = asset["body"]
        try:
            data = body.read() if hasattr(body, "read") else body
        finally:
            if hasattr(body, "close"):
                body.close()
        self.assertEqual(data, payload)

    def test_open_release_asset_rejects_unknown_filename(self):
        self.assertIsNone(payments.open_release_asset("not-a-catalog-file.exe"))

    def test_open_release_asset_rejects_stale_version_filename(self):
        """Prior catalog tags must not fulfil under the current pay path."""
        from downloads import RELEASE_VERSION

        stale = "restore-privacy-client-0.2.9-windows-x64-setup.exe"
        self.assertNotEqual(RELEASE_VERSION, "0.2.9")
        self.assertNotIn(stale, payments.catalog_filenames())
        self.assertIsNone(payments.open_release_asset(stale))
        for ver in ("0.2.3", "0.2.9", "0.1.8"):
            name = f"restore-privacy-client-{ver}-android.apk"
            self.assertIsNone(
                payments.open_release_asset(name),
                msg=f"must refuse stale {name}",
            )

    def test_open_release_asset_github_api_sends_auth_header(self):
        fname = "restore-privacy-client-0.3.3-windows-x64-setup.exe"
        os.environ["RPT_GITHUB_TOKEN"] = "unit-test-token"
        # Empty search dirs so we do not pick up real releases/0.3.3 on disk
        os.environ["RPT_ASSET_DIR"] = str(Path(self._td.name) / "empty_assets")
        Path(os.environ["RPT_ASSET_DIR"]).mkdir(parents=True, exist_ok=True)
        seen = []

        class FakeResp:
            def __init__(self, data: bytes, headers=None):
                self._data = data
                self.headers = headers or {}

            def read(self, n=-1):
                if n is None or n < 0:
                    out, self._data = self._data, b""
                    return out
                out, self._data = self._data[:n], self._data[n:]
                return out

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def close(self):
                pass

        def fake_urlopen(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else req.get_full_url()
            headers = {k.lower(): v for k, v in req.header_items()}
            seen.append((url, headers.get("authorization", "")))
            if url.endswith("/releases/tags/0.3.0"):
                body = json.dumps(
                    {"assets": [{"name": fname, "id": 424242}]}
                ).encode()
                return FakeResp(body, {"Content-Type": "application/json"})
            if url.endswith("/releases/assets/424242"):
                return FakeResp(b"EXE-BYTES", {"Content-Length": "9"})
            raise AssertionError(f"unexpected url {url}")

        with mock.patch.object(
            payments, "asset_search_dirs", return_value=[Path(os.environ["RPT_ASSET_DIR"])]
        ):
            asset = payments.open_release_asset(fname, urlopen=fake_urlopen)
        self.assertIsNotNone(asset)
        assert asset is not None
        self.assertEqual(asset["source"], "github_api")
        body = asset["body"]
        data = body.read() if hasattr(body, "read") else body
        if hasattr(body, "close"):
            body.close()
        self.assertEqual(data, b"EXE-BYTES")
        self.assertTrue(
            any(h.startswith("Bearer unit-test-token") for _, h in seen), seen
        )
        self.assertTrue(any("/releases/assets/424242" in u for u, _ in seen), seen)

    def test_http_download_streams_not_redirects_to_github(self):
        import threading
        import urllib.request

        fname = "restore-privacy-client-0.3.3-android.apk"
        payload = b"APK-UNIT-PAYLOAD"
        (Path(self._td.name) / fname).write_bytes(payload)
        token = payments.mint_download_token(
            filename=fname, platform="android", session_id="cs_unit_proxy"
        )
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/download?token={token}"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.assertEqual(resp.status, 200)
                self.assertNotIn("github.com", resp.geturl())
                body = resp.read()
                disp = resp.headers.get("Content-Disposition", "")
            self.assertEqual(body, payload)
            self.assertIn(fname, disp)
            with self.assertRaises(Exception):
                urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/download?token={token}", timeout=5
                )
        finally:
            httpd.shutdown()
            httpd.server_close()



class TestGrantNotBurnedOnFulfilmentFail(unittest.TestCase):
    """Proxy failure must not consume the single-use grant (lookup then consume)."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        os.environ["RPT_ASSET_DIR"] = str(Path(self._td.name) / "empty")
        Path(os.environ["RPT_ASSET_DIR"]).mkdir(parents=True, exist_ok=True)
        for k in ("RPT_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
            os.environ.pop(k, None)
        payments.init_db()

    def test_lookup_does_not_consume(self):
        fname = "restore-privacy-client-0.3.3-linux-x64.tar.gz"
        tok = payments.mint_download_token(
            filename=fname, platform="linux", session_id="cs_lookup"
        )
        g1 = payments.lookup_download_token(tok)
        g2 = payments.lookup_download_token(tok)
        self.assertIsNotNone(g1)
        self.assertIsNotNone(g2)
        self.assertEqual(g1["filename"], fname)
        # still consumable
        self.assertTrue(payments.consume_download_token(tok))
        self.assertIsNone(payments.lookup_download_token(tok))

    def test_http_502_leaves_token_reusable_then_success(self):
        import threading
        import urllib.error
        import urllib.request

        fname = "restore-privacy-client-0.3.3-macos.zip"
        tok = payments.mint_download_token(
            filename=fname, platform="macos", session_id="cs_noburn"
        )
        # No local asset, no token → open fails
        with mock.patch.object(
            payments, "asset_search_dirs", return_value=[Path(self._td.name) / "empty"]
        ):
            with mock.patch.object(payments, "github_auth_token", return_value=""):
                with mock.patch.object(
                    payments, "open_release_asset", return_value=None
                ):
                    # Need app to call open_release_asset from payments module
                    pass
        # Patch on status_app.open_release_asset since app imports the symbol
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with mock.patch.object(status_app, "open_release_asset", return_value=None):
                try:
                    urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/download?token={tok}", timeout=10
                    )
                    self.fail("expected HTTPError 502")
                except urllib.error.HTTPError as e:
                    self.assertEqual(e.code, 502)
                    body = e.read().decode("utf-8", errors="replace")
                    self.assertIn("download-fulfil-failed", body)
            # Grant still valid
            self.assertIsNotNone(payments.lookup_download_token(tok))
            # Stage asset and succeed
            payload = b"MACOS-ZIP-UNIT"
            (Path(self._td.name) / fname).write_bytes(payload)
            os.environ["RPT_ASSET_DIR"] = self._td.name
            with mock.patch.object(
                status_app,
                "open_release_asset",
                side_effect=lambda fn, **kw: payments.open_release_asset(fn, **kw),
            ):
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/download?token={tok}", timeout=10
                ) as resp:
                    self.assertEqual(resp.status, 200)
                    data = resp.read()
            self.assertEqual(data, payload)
            # Now burned
            self.assertIsNone(payments.lookup_download_token(tok))
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_check_fulfilment_ready_local(self):
        fname = "restore-privacy-client-0.3.3-ios.zip"
        (Path(self._td.name) / fname).write_bytes(b"PK\x03\x04ios-unit")
        os.environ["RPT_ASSET_DIR"] = self._td.name
        os.environ.pop("RPT_ASSET_FETCH_TOKEN", None)
        os.environ.pop("RPT_VPS_ASSET_TOKEN", None)
        ready = payments.check_fulfilment_ready()
        self.assertTrue(ready.get("ok"), ready)
        self.assertEqual(ready.get("source"), "local")
        self.assertIn("vps_token_configured", ready)
        self.assertFalse(ready.get("vps_token_configured"))

    def test_check_fulfilment_ready_reports_vps_token_configured(self):
        fname = "restore-privacy-client-0.3.3-linux-x64.tar.gz"
        (Path(self._td.name) / fname).write_bytes(b"FAKE-TGZ-UNIT")
        os.environ["RPT_ASSET_DIR"] = self._td.name
        os.environ["RPT_ASSET_FETCH_TOKEN"] = "unit-match-secret-not-prod"
        ready = payments.check_fulfilment_ready()
        self.assertTrue(ready.get("ok"), ready)
        self.assertTrue(ready.get("vps_token_configured"), ready)
        self.assertIn("vps_asset_base", ready)



class TestPostPaymentThankYouBuilder(unittest.TestCase):
    """Pure builder: thank you, auto-start paid path, run-as-administrator."""

    def test_builder_thankyou_admin_and_auto_start(self):
        html = payments.render_post_payment_thankyou_html(
            download_path="/download?token=unit_tok_abc",
            filename="restore-privacy-client-0.3.3-windows-x64-setup.exe",
            platform="windows",
        )
        self.assertIn("Thank you", html)
        self.assertIn("thank-you-heading", html)
        self.assertIn("pay-success", html)
        self.assertIn("restore-privacy-client-0.3.3-windows-x64-setup.exe", html)
        self.assertIn("run the file as administrator", html.lower())
        self.assertIn("Run as administrator", html)
        self.assertIn("auto-download-frame", html)
        self.assertIn('src="/download?token=unit_tok_abc"', html)
        self.assertIn("success-download-link", html)
        self.assertIn('href="/download?token=unit_tok_abc"', html)
        self.assertIn('data-manual-download="1"', html)
        # Exactly one auto-start: iframe only — no script click / meta refresh
        self.assertNotIn("auto-download-script", html)
        self.assertNotIn(".click()", html)
        self.assertNotIn("setTimeout", html)
        self.assertNotIn('http-equiv="refresh"', html.lower())
        self.assertEqual(html.count('id="auto-download-frame"'), 1)
        self.assertNotIn("github.com", html)
        self.assertNotIn("releases/download", html)

    def test_builder_rejects_external_free_url(self):
        with self.assertRaises(ValueError):
            payments.render_post_payment_thankyou_html(
                download_path=(
                    "https://github.com/rgsneddon/restore-privacy/releases/"
                    "download/0.3.0/restore-privacy-client-0.3.3-windows-x64-setup.exe"
                ),
                filename="x.exe",
                platform="windows",
            )

    def test_run_as_admin_windows_and_linux(self):
        w = payments.run_as_administrator_instruction(
            filename="restore-privacy-client-0.3.3-windows-x64-setup.exe",
            platform="windows",
        )
        self.assertIn("Run as administrator", w)
        l = payments.run_as_administrator_instruction(
            filename="restore-privacy-client-0.3.3-linux-x64.tar.gz",
            platform="linux",
        )
        self.assertIn("administrator", l.lower())
        self.assertIn("sudo", l.lower())

    def test_success_page_token_query_auto_starts(self):
        import threading
        import urllib.request

        fname = "restore-privacy-client-0.3.3-android.apk"
        tok = payments.mint_download_token(
            filename=fname, platform="android", session_id="cs_thank_tok"
        )
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{port}/pay/success?token={urllib.parse.quote(tok)}&platform=android"
            with urllib.request.urlopen(url, timeout=15) as resp:
                body = resp.read().decode("utf-8")
                self.assertEqual(resp.status, 200)
            self.assertIn("Thank you", body)
            self.assertIn("run the file as administrator", body.lower())
            self.assertIn(f"/download?token={tok}", body)
            self.assertIn("auto-download-frame", body)
            self.assertNotIn("auto-download-script", body)
            self.assertNotIn(".click()", body)
            self.assertNotIn("releases/download", body)
            # Success page itself does not consume; only iframe/manual /download does
            self.assertIsNotNone(payments.lookup_download_token(tok))
        finally:
            httpd.shutdown()
            httpd.server_close()



class TestPostPayAutoStartSingleConsume(unittest.TestCase):
    """Auto-start may consume the grant at most once; manual link is not pre-fired."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        os.environ["RPT_ASSET_DIR"] = self._td.name
        for k in ("RPT_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
            os.environ.pop(k, None)
        payments.init_db()

    def test_html_has_single_auto_start_iframe_not_script_click(self):
        html = payments.render_post_payment_thankyou_html(
            download_path="/download?token=once_only",
            filename="restore-privacy-client-0.3.3-windows-x64-setup.exe",
            platform="windows",
        )
        # Parse auto-start: only iframe src points at download; anchor is manual
        self.assertEqual(html.count('id="auto-download-frame"'), 1)
        self.assertIn('src="/download?token=once_only"', html)
        self.assertIn('data-manual-download="1"', html)
        self.assertNotIn("data-auto-download", html)
        self.assertNotIn(".click()", html)
        self.assertNotIn("setTimeout", html)
        # One paid path occurrence in iframe src + one in manual href = 2 href-like refs
        self.assertEqual(html.count("/download?token=once_only"), 2)

    def test_auto_start_path_consumes_grant_once_only(self):
        """Simulate iframe auto-start: one successful /download, second is 403.

        Happy path needs only that single request; manual link is not required
        and is not pre-fired by the success page HTML.
        """
        import threading
        import urllib.error
        import urllib.request

        fname = "restore-privacy-client-0.3.3-linux-x64.tar.gz"
        payload = b"LINUX-UNIT-AUTO-ONCE"
        (Path(self._td.name) / fname).write_bytes(payload)
        tok = payments.mint_download_token(
            filename=fname, platform="linux", session_id="cs_auto_once"
        )
        # Success page must not consume
        success_html = payments.render_post_payment_thankyou_html(
            download_path=f"/download?token={tok}",
            filename=fname,
            platform="linux",
        )
        self.assertIsNotNone(payments.lookup_download_token(tok))
        self.assertNotIn(".click()", success_html)

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            # HIT1: auto-start (iframe would load this URL once)
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/download?token={tok}", timeout=15
            ) as resp:
                self.assertEqual(resp.status, 200)
                body = resp.read()
            self.assertEqual(body, payload)
            self.assertIsNone(payments.lookup_download_token(tok))
            # HIT2: second request (e.g. accidental dual auto-start) fails
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/download?token={tok}", timeout=10
                )
            self.assertEqual(ctx.exception.code, 403)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_manual_link_works_when_auto_start_never_fired(self):
        """If iframe is blocked, grant remains and one manual click delivers."""
        import threading
        import urllib.request

        fname = "restore-privacy-client-0.3.3-ios.zip"
        payload = b"PK\x03\x04IOS-MANUAL"
        (Path(self._td.name) / fname).write_bytes(payload)
        tok = payments.mint_download_token(
            filename=fname, platform="ios", session_id="cs_manual_only"
        )
        # Render success page (does not hit /download)
        page = payments.render_post_payment_thankyou_html(
            download_path=f"/download?token={tok}",
            filename=fname,
            platform="ios",
        )
        self.assertIn("auto-download-frame", page)
        self.assertIsNotNone(payments.lookup_download_token(tok))

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), status_app.Handler)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            # User clicks manual link only (no prior auto-start request)
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/download?token={tok}", timeout=15
            ) as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.read(), payload)
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
