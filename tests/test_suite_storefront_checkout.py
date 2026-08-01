"""Restore Privacy Suite storefront + Stripe product_line + entitlement inheritance."""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
import urllib.parse
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT / "client"))


class TestSuiteStorefrontOrder(unittest.TestCase):
    def test_suite_section_precedes_vpn_downloads_in_render_html(self):
        from app import render_html
        from downloads import (
            DOWNLOADS_SECTION_ID,
            SUITE_SECTION_ID,
            SUITE_PRODUCT_TITLE,
            SUITE_FREE_DOWNLOAD_PATH,
        )

        html = render_html({"title": "RESTORE PRIVACY VPN"}).decode("utf-8")
        suite_at = html.find(f'id="{SUITE_SECTION_ID}"')
        vpn_at = html.find(f'id="{DOWNLOADS_SECTION_ID}"')
        self.assertGreaterEqual(suite_at, 0, "suite-storefront missing")
        self.assertGreaterEqual(vpn_at, 0, "downloads section missing")
        self.assertLess(suite_at, vpn_at, "Suite must appear above VPN downloads")
        self.assertIn(SUITE_PRODUCT_TITLE, html)
        self.assertIn('data-free-download="1"', html)
        self.assertIn(SUITE_FREE_DOWNLOAD_PATH, html)
        self.assertIn("Get KEYGEN", html)
        self.assertIn('name="product" value="suite"', html)
        self.assertIn('name="interval" value="month"', html)
        # Cart entry: GET /pay (not direct POST checkout with silent auto_renew)
        self.assertIn('id="suite-keygen-form"', html)
        self.assertIn('action="/pay"', html)
        self.assertIn('method="get"', html.lower())
        self.assertIn('data-cart-step="1"', html)
        self.assertNotIn(
            'id="suite-auto-renew-field"',
            html,
            msg="homepage suite CTA must not force auto_renew via hidden field",
        )
        # VPN shop section id/role preserved
        self.assertIn('id="downloads"', html)
        self.assertIn("Download Suite client", html)

    def test_suite_storefront_helper_emits_free_download_and_keygen(self):
        from downloads import (
            PRICE_LABEL,
            render_suite_storefront_html,
            SUITE_PRODUCT_TITLE,
            SUITE_FREE_DOWNLOAD_PATH,
        )

        block = render_suite_storefront_html(default_platform="windows")
        self.assertIn(SUITE_PRODUCT_TITLE, block)
        self.assertIn(PRICE_LABEL, block)
        self.assertIn('data-product="suite"', block)
        self.assertIn('data-free-download="1"', block)
        self.assertIn(SUITE_FREE_DOWNLOAD_PATH, block)
        self.assertIn("KEYGEN", block)
        self.assertIn("Evolve", block)
        self.assertNotIn("coming soon", block.lower())
        # Monthly licence cart entry (GET /pay) — not direct checkout post
        self.assertIn('value="month"', block)
        self.assertIn('action="/pay"', block)
        self.assertIn('method="get"', block.lower())
        self.assertNotIn("suite-plan-year", block)
        self.assertNotIn(
            'name="auto_renew" value="1" id="suite-auto-renew-field"',
            block,
        )


class TestSuiteKeygenCartMarkup(unittest.TestCase):
    """Homepage Get KEYGEN → cart step with visible auto-renew (not 502 post)."""

    def test_suite_keygen_cta_is_get_pay_cart_not_hidden_autorenew_checkout(self):
        from downloads import AUTO_RENEW_LABEL, render_suite_storefront_html
        from payments import render_pay_plan_page_html

        suite = render_suite_storefront_html(default_platform="macos")
        # Cart entry markup
        self.assertIn('id="suite-keygen-form"', suite)
        self.assertIn('action="/pay"', suite)
        self.assertRegex(suite, r'method\s*=\s*["\']get["\']', msg=suite[:400])
        self.assertIn('name="product" value="suite"', suite)
        self.assertIn('name="interval" value="month"', suite)
        self.assertIn("Device for KEYGEN licence", suite)
        self.assertIn("Get KEYGEN", suite)
        # No silent force auto-renew on homepage CTA
        self.assertNotIn('id="suite-auto-renew-field"', suite)
        self.assertNotIn('action="/pay/checkout"', suite)

        # Cart page: monthly default + explicit auto-renew control + product=suite
        cart = render_pay_plan_page_html(
            "macos", interval="month", product="suite"
        ).decode("utf-8")
        self.assertIn('data-cart="1"', cart)
        self.assertIn('data-product="suite"', cart)
        self.assertIn('name="product" value="suite"', cart)
        self.assertIn('id="pay-auto-renew"', cart)
        self.assertIn(AUTO_RENEW_LABEL, cart)
        self.assertIn('name="auto_renew"', cart)
        self.assertIn('value="month"', cart)
        self.assertIn('action="/pay/checkout"', cart)
        self.assertIn("Continue to secure checkout", cart)
        # Visible on/off: hidden 0 + checkbox 1 pattern (same as VPN buy form)
        self.assertIn('id="pay-auto-renew-off"', cart)
        self.assertIn('value="0"', cart)


class TestSuitePayCheckoutHandler(unittest.TestCase):
    """POST /pay/checkout via Handler: mock Stripe success/fail → redirect, not crash."""

    def _post_checkout(
        self,
        form: dict[str, str],
        *,
        env: dict[str, str] | None = None,
        session_fn=None,
    ) -> tuple[int, str, bytes]:
        import os
        from http.server import ThreadingHTTPServer
        from threading import Thread
        from urllib import error, request

        from app import Handler

        prev = {
            k: os.environ.get(k) for k in ("STRIPE_SECRET_KEY", "RPT_PUBLIC_BASE_URL")
        }
        patches: list[Any] = []
        try:
            if env is not None:
                for k, v in env.items():
                    if v is None or v == "":
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
            else:
                os.environ["STRIPE_SECRET_KEY"] = "sk_test_cart_unit"
                os.environ.setdefault(
                    "RPT_PUBLIC_BASE_URL", "https://restoreprivacy.online"
                )

            if session_fn is not None:
                # Handler imports create_subscription_checkout_session locally
                # from payments at call time.
                p = mock.patch(
                    "payments.create_subscription_checkout_session", session_fn
                )
                p.start()
                patches.append(p)

            httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            port = httpd.server_address[1]
            t = Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            try:
                body = urllib.parse.urlencode(form).encode("utf-8")
                req = request.Request(
                    f"http://127.0.0.1:{port}/pay/checkout",
                    data=body,
                    method="POST",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                class _NoRedirect(request.HTTPRedirectHandler):
                    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, N802
                        return None

                opener = request.build_opener(_NoRedirect)
                try:
                    with opener.open(req, timeout=8) as resp:
                        return (
                            resp.getcode(),
                            resp.headers.get("Location") or "",
                            resp.read(),
                        )
                except error.HTTPError as e:
                    loc = e.headers.get("Location") if e.headers else ""
                    return e.code, loc or "", e.read()
            finally:
                httpd.shutdown()
        finally:
            for p in patches:
                p.stop()
            for k, v in prev.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_checkout_success_redirects_to_mock_stripe_url_auto_renew_both(self):
        from payments import create_subscription_checkout_session

        captured: list[bytes] = []

        def fake_post(url, headers, body):  # noqa: ARG001
            captured.append(body)
            return (
                200,
                b'{"id":"cs_test_cart","url":"https://checkout.stripe.com/c/pay/cs_test_cart"}',
            )

        def session_fn(platform, **kwargs):  # noqa: ANN001
            kwargs = dict(kwargs)
            kwargs["http_post"] = fake_post
            kwargs["base_url"] = "https://restoreprivacy.online"
            return create_subscription_checkout_session(platform, **kwargs)

        for renew in ("1", "0"):
            with self.subTest(auto_renew=renew):
                captured.clear()
                code, loc, _ = self._post_checkout(
                    {
                        "platform": "macos",
                        "interval": "month",
                        "product": "suite",
                        "auto_renew": renew,
                    },
                    session_fn=session_fn,
                )
                self.assertIn(code, (302, 303))
                self.assertIn("checkout.stripe.com", loc)
                self.assertTrue(captured)
                fields = urllib.parse.parse_qs(captured[-1].decode("utf-8"))
                self.assertEqual(fields.get("metadata[product_line]"), ["suite"])
                self.assertEqual(fields.get("metadata[auto_renew]"), [renew])

    def test_checkout_stripe_failure_redirects_to_pay_with_error(self):
        def boom(**_kwargs):  # noqa: ANN001
            raise ValueError("stripe checkout create failed HTTP 500: boom")

        code, loc, body = self._post_checkout(
            {
                "platform": "windows",
                "interval": "month",
                "product": "suite",
                "auto_renew": "1",
            },
            session_fn=boom,
        )
        self.assertIn(code, (302, 303))
        self.assertIn("/pay?", loc)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
        self.assertEqual(q.get("product"), ["suite"])
        self.assertEqual(q.get("platform"), ["windows"])
        err = (q.get("error") or [""])[0]
        self.assertTrue(err, msg=f"expected error on cart redirect: {loc}")
        self.assertNotIn(b"502 Bad Gateway", body[:400] if body else b"")

    def test_checkout_uncaught_style_exception_still_redirects(self):
        def raise_net(**_kwargs):  # noqa: ANN001
            raise OSError("simulated stripe network down")

        code, loc, _ = self._post_checkout(
            {
                "platform": "linux",
                "interval": "month",
                "product": "suite",
                "auto_renew": "0",
            },
            session_fn=raise_net,
        )
        self.assertIn(code, (302, 303))
        self.assertIn("/pay?", loc)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
        self.assertIn("error", q)
        self.assertEqual(q.get("product"), ["suite"])

    def test_checkout_unconfigured_stripe_redirects_to_pay(self):
        code, loc, _ = self._post_checkout(
            {
                "platform": "macos",
                "interval": "month",
                "product": "suite",
                "auto_renew": "1",
            },
            env={"STRIPE_SECRET_KEY": ""},
        )
        self.assertIn(code, (302, 303))
        self.assertIn("/pay?", loc)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
        self.assertIn("error", q)
        self.assertIn("unavailable", q["error"][0].lower())


class TestSuiteStripeCheckout(unittest.TestCase):
    def test_encode_parse_suite_client_reference(self):
        from payments import (
            encode_client_reference_id,
            parse_client_reference_id,
            parse_product_line_from_client_reference,
            PRODUCT_LINE_SUITE,
            PRODUCT_LINE_VPN,
        )

        ref = encode_client_reference_id(
            "windows", interval="month", product_line=PRODUCT_LINE_SUITE
        )
        self.assertEqual(ref, "windows|month|suite")
        plat, iv = parse_client_reference_id(ref)
        self.assertEqual(plat, "windows")
        self.assertEqual(iv, "month")
        self.assertEqual(
            parse_product_line_from_client_reference(ref), PRODUCT_LINE_SUITE
        )
        vpn_ref = encode_client_reference_id("android", interval="year")
        self.assertEqual(vpn_ref, "android|year")
        self.assertEqual(
            parse_product_line_from_client_reference(vpn_ref), PRODUCT_LINE_VPN
        )
        # year|suite must not collapse interval to month
        yref = encode_client_reference_id(
            "ios", interval="year", product_line="suite"
        )
        self.assertEqual(parse_client_reference_id(yref), ("ios", "year"))

    def test_build_subscription_body_marks_suite(self):
        from payments import (
            build_subscription_checkout_form_body,
            PRODUCT_LINE_SUITE,
            STRIPE_PRODUCT_NAME_SUITE_MONTHLY,
        )

        body = build_subscription_checkout_form_body(
            "windows",
            "restore-privacy-client-1.0.0-windows-x64-setup.exe",
            interval="month",
            success_url="https://example.test/ok",
            cancel_url="https://example.test/cancel",
            product_line=PRODUCT_LINE_SUITE,
        )
        fields = urllib.parse.parse_qs(body.decode("utf-8"))
        self.assertEqual(fields["metadata[product_line]"], ["suite"])
        self.assertEqual(fields["metadata[product]"], ["suite"])
        self.assertEqual(fields["client_reference_id"], ["windows|month|suite"])
        self.assertEqual(
            fields["metadata[product_name]"], [STRIPE_PRODUCT_NAME_SUITE_MONTHLY]
        )
        self.assertEqual(
            fields["subscription_data[metadata][product_line]"], ["suite"]
        )

    def test_vpn_body_unchanged_default(self):
        from payments import (
            build_subscription_checkout_form_body,
            STRIPE_PRODUCT_NAME_MONTHLY,
        )

        body = build_subscription_checkout_form_body(
            "linux",
            "restore-privacy-client-1.0.0-linux-x64.tar.gz",
            interval="month",
            success_url="https://example.test/ok",
            cancel_url="https://example.test/cancel",
        )
        fields = urllib.parse.parse_qs(body.decode("utf-8"))
        self.assertEqual(fields["metadata[product_line]"], ["vpn"])
        self.assertEqual(fields["client_reference_id"], ["linux|month"])
        self.assertEqual(
            fields["metadata[product_name]"], [STRIPE_PRODUCT_NAME_MONTHLY]
        )

    def test_create_subscription_session_passes_product_line(self):
        from payments import create_subscription_checkout_session

        captured: list[bytes] = []

        def fake_post(url, headers, body):  # noqa: ARG001
            captured.append(body)
            return 200, b'{"id":"cs_test_suite","url":"https://checkout.stripe.com/c/pay/cs_test"}'

        with mock.patch.dict(
            os.environ, {"STRIPE_SECRET_KEY": "sk_test_suite_unit"}, clear=False
        ):
            sess = create_subscription_checkout_session(
                "macos",
                interval="year",
                product_line="suite",
                http_post=fake_post,
                base_url="https://restoreprivacy.online",
            )
        self.assertEqual(sess["product_line"], "suite")
        self.assertIn("Suite", sess["product_name"])
        self.assertTrue(captured)
        fields = urllib.parse.parse_qs(captured[0].decode("utf-8"))
        self.assertEqual(fields["metadata[product_line]"], ["suite"])
        self.assertIn("suite-storefront", fields["cancel_url"][0])

    def test_product_line_from_checkout_object(self):
        from payments import product_line_from_checkout_object

        self.assertEqual(
            product_line_from_checkout_object(
                {"metadata": {"product_line": "suite"}}
            ),
            "suite",
        )
        self.assertEqual(
            product_line_from_checkout_object(
                {"client_reference_id": "windows|month|suite"}
            ),
            "suite",
        )
        self.assertEqual(
            product_line_from_checkout_object(
                {"client_reference_id": "windows|month"}
            ),
            "vpn",
        )


class TestSuiteEntitlementInheritance(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name

    def tearDown(self):
        self._td.cleanup()
        os.environ.pop("RPT_PAYMENT_DATA_DIR", None)

    def test_suite_activate_same_connect_semantics_as_vpn(self):
        from payments import (
            activate_connect_entitlement,
            client_entitlement_file_payload,
            get_connect_entitlement,
            get_connect_entitlement_by_keygen,
            PRODUCT_LINE_SUITE,
            PRODUCT_LINE_VPN,
        )

        now = time.time()
        vu = now + 86400 * 30
        kg_suite = activate_connect_entitlement(
            "cs_suite_inherit_1",
            platform="windows",
            valid_until=vu,
            billing_interval="month",
            product_line=PRODUCT_LINE_SUITE,
            now=now,
        )
        self.assertTrue(kg_suite.startswith("RPT-KEY-"))
        ent = get_connect_entitlement("cs_suite_inherit_1", now=now)
        assert ent is not None
        self.assertEqual(ent["status"], "active")
        self.assertTrue(ent["connect_allowed"])
        self.assertEqual(ent["product_line"], PRODUCT_LINE_SUITE)
        # Keygen unlock path (GUI + residual)
        by_kg = get_connect_entitlement_by_keygen(kg_suite, now=now)
        assert by_kg is not None
        self.assertTrue(by_kg["connect_allowed"])
        self.assertEqual(by_kg["product_line"], PRODUCT_LINE_SUITE)
        payload = client_entitlement_file_payload("cs_suite_inherit_1")
        assert payload is not None
        self.assertEqual(payload["product_line"], "suite")
        self.assertEqual(payload["status"], "active")
        self.assertTrue(payload["connect_allowed"])

        # VPN grant still works (regression)
        kg_vpn = activate_connect_entitlement(
            "cs_vpn_inherit_1",
            platform="android",
            valid_until=vu,
            billing_interval="year",
            product_line=PRODUCT_LINE_VPN,
            now=now,
        )
        ent_vpn = get_connect_entitlement("cs_vpn_inherit_1", now=now)
        assert ent_vpn is not None
        self.assertTrue(ent_vpn["connect_allowed"])
        self.assertEqual(ent_vpn["product_line"], PRODUCT_LINE_VPN)
        self.assertTrue(kg_vpn.startswith("RPT-KEY-"))

    def test_residual_client_accepts_suite_payload(self):
        """Python residual payment_entitlement inherits Suite active grants."""
        from payment_entitlement import (
            PaymentEntitlement,
            STATUS_ACTIVE,
            PRODUCT_LINE_SUITE,
            normalize_product_line,
        )

        ent = PaymentEntitlement.from_dict(
            {
                "session_id": "cs_suite_client",
                "status": STATUS_ACTIVE,
                "platform": "windows",
                "keygen": "RPT-KEY-TEST-SUITE-AAAA",
                "product_line": "suite",
                "valid_until": time.time() + 3600,
            }
        )
        self.assertEqual(ent.product_line, PRODUCT_LINE_SUITE)
        self.assertEqual(ent.status, STATUS_ACTIVE)
        self.assertEqual(normalize_product_line("suite"), PRODUCT_LINE_SUITE)
        d = ent.to_dict()
        self.assertEqual(d["product_line"], "suite")
        # Local status active is the unlock condition (same as VPN)
        self.assertEqual(ent.status, STATUS_ACTIVE)

    def test_admin_list_includes_suite_product_line(self):
        from payments import (
            activate_connect_entitlement,
            list_licences_for_admin,
            PRODUCT_LINE_SUITE,
        )

        now = time.time()
        activate_connect_entitlement(
            "cs_admin_suite",
            platform="linux",
            valid_until=now + 10000,
            product_line=PRODUCT_LINE_SUITE,
            customer_email="suite@example.test",
            now=now,
        )
        rows = list_licences_for_admin()
        suite_rows = [r for r in rows if r.get("session_id") == "cs_admin_suite"]
        self.assertTrue(suite_rows)
        self.assertEqual(suite_rows[0]["product_line"], "suite")


class TestSuiteCheckoutWebhookMint(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name

    def tearDown(self):
        self._td.cleanup()
        os.environ.pop("RPT_PAYMENT_DATA_DIR", None)

    def test_process_checkout_completed_suite_metadata(self):
        from downloads import RELEASE_VERSION
        from payments import (
            PRICE_PENCE,
            process_checkout_completed_event,
            get_connect_entitlement,
        )

        fname = f"restore-privacy-client-{RELEASE_VERSION}-windows-x64-setup.exe"
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_suite_webhook",
                    "payment_status": "paid",
                    "amount_total": PRICE_PENCE,
                    "currency": "gbp",
                    "client_reference_id": "windows|month|suite",
                    "metadata": {
                        "platform": "windows",
                        "filename": fname,
                        "amount_pence": str(PRICE_PENCE),
                        "product_line": "suite",
                        "billing_interval": "month",
                    },
                    "subscription": "sub_suite_1",
                }
            },
        }
        token = process_checkout_completed_event(
            event, email_transport=lambda _p: {"ok": True}
        )
        self.assertTrue(token)
        ent = get_connect_entitlement("cs_test_suite_webhook")
        assert ent is not None
        self.assertEqual(ent["product_line"], "suite")
        self.assertTrue(ent["connect_allowed"])
        self.assertTrue((ent.get("keygen") or "").startswith("RPT-KEY-"))


if __name__ == "__main__":
    unittest.main()
