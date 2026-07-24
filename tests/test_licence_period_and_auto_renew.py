"""Monthly/yearly licence periods, expiry hard-lock, and purchase auto-renew.

Drives shipped payments helpers + fulfilment (not re-implementations).
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestPeriodHelpers(unittest.TestCase):
    def test_normalize_and_calendar_period_end(self):
        from payments import (
            BILLING_INTERVAL_MONTH,
            BILLING_INTERVAL_YEAR,
            MAX_MONTH_SECONDS,
            MAX_YEAR_SECONDS,
            MIN_MONTH_SECONDS,
            MIN_YEAR_SECONDS,
            normalize_billing_interval,
            period_end_for_billing_interval,
            valid_until_for_paid_interval,
        )

        self.assertEqual(normalize_billing_interval("yearly"), BILLING_INTERVAL_YEAR)
        self.assertEqual(normalize_billing_interval("month"), BILLING_INTERVAL_MONTH)

        # Fixed UTC start: 2024-01-15 12:00:00
        start = 1_705_320_000.0
        month_end = period_end_for_billing_interval(start, "month")
        year_end = period_end_for_billing_interval(start, "year")
        md = month_end - start
        yd = year_end - start
        self.assertGreaterEqual(md, MIN_MONTH_SECONDS)
        self.assertLessEqual(md, MAX_MONTH_SECONDS)
        self.assertGreaterEqual(yd, MIN_YEAR_SECONDS)
        self.assertLessEqual(yd, MAX_YEAR_SECONDS)
        self.assertGreater(yd, md * 10)

        # Prefer Stripe current_period_end when in the future
        pe = start + 40 * 86400
        self.assertEqual(
            valid_until_for_paid_interval("month", now=start, stripe_period_end=pe),
            pe,
        )
        # Past Stripe period → fallback calendar month
        past = start - 100
        vu = valid_until_for_paid_interval(
            "month", now=start, stripe_period_end=past
        )
        self.assertEqual(vu, period_end_for_billing_interval(start, "month"))

    def test_stripe_period_end_from_expanded_subscription(self):
        from payments import stripe_period_end_from_checkout_object

        pe = 2_000_000_000.0
        self.assertEqual(
            stripe_period_end_from_checkout_object(
                {"subscription": {"id": "sub_x", "current_period_end": pe}}
            ),
            pe,
        )
        self.assertIsNone(
            stripe_period_end_from_checkout_object({"subscription": "sub_string_only"})
        )


class TestPaidActivationSetsValidUntil(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(
            os.environ, {"RPT_PAYMENT_DATA_DIR": self._td.name}, clear=False
        )
        self.env.start()
        import payments as pay

        pay.init_db()
        self.pay = pay
        self.now = 1_705_320_000.0  # 2024-01-15-ish UTC

    def tearDown(self):
        self.env.stop()
        self._td.cleanup()

    def _paid_event(
        self,
        *,
        session_id: str,
        interval: str,
        amount: int | None = None,
        subscription: object = "sub_period_1",
    ) -> dict:
        pay = self.pay
        if amount is None:
            amount = (
                pay.PRICE_YEARLY_PENCE
                if interval == "year"
                else pay.PRICE_PENCE
            )
        ref = f"windows|{interval}" if interval == "year" else "windows|month"
        return {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "mode": "subscription",
                    "payment_status": "paid",
                    "amount_total": amount,
                    "currency": "gbp",
                    "client_reference_id": ref,
                    "subscription": subscription,
                    "customer_email": "period@example.com",
                    "metadata": {
                        "platform": "windows",
                        "billing_interval": interval,
                        "amount_pence": str(amount),
                    },
                }
            },
        }

    def test_monthly_purchase_valid_until_one_month(self):
        pay = self.pay
        token = pay.process_checkout_completed_event(
            self._paid_event(session_id="cs_month_period", interval="month"),
            now=self.now,
        )
        self.assertTrue(token)
        ent = pay.get_connect_entitlement("cs_month_period", now=self.now)
        self.assertIsNotNone(ent)
        assert ent is not None
        vu = ent.get("valid_until")
        self.assertIsNotNone(vu, "paid monthly must not have unlimited valid_until")
        delta = float(vu) - self.now
        self.assertGreaterEqual(delta, pay.MIN_MONTH_SECONDS)
        self.assertLessEqual(delta, pay.MAX_MONTH_SECONDS)
        self.assertEqual(ent.get("billing_interval"), "month")
        self.assertTrue(ent["connect_allowed"])
        self.assertEqual(
            pay.licence_status_from_entitlement(ent, now=self.now),
            pay.LICENCE_STATUS_OK,
        )

    def test_yearly_purchase_valid_until_one_year(self):
        pay = self.pay
        token = pay.process_checkout_completed_event(
            self._paid_event(session_id="cs_year_period", interval="year"),
            now=self.now,
        )
        self.assertTrue(token)
        ent = pay.get_connect_entitlement("cs_year_period", now=self.now)
        self.assertIsNotNone(ent)
        assert ent is not None
        vu = ent.get("valid_until")
        self.assertIsNotNone(vu)
        delta = float(vu) - self.now
        self.assertGreaterEqual(delta, pay.MIN_YEAR_SECONDS)
        self.assertLessEqual(delta, pay.MAX_YEAR_SECONDS)
        self.assertEqual(ent.get("billing_interval"), "year")
        self.assertTrue(ent["connect_allowed"])

    def test_stripe_current_period_end_preferred(self):
        pay = self.pay
        pe = self.now + 45 * 86400
        token = pay.process_checkout_completed_event(
            self._paid_event(
                session_id="cs_stripe_pe",
                interval="month",
                subscription={
                    "id": "sub_pe",
                    "current_period_end": pe,
                },
            ),
            now=self.now,
        )
        self.assertTrue(token)
        ent = pay.get_connect_entitlement("cs_stripe_pe", now=self.now)
        assert ent is not None
        self.assertEqual(ent.get("valid_until"), pe)


class TestLicenceExpiryHardLock(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(
            os.environ, {"RPT_PAYMENT_DATA_DIR": self._td.name}, clear=False
        )
        self.env.start()
        import payments as pay

        pay.init_db()
        self.pay = pay
        self.now = 1_705_320_000.0

    def tearDown(self):
        self.env.stop()
        self._td.cleanup()

    def test_expired_after_period_end_without_renewal(self):
        pay = self.pay
        pe = self.now + 30 * 86400
        pay.activate_connect_entitlement(
            "cs_exp_1",
            platform="linux",
            subscription_id="sub_exp_1",
            valid_until=pe,
            billing_interval="month",
            now=self.now,
        )
        self.assertTrue(pay.connect_entitlement_allows("cs_exp_1", now=self.now + 10))
        ent_ok = pay.get_connect_entitlement("cs_exp_1", now=self.now + 10)
        assert ent_ok is not None
        self.assertEqual(
            pay.licence_status_from_entitlement(ent_ok, now=self.now + 10),
            pay.LICENCE_STATUS_OK,
        )
        # Past period end → Connect denied + EXPIRED
        after = pe + 1
        self.assertFalse(pay.connect_entitlement_allows("cs_exp_1", now=after))
        ent_ex = pay.get_connect_entitlement("cs_exp_1", now=after)
        assert ent_ex is not None
        self.assertFalse(ent_ex["connect_allowed"])
        self.assertEqual(
            pay.licence_status_from_entitlement(ent_ex, now=after),
            pay.LICENCE_STATUS_EXPIRED,
        )

    def test_client_licence_status_expired_when_valid_until_past(self):
        from client.payment_entitlement import (
            LICENCE_STATUS_EXPIRED,
            LICENCE_STATUS_OK,
            PaymentEntitlement,
            STATUS_ACTIVE,
            licence_status_from_payment_entitlement,
        )

        kg = "RPT-KEY-ABCDEF0123456789ABCDEF01"
        past = time.time() - 100
        future = time.time() + 86400
        expired = PaymentEntitlement(
            status=STATUS_ACTIVE,
            session_id="cs_c",
            platform="windows",
            keygen=kg,
            valid_until=past,
        )
        ok = PaymentEntitlement(
            status=STATUS_ACTIVE,
            session_id="cs_c2",
            platform="windows",
            keygen=kg,
            valid_until=future,
        )
        self.assertEqual(
            licence_status_from_payment_entitlement(expired), LICENCE_STATUS_EXPIRED
        )
        self.assertEqual(
            licence_status_from_payment_entitlement(ok), LICENCE_STATUS_OK
        )

    def test_invoice_paid_extends_period_and_restores_access(self):
        pay = self.pay
        pe1 = self.now + 10
        pay.activate_connect_entitlement(
            "cs_renew_1",
            platform="android",
            subscription_id="sub_renew_1",
            valid_until=pe1,
            billing_interval="month",
            now=self.now,
        )
        # Past first period
        after = pe1 + 5
        self.assertFalse(pay.connect_entitlement_allows("cs_renew_1", now=after))
        pe2 = after + 30 * 86400
        res = pay.process_subscription_lifecycle_event(
            {
                "type": "invoice.paid",
                "data": {
                    "object": {
                        "subscription": "sub_renew_1",
                        "lines": {
                            "data": [{"period": {"end": pe2}}],
                        },
                    }
                },
            },
            now=after,
        )
        self.assertIsNotNone(res)
        assert res is not None
        self.assertEqual(res["action"], "renewed")
        self.assertEqual(res["valid_until"], pe2)
        self.assertTrue(pay.connect_entitlement_allows("cs_renew_1", now=after + 1))


class TestAutoRenewLifecycleAndCheckout(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(
            os.environ, {"RPT_PAYMENT_DATA_DIR": self._td.name}, clear=False
        )
        self.env.start()
        import payments as pay

        pay.init_db()
        self.pay = pay

    def tearDown(self):
        self.env.stop()
        self._td.cleanup()

    def test_parse_auto_renew_form_values(self):
        from payments import parse_auto_renew_choice, parse_auto_renew_form_values

        self.assertTrue(parse_auto_renew_choice(None))
        self.assertFalse(parse_auto_renew_choice("0"))
        self.assertFalse(parse_auto_renew_choice(False))
        self.assertTrue(parse_auto_renew_form_values(["0", "1"]))
        self.assertFalse(parse_auto_renew_form_values(["0"]))
        self.assertTrue(parse_auto_renew_form_values(None))

    def test_checkout_body_cancel_at_period_end_when_auto_renew_off(self):
        from payments import build_subscription_checkout_form_body

        on = build_subscription_checkout_form_body(
            "windows",
            "f.exe",
            interval="month",
            success_url="https://x/s",
            cancel_url="https://x/c",
            auto_renew=True,
        ).decode()
        off = build_subscription_checkout_form_body(
            "windows",
            "f.exe",
            interval="year",
            success_url="https://x/s",
            cancel_url="https://x/c",
            auto_renew=False,
        ).decode()
        self.assertNotIn("cancel_at_period_end", on)
        self.assertIn("metadata%5Bauto_renew%5D=1", on)
        self.assertIn("subscription_data%5Bcancel_at_period_end%5D=true", off)
        self.assertIn("metadata%5Bauto_renew%5D=0", off)
        # Year price still bound when auto-renew off
        from payments import DEFAULT_STRIPE_PRICE_ID_YEARLY

        self.assertIn(DEFAULT_STRIPE_PRICE_ID_YEARLY, off)

    def test_apply_subscription_auto_renew_preference_posts_cancel_flag(self):
        from payments import apply_subscription_auto_renew_preference

        calls: list[tuple[str, bytes]] = []

        def fake_post(url: str, headers: dict, body: bytes):
            calls.append((url, body))
            return 200, b'{"id":"sub_x","cancel_at_period_end":true}'

        res = apply_subscription_auto_renew_preference(
            "sub_x",
            auto_renew=False,
            http_post=fake_post,
            secret_key="sk_test_x",
        )
        self.assertTrue(res.get("ok"))
        self.assertEqual(len(calls), 1)
        self.assertIn("/v1/subscriptions/sub_x", calls[0][0])
        self.assertIn(b"cancel_at_period_end=true", calls[0][1])

        calls.clear()

        def fake_on(url: str, headers: dict, body: bytes):
            calls.append((url, body))
            return 200, b'{"id":"sub_y","cancel_at_period_end":false}'

        res2 = apply_subscription_auto_renew_preference(
            "sub_y",
            auto_renew=True,
            http_post=fake_on,
            secret_key="sk_test_x",
        )
        self.assertTrue(res2.get("ok"))
        self.assertIn(b"cancel_at_period_end=false", calls[0][1])

    def test_create_session_retries_without_cancel_flag_on_parameter_unknown(self):
        """Live Stripe may reject create-time cancel_at_period_end; retry keeps auto_renew=0."""
        from payments import create_subscription_checkout_session

        bodies: list[bytes] = []

        def fake_post(url: str, headers: dict, body: bytes):
            bodies.append(body)
            if b"cancel_at_period_end" in body:
                return (
                    400,
                    b'{"error":{"code":"parameter_unknown","message":'
                    b'"Received unknown parameter: subscription_data[cancel_at_period_end]"}}',
                )
            return (
                200,
                b'{"id":"cs_retry_1","url":"https://checkout.stripe.com/c/pay/cs_retry_1"}',
            )

        with mock.patch.dict(
            os.environ, {"STRIPE_SECRET_KEY": "sk_test_retry"}, clear=False
        ):
            sess = create_subscription_checkout_session(
                "windows",
                interval="year",
                auto_renew=False,
                http_post=fake_post,
                base_url="https://restoreprivacy.online",
            )
        self.assertEqual(sess["id"], "cs_retry_1")
        self.assertFalse(sess["auto_renew"])
        self.assertEqual(len(bodies), 2)
        self.assertIn(b"cancel_at_period_end", bodies[0])
        self.assertNotIn(b"cancel_at_period_end", bodies[1])
        self.assertIn(b"metadata%5Bauto_renew%5D=0", bodies[1])

    def test_cancel_at_period_end_usable_until_end_then_locked(self):
        pay = self.pay
        pe = 2_000_000_000.0
        now = 1_700_000_000.0
        pay.activate_connect_entitlement(
            "cs_ar_1",
            subscription_id="sub_ar_1",
            platform="windows",
            valid_until=pe,
            billing_interval="month",
            now=now,
        )
        res = pay.process_subscription_lifecycle_event(
            {
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": "sub_ar_1",
                        "status": "active",
                        "cancel_at_period_end": True,
                        "current_period_end": pe,
                    }
                },
            },
            now=now,
        )
        self.assertIsNotNone(res)
        self.assertTrue(pay.connect_entitlement_allows("cs_ar_1", now=now))
        self.assertFalse(pay.connect_entitlement_allows("cs_ar_1", now=pe + 1))


class TestPurchaseAutoRenewUi(unittest.TestCase):
    def test_homepage_buy_form_has_auto_renew_control(self):
        from downloads import (
            AUTO_RENEW_LABEL,
            render_download_section_html,
            render_homepage_buy_form_html,
        )

        form = render_homepage_buy_form_html(coming_soon=False)
        self.assertIn('name="auto_renew"', form)
        self.assertIn('id="dl-auto-renew"', form)
        self.assertIn(AUTO_RENEW_LABEL, form)
        self.assertIn("checked", form)
        # hidden off value for unchecked posts
        self.assertIn('value="0"', form)
        self.assertIn('value="1"', form)

        html = render_download_section_html(
            coming_soon=False, currency="GBP", country="GB"
        )
        self.assertIn("dl-auto-renew", html)
        self.assertIn('action="/pay/checkout"', html)

    def test_pay_plan_page_has_auto_renew_control(self):
        from payments import render_pay_plan_page_html

        page = render_pay_plan_page_html("windows", interval="month").decode("utf-8")
        self.assertIn('id="pay-auto-renew"', page)
        self.assertIn('name="auto_renew"', page)
        self.assertIn("Auto-renew", page)
        self.assertIn("one month", page.lower())
        self.assertIn("one year", page.lower())


if __name__ == "__main__":
    unittest.main()
