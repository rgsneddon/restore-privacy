"""Subscription Payment Link catalogue + fulfilment path (shipped code only).

Gating tests for donate→subscription: catalog BUY hrefs, trial/paid subscription
checkout.session.completed, lifecycle cancel/delete/refund.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestCatalogSubscriptionPaymentLink(unittest.TestCase):
    def setUp(self):
        for k in (
            "STRIPE_PAYMENT_PAGE_URL",
            "RPT_STRIPE_PAYMENT_PAGE_URL",
            "STRIPE_PAYMENT_LINK_ID",
            "RPT_STRIPE_PAYMENT_LINK_ID",
        ):
            os.environ.pop(k, None)

    def test_desired_fields_are_subscription_245_monthly_trial(self):
        from payments import (
            CATALOG_STRIPE_PAYMENT_MODE,
            DEFAULT_STRIPE_PAYMENT_PAGE_URL,
            PRICE_PENCE,
            desired_payment_link_trial_fields,
            stripe_payment_page_url,
        )

        d = desired_payment_link_trial_fields()
        self.assertEqual(d["mode"], "subscription")
        self.assertEqual(d["mode"], CATALOG_STRIPE_PAYMENT_MODE)
        self.assertEqual(d["unit_amount_pence"], PRICE_PENCE)
        self.assertEqual(d["unit_amount_pence"], 245)
        self.assertEqual(d["currency"], "gbp")
        self.assertEqual(d["recurring_interval"], "month")
        self.assertEqual(d["trial_period_days"], 7)
        self.assertEqual(d["payment_page_url"], DEFAULT_STRIPE_PAYMENT_PAGE_URL)
        self.assertEqual(stripe_payment_page_url(), d["payment_page_url"])
        # Product path is subscription buy host (not a one-time donate tip default)
        self.assertTrue(
            DEFAULT_STRIPE_PAYMENT_PAGE_URL.startswith("https://buy.stripe.com/"),
            DEFAULT_STRIPE_PAYMENT_PAGE_URL,
        )
        self.assertNotIn("donate.stripe.com", DEFAULT_STRIPE_PAYMENT_PAGE_URL)

    def test_platform_buy_hrefs_carry_client_reference_id(self):
        from downloads import available_downloads
        from payments import (
            desired_payment_link_trial_fields,
            stripe_payment_page_href_for_platform,
            stripe_payment_page_url,
        )

        base = stripe_payment_page_url()
        self.assertEqual(base, desired_payment_link_trial_fields()["payment_page_url"])
        for a in available_downloads():
            href = stripe_payment_page_href_for_platform(a.platform)
            self.assertTrue(href.startswith(base), href)
            self.assertIn(f"client_reference_id={a.platform}", href)
            # Catalog DownloadAsset.pay_path uses the same helper
            self.assertEqual(href, a.pay_path)

    def test_catalog_html_uses_subscription_payment_link(self):
        from downloads import available_downloads, render_download_section_html
        from payments import stripe_payment_page_url

        html = render_download_section_html(coming_soon=False)
        base = stripe_payment_page_url()
        self.assertIn(base, html)
        self.assertIn("buy.stripe.com", html)
        self.assertNotIn("donate.stripe.com", html)
        self.assertIn('data-buy-mode="stripe-live"', html)
        for a in available_downloads():
            self.assertIn(f"client_reference_id={a.platform}", html)


class TestSubscriptionCheckoutCompleted(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(
            os.environ,
            {"RPT_PAYMENT_DATA_DIR": self._td.name},
            clear=False,
        )
        self.env.start()
        import payments as pay

        pay.init_db()
        self.pay = pay

    def tearDown(self):
        self.env.stop()
        self._td.cleanup()

    def _trial_event(
        self,
        session_id: str = "cs_test_sub_trial_1",
        platform: str = "windows",
        subscription_id: str = "sub_trial_abc",
    ) -> dict:
        return {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "mode": "subscription",
                    "payment_status": "no_payment_required",
                    "amount_total": 0,
                    "currency": "gbp",
                    "client_reference_id": platform,
                    "subscription": subscription_id,
                    "customer_email": "trial@example.com",
                    "metadata": {},
                }
            },
        }

    def _paid_sub_event(
        self,
        session_id: str = "cs_test_sub_paid_1",
        platform: str = "linux",
        subscription_id: str = "sub_paid_xyz",
    ) -> dict:
        return {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "mode": "subscription",
                    "payment_status": "paid",
                    "amount_total": self.pay.PRICE_PENCE,
                    "currency": "gbp",
                    "client_reference_id": platform,
                    "subscription": {"id": subscription_id},
                    "payment_intent": "pi_sub_paid_1",
                    "customer_email": "paid@example.com",
                    "metadata": {
                        "platform": platform,
                        "amount_pence": str(self.pay.PRICE_PENCE),
                        "currency": "gbp",
                    },
                }
            },
        }

    def test_trial_subscription_mints_grant_and_stores_subscription_id(self):
        pay = self.pay
        token = pay.process_checkout_completed_event(self._trial_event())
        self.assertTrue(token)
        grant = pay.lookup_download_token(token)
        self.assertIsNotNone(grant)
        assert grant is not None
        self.assertEqual(grant["platform"], "windows")
        self.assertEqual(grant["session_id"], "cs_test_sub_trial_1")
        self.assertEqual(grant["amount_pence"], pay.PRICE_PENCE)

        ent = pay.get_connect_entitlement("cs_test_sub_trial_1")
        self.assertIsNotNone(ent)
        assert ent is not None
        self.assertEqual(ent["status"], "active")
        self.assertTrue(ent["connect_allowed"])
        self.assertEqual(ent.get("subscription_id"), "sub_trial_abc")
        self.assertTrue((ent.get("keygen") or "").startswith("RPT-KEY-"))

    def test_paid_subscription_session_mints_and_binds_subscription(self):
        pay = self.pay
        token = pay.process_checkout_completed_event(self._paid_sub_event())
        self.assertTrue(token)
        ent = pay.get_connect_entitlement("cs_test_sub_paid_1")
        self.assertIsNotNone(ent)
        assert ent is not None
        self.assertTrue(ent["connect_allowed"])
        self.assertEqual(ent.get("subscription_id"), "sub_paid_xyz")
        self.assertEqual(ent.get("platform"), "linux")

    def test_underpay_without_subscription_does_not_mint(self):
        pay = self.pay
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_underpay",
                    "payment_status": "paid",
                    "amount_total": 1,
                    "currency": "gbp",
                    "client_reference_id": "android",
                    "metadata": {"amount_pence": "1"},
                }
            },
        }
        self.assertIsNone(pay.process_checkout_completed_event(event))
        self.assertIsNone(pay.get_connect_entitlement("cs_underpay"))

    def test_zero_without_subscription_does_not_mint(self):
        pay = self.pay
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_zero_no_sub",
                    "payment_status": "no_payment_required",
                    "amount_total": 0,
                    "currency": "gbp",
                    "client_reference_id": "macos",
                }
            },
        }
        self.assertIsNone(pay.process_checkout_completed_event(event))

    def test_webhook_handler_grants_on_trial_subscription(self):
        pay = self.pay
        body = json.dumps(self._trial_event("cs_wh_trial", "ios", "sub_wh_1")).encode()
        with mock.patch.object(pay, "verify_stripe_signature", return_value=True):
            result = pay.handle_stripe_webhook(body, "t=1,v1=x")
        self.assertTrue(result.get("ok"))
        self.assertTrue(result.get("granted"))
        self.assertTrue(result.get("token"))
        ent = pay.get_connect_entitlement("cs_wh_trial")
        self.assertIsNotNone(ent)
        assert ent is not None
        self.assertEqual(ent.get("subscription_id"), "sub_wh_1")


class TestSubscriptionLifecycle(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(
            os.environ,
            {"RPT_PAYMENT_DATA_DIR": self._td.name},
            clear=False,
        )
        self.env.start()
        import payments as pay

        pay.init_db()
        self.pay = pay

    def tearDown(self):
        self.env.stop()
        self._td.cleanup()

    def test_cancel_at_period_end_keeps_usable_until_period_end(self):
        pay = self.pay
        pay.activate_connect_entitlement(
            "cs_life_1", subscription_id="sub_life_1", platform="windows"
        )
        pe = 2_000_000_000.0
        now = 1_700_000_000.0
        res = pay.process_subscription_lifecycle_event(
            {
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": "sub_life_1",
                        "status": "active",
                        "cancel_at_period_end": True,
                        "current_period_end": pe,
                    }
                },
            },
            now=now,
        )
        self.assertIsNotNone(res)
        assert res is not None
        self.assertIn(res["action"], ("period_updated", "period_end_scheduled"))
        self.assertTrue(pay.connect_entitlement_allows("cs_life_1", now=now))
        self.assertFalse(pay.connect_entitlement_allows("cs_life_1", now=pe + 1))

    def test_subscription_deleted_revokes(self):
        pay = self.pay
        pay.activate_connect_entitlement(
            "cs_life_2", subscription_id="sub_del_1", platform="linux"
        )
        res = pay.process_subscription_lifecycle_event(
            {
                "type": "customer.subscription.deleted",
                "data": {"object": {"id": "sub_del_1"}},
            }
        )
        self.assertEqual(res["action"], "revoked")
        self.assertFalse(pay.connect_entitlement_allows("cs_life_2"))

    def test_refund_revokes_after_subscription_checkout(self):
        pay = self.pay
        event_ok = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_life_refund",
                    "mode": "subscription",
                    "payment_status": "paid",
                    "amount_total": pay.PRICE_PENCE,
                    "currency": "gbp",
                    "client_reference_id": "android",
                    "subscription": "sub_ref_1",
                    "payment_intent": "pi_life_ref",
                }
            },
        }
        self.assertTrue(pay.process_checkout_completed_event(event_ok))
        sid = pay.process_payment_failure_event(
            {
                "type": "charge.refunded",
                "data": {
                    "object": {
                        "id": "ch_life_ref",
                        "payment_intent": "pi_life_ref",
                        "metadata": {},
                    }
                },
            }
        )
        self.assertEqual(sid, "cs_life_refund")
        ent = pay.get_connect_entitlement("cs_life_refund")
        self.assertEqual(ent["status"], "revoked")
        self.assertFalse(ent["connect_allowed"])


if __name__ == "__main__":
    unittest.main()
