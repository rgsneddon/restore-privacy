"""KEYGEN £3/mo · £30/yr Stripe flow ends in Raskul accounting.

Drives shipped checkout body builders, process_checkout_completed_event,
invoice.paid sale recording, and accounting.sales_from_grants / build_ledger.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT))


class TestKeygenPayLinkInventory(unittest.TestCase):
    def test_inventory_and_subscription_bodies_are_catalog_keygen(self) -> None:
        from payments import (
            CATALOG_TRIAL_PERIOD_DAYS,
            COMMERCIAL_SUITE_NODE_PRICE_PENCE,
            PRICE_PENCE,
            PRICE_YEARLY_PENCE,
            catalog_keygen_subscription_body_fields,
            inventory_catalog_keygen_pay_entry_points,
            is_catalog_keygen_amount_pence,
        )

        self.assertEqual(PRICE_PENCE, 300)
        self.assertEqual(PRICE_YEARLY_PENCE, 3000)
        self.assertEqual(CATALOG_TRIAL_PERIOD_DAYS, 3)
        self.assertTrue(is_catalog_keygen_amount_pence(300))
        self.assertTrue(is_catalog_keygen_amount_pence(3000))
        self.assertFalse(is_catalog_keygen_amount_pence(0))
        self.assertFalse(is_catalog_keygen_amount_pence(300_000))
        self.assertFalse(is_catalog_keygen_amount_pence(1))

        inv = inventory_catalog_keygen_pay_entry_points()
        ids = {e["id"] for e in inv}
        self.assertIn("site_pay_plan", ids)
        self.assertIn("homepage_buy_form", ids)
        self.assertIn("suite_keygen_form", ids)
        self.assertIn("api_checkout", ids)
        self.assertIn("commercial_suite_deposit", ids)
        for e in inv:
            if e.get("not_keygen"):
                self.assertEqual(e["amounts_pence"], [COMMERCIAL_SUITE_NODE_PRICE_PENCE])
                continue
            self.assertEqual(e["trial_days"], 3)
            for a in e["amounts_pence"]:
                self.assertTrue(is_catalog_keygen_amount_pence(a), msg=a)

        m = catalog_keygen_subscription_body_fields("windows", interval="month")
        self.assertTrue(m["ok"], m)
        self.assertEqual(m["mode"], "subscription")
        self.assertEqual(m["amount_pence"], 300)
        self.assertEqual(m["trial_period_days"], 3)

        y = catalog_keygen_subscription_body_fields("linux", interval="year")
        self.assertTrue(y["ok"], y)
        self.assertEqual(y["amount_pence"], 3000)
        self.assertEqual(y["trial_period_days"], 3)

        # Suite product line same prices
        s = catalog_keygen_subscription_body_fields(
            "macos", interval="month", product_line="suite"
        )
        self.assertTrue(s["ok"], s)
        self.assertEqual(s["amount_pence"], 300)
        self.assertEqual(s["product_line"], "suite")

    def test_html_forms_post_to_pay_checkout(self) -> None:
        from downloads import render_download_section_html, render_suite_storefront_html
        from payments import render_pay_plan_page_html

        plan = render_pay_plan_page_html("windows", interval="month").decode()
        self.assertIn('action="/pay/checkout"', plan)
        self.assertIn("£3.00", plan)
        self.assertIn("£30.00", plan)
        self.assertIn("3-day free trial", plan.lower() or plan)

        home = render_download_section_html(coming_soon=False)
        self.assertIn('action="/pay/checkout"', home)

        suite = render_suite_storefront_html(default_platform="android")
        self.assertIn('action="/pay/checkout"', suite)
        self.assertIn('name="product" value="suite"', suite)
        self.assertIn('name="interval" value="month"', suite)

        # Commercial deposit stays distinct
        from service_commercial import render_service_page_html

        svc = render_service_page_html().decode()
        self.assertIn("/pay/commercial-suite", svc)
        self.assertIn("300000", svc)
        self.assertNotIn('action="/pay/checkout"', svc.split("service-commercial-box")[1][:800])


class TestCheckoutCompletedKeygenChain(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(
            os.environ, {"RPT_PAYMENT_DATA_DIR": self._td.name}, clear=False
        )
        self.env.start()
        import payments as pay

        pay.init_db()
        self.pay = pay

    def tearDown(self) -> None:
        self.env.stop()
        self._td.cleanup()

    def test_monthly_paid_unlocks_and_books_sale(self) -> None:
        pay = self.pay
        from accounting import build_ledger_from_payment_store, sales_from_grants

        ts = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc).timestamp()
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_keygen_paid_mo",
                    "mode": "subscription",
                    "payment_status": "paid",
                    "amount_total": pay.PRICE_PENCE,
                    "currency": "gbp",
                    "client_reference_id": "windows|month",
                    "subscription": "sub_mo_1",
                    "customer_email": "buyer@example.com",
                    "metadata": {
                        "platform": "windows",
                        "amount_pence": str(pay.PRICE_PENCE),
                        "billing_interval": "month",
                        "product_line": "suite",
                    },
                    "created": int(ts),
                }
            },
        }
        with mock.patch.object(pay.time, "time", return_value=ts):
            token = pay.process_checkout_completed_event(event, now=ts)
        self.assertTrue(token)
        ent = pay.get_connect_entitlement("cs_keygen_paid_mo")
        self.assertIsNotNone(ent)
        assert ent is not None
        self.assertTrue(ent["connect_allowed"])
        self.assertTrue((ent.get("keygen") or "").startswith("RPT-KEY-"))
        grant = pay.lookup_download_token(token)
        self.assertIsNotNone(grant)
        assert grant is not None
        self.assertEqual(grant["amount_pence"], 300)

        sales = sales_from_grants(pay.list_all_grants())
        amounts = [int(s.get("amount_pence") or s.get("gross") or 0) for s in sales]
        # sales_from_grants returns dicts with gross via build — check grant amount in sales
        self.assertTrue(
            any(int(g.get("amount_pence") or 0) == 300 for g in pay.list_all_grants() if g.get("session_id") == "cs_keygen_paid_mo")
        )
        ledger = build_ledger_from_payment_store()
        sale_rows = [r for r in ledger if r.kind == "sale" and r.gross_pence == 300]
        self.assertGreaterEqual(len(sale_rows), 1, [ (r.kind, r.gross_pence, r.description) for r in ledger])

    def test_yearly_paid_unlocks_and_books_3000(self) -> None:
        pay = self.pay
        from accounting import build_ledger_from_payment_store

        ts = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc).timestamp()
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_keygen_paid_yr",
                    "mode": "subscription",
                    "payment_status": "paid",
                    "amount_total": pay.PRICE_YEARLY_PENCE,
                    "currency": "gbp",
                    "client_reference_id": "linux|year",
                    "subscription": "sub_yr_1",
                    "customer_email": "year@example.com",
                    "metadata": {
                        "platform": "linux",
                        "amount_pence": str(pay.PRICE_YEARLY_PENCE),
                        "billing_interval": "year",
                    },
                    "created": int(ts),
                }
            },
        }
        token = pay.process_checkout_completed_event(event, now=ts)
        self.assertTrue(token)
        grant = pay.lookup_download_token(token)
        assert grant is not None
        self.assertEqual(grant["amount_pence"], 3000)
        ent = pay.get_connect_entitlement("cs_keygen_paid_yr")
        self.assertTrue(ent and ent.get("connect_allowed"))
        ledger = build_ledger_from_payment_store()
        sale_rows = [r for r in ledger if r.kind == "sale" and r.gross_pence == 3000]
        self.assertGreaterEqual(len(sale_rows), 1)

    def test_trial_unlocks_but_not_accounting_sale(self) -> None:
        pay = self.pay
        from accounting import sales_from_grants

        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_keygen_trial_only",
                    "mode": "subscription",
                    "payment_status": "no_payment_required",
                    "amount_total": 0,
                    "currency": "gbp",
                    "client_reference_id": "macos",
                    "subscription": "sub_trial_only",
                    "customer_email": "trial@example.com",
                    "metadata": {},
                }
            },
        }
        token = pay.process_checkout_completed_event(event)
        self.assertTrue(token)
        grant = pay.lookup_download_token(token)
        assert grant is not None
        self.assertEqual(grant["amount_pence"], 0)
        ent = pay.get_connect_entitlement("cs_keygen_trial_only")
        self.assertTrue(ent and ent.get("connect_allowed"))
        sales = sales_from_grants(pay.list_all_grants())
        # No cash sale for zero-amount trial grant
        for s in sales:
            self.assertNotEqual(s.get("session_id"), "cs_keygen_trial_only")

    def test_invoice_paid_after_trial_books_catalog_sale(self) -> None:
        pay = self.pay
        from accounting import build_ledger_from_payment_store

        # Start trial
        pay.process_checkout_completed_event(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_trial_then_pay",
                        "mode": "subscription",
                        "payment_status": "no_payment_required",
                        "amount_total": 0,
                        "client_reference_id": "android",
                        "subscription": "sub_t2p",
                        "customer_email": "t2p@example.com",
                        "metadata": {"platform": "android"},
                    }
                },
            }
        )
        ts = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc).timestamp()
        inv_event = {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_catalog_mo_1",
                    "subscription": "sub_t2p",
                    "amount_paid": pay.PRICE_PENCE,
                    "currency": "gbp",
                    "period_end": int(ts) + 30 * 86400,
                    "lines": {
                        "data": [
                            {
                                "period": {"end": int(ts) + 30 * 86400},
                                "metadata": {"platform": "android"},
                            }
                        ]
                    },
                }
            },
        }
        res = pay.process_subscription_lifecycle_event(inv_event, now=ts)
        self.assertIsNotNone(res)
        assert res is not None
        self.assertEqual(res.get("action"), "renewed")
        sale = res.get("catalog_sale") or {}
        self.assertTrue(sale.get("ok"), sale)
        self.assertEqual(sale.get("amount_pence"), 300)
        ledger = build_ledger_from_payment_store()
        sale_rows = [r for r in ledger if r.kind == "sale" and r.gross_pence == 300]
        self.assertGreaterEqual(len(sale_rows), 1)

    def test_underpay_and_commercial_amount_do_not_unlock_keygen_path(self) -> None:
        pay = self.pay
        # Underpay without subscription
        self.assertIsNone(
            pay.process_checkout_completed_event(
                {
                    "type": "checkout.session.completed",
                    "data": {
                        "object": {
                            "id": "cs_under",
                            "payment_status": "paid",
                            "amount_total": 1,
                            "client_reference_id": "windows",
                            "metadata": {"amount_pence": "1"},
                        }
                    },
                }
            )
        )
        # Monthly subscription underpay (1p / 150p) with subscription id — fail closed
        for amt, sid in ((1, "cs_mo_under_1"), (150, "cs_mo_under_150"), (999, "cs_mo_under_999")):
            self.assertIsNone(
                pay.process_checkout_completed_event(
                    {
                        "type": "checkout.session.completed",
                        "data": {
                            "object": {
                                "id": sid,
                                "mode": "subscription",
                                "payment_status": "paid",
                                "amount_total": amt,
                                "currency": "gbp",
                                "client_reference_id": "windows|month",
                                "subscription": f"sub_{sid}",
                                "metadata": {
                                    "platform": "windows",
                                    "amount_pence": str(amt),
                                    "billing_interval": "month",
                                },
                            }
                        },
                    }
                ),
                msg=f"monthly underpay {amt}p",
            )
            self.assertFalse(pay.connect_entitlement_allows(sid), msg=sid)

        # payment_status=paid with amount 0 is NOT a free trial — must not unlock
        self.assertIsNone(
            pay.process_checkout_completed_event(
                {
                    "type": "checkout.session.completed",
                    "data": {
                        "object": {
                            "id": "cs_paid_zero_not_trial",
                            "mode": "subscription",
                            "payment_status": "paid",
                            "amount_total": 0,
                            "currency": "gbp",
                            "client_reference_id": "linux",
                            "subscription": "sub_paid_zero",
                            "customer_email": "pz@example.com",
                            "metadata": {"amount_pence": "0", "platform": "linux"},
                        }
                    },
                }
            )
        )
        self.assertFalse(pay.connect_entitlement_allows("cs_paid_zero_not_trial"))
        # Yearly subscription underpay (1p) — must not unlock (closed yearly_sub_ok loophole)
        self.assertIsNone(
            pay.process_checkout_completed_event(
                {
                    "type": "checkout.session.completed",
                    "data": {
                        "object": {
                            "id": "cs_year_under_1p",
                            "mode": "subscription",
                            "payment_status": "paid",
                            "amount_total": 1,
                            "currency": "gbp",
                            "client_reference_id": "windows|year",
                            "subscription": "sub_year_under_1",
                            "customer_email": "u1@example.com",
                            "metadata": {
                                "platform": "windows",
                                "amount_pence": "1",
                                "billing_interval": "year",
                            },
                        }
                    },
                }
            )
        )
        self.assertIsNone(pay.get_connect_entitlement("cs_year_under_1p"))
        self.assertFalse(pay.connect_entitlement_allows("cs_year_under_1p"))

        # Yearly subscription underpay (999p) — not catalog 3000
        self.assertIsNone(
            pay.process_checkout_completed_event(
                {
                    "type": "checkout.session.completed",
                    "data": {
                        "object": {
                            "id": "cs_year_under_999",
                            "mode": "subscription",
                            "payment_status": "paid",
                            "amount_total": 999,
                            "currency": "gbp",
                            "client_reference_id": "linux|year",
                            "subscription": "sub_year_under_999",
                            "customer_email": "u9@example.com",
                            "metadata": {
                                "platform": "linux",
                                "amount_pence": "999",
                                "billing_interval": "year",
                            },
                        }
                    },
                }
            )
        )
        self.assertIsNone(pay.get_connect_entitlement("cs_year_under_999"))
        self.assertFalse(pay.connect_entitlement_allows("cs_year_under_999"))

        # Commercial deposit amount must not unlock residual KEYGEN as catalog sub
        # without subscription id + wrong product path
        self.assertIsNone(
            pay.process_checkout_completed_event(
                {
                    "type": "checkout.session.completed",
                    "data": {
                        "object": {
                            "id": "cs_commercial_not_keygen",
                            "mode": "payment",
                            "payment_status": "paid",
                            "amount_total": pay.COMMERCIAL_SUITE_NODE_PRICE_PENCE,
                            "client_reference_id": "commercial_suite_node",
                            "metadata": {
                                "amount_pence": str(pay.COMMERCIAL_SUITE_NODE_PRICE_PENCE),
                                "product": "commercial_suite_node",
                            },
                        }
                    },
                }
            )
        )

    def test_invoice_paid_non_catalog_does_not_renew_connect(self) -> None:
        """After trial, invoice.paid with amount_paid=1 must not extend KEYGEN."""
        pay = self.pay
        now = 1_700_000_000.0
        # Trial unlock with finite period
        pay.process_checkout_completed_event(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_trial_bad_inv",
                        "mode": "subscription",
                        "payment_status": "no_payment_required",
                        "amount_total": 0,
                        "client_reference_id": "android",
                        "subscription": "sub_bad_inv",
                        "customer_email": "badinv@example.com",
                        "metadata": {"platform": "android"},
                    }
                },
            },
            now=now,
        )
        ent_before = pay.get_connect_entitlement("cs_trial_bad_inv", now=now)
        self.assertIsNotNone(ent_before)
        assert ent_before is not None
        self.assertTrue(ent_before.get("connect_allowed"))
        vu_before = ent_before.get("valid_until")

        # Non-catalog invoice after trial — must not renew / extend
        res = pay.process_subscription_lifecycle_event(
            {
                "type": "invoice.paid",
                "data": {
                    "object": {
                        "id": "in_underpay_1",
                        "subscription": "sub_bad_inv",
                        "amount_paid": 1,
                        "currency": "gbp",
                        "period_end": int(now) + 365 * 86400,
                        "lines": {
                            "data": [
                                {
                                    "period": {"end": int(now) + 365 * 86400},
                                    "metadata": {"platform": "android"},
                                }
                            ]
                        },
                    }
                },
            },
            now=now + 4 * 86400,
        )
        self.assertIsNotNone(res)
        assert res is not None
        self.assertEqual(res.get("action"), "rejected_non_catalog_amount")
        self.assertIsNone(res.get("catalog_sale"))
        ent_after = pay.get_connect_entitlement("cs_trial_bad_inv", now=now + 4 * 86400)
        self.assertIsNotNone(ent_after)
        assert ent_after is not None
        # valid_until must not jump to the year-long invoice period_end
        if vu_before is not None and ent_after.get("valid_until") is not None:
            self.assertLessEqual(
                float(ent_after["valid_until"]),
                float(vu_before) + 1.0,
            )
        # Far future (past original trial) must not still be allowed solely due to bad invoice
        far = now + 200 * 86400
        # Only fail if trial period would have ended — set a short trial valid_until
        pay.set_entitlement_valid_until(
            "cs_trial_bad_inv", now + 3 * 86400, reason="test_trial_window", now=now
        )
        self.assertFalse(
            pay.connect_entitlement_allows("cs_trial_bad_inv", now=now + 10 * 86400)
        )
        # Re-fire bad invoice while expired — still no renew
        res2 = pay.process_subscription_lifecycle_event(
            {
                "type": "invoice.paid",
                "data": {
                    "object": {
                        "id": "in_underpay_1b",
                        "subscription": "sub_bad_inv",
                        "amount_paid": 999,
                        "currency": "gbp",
                        "period_end": int(far),
                    }
                },
            },
            now=now + 10 * 86400,
        )
        self.assertEqual(res2 and res2.get("action"), "rejected_non_catalog_amount")
        self.assertFalse(
            pay.connect_entitlement_allows("cs_trial_bad_inv", now=now + 10 * 86400)
        )


class TestAmountTotalOverMetadata(unittest.TestCase):
    """Stripe amount_total is cash truth — metadata.amount_pence must not override."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(
            os.environ, {"RPT_PAYMENT_DATA_DIR": self._td.name}, clear=False
        )
        self.env.start()
        import payments as pay

        pay.init_db()
        self.pay = pay

    def tearDown(self) -> None:
        self.env.stop()
        self._td.cleanup()

    def test_usd_builder_shaped_paid_monthly_unlocks(self) -> None:
        """USD subscription body uses metadata amount_pence=300 + currency=usd;
        amount_total is relative cents (~381) — must unlock KEYGEN."""
        pay = self.pay
        from local_currency import PRICE_MONTHLY_GBP, convert_gbp_to_currency
        from payments import build_subscription_checkout_form_body
        from urllib.parse import parse_qs

        raw = build_subscription_checkout_form_body(
            "windows",
            pay.platform_filename("windows") or "restore-privacy-client-windows.exe",
            interval="month",
            success_url="https://example.com/ok",
            cancel_url="https://example.com/cancel",
            currency="usd",
        )
        fields = parse_qs(raw.decode("utf-8"))
        self.assertEqual(fields.get("mode"), ["subscription"])
        self.assertEqual(fields.get("metadata[currency]"), ["usd"])
        self.assertEqual(fields.get("metadata[amount_pence]"), ["300"])
        unit = int(fields["line_items[0][price_data][unit_amount]"][0])
        expect = int(round(convert_gbp_to_currency(PRICE_MONTHLY_GBP, "USD") * 100))
        self.assertEqual(unit, expect)

        ts = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc).timestamp()
        token = pay.process_checkout_completed_event(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_usd_mo_real",
                        "mode": "subscription",
                        "payment_status": "paid",
                        "amount_total": unit,
                        "currency": "usd",
                        "client_reference_id": "windows|month",
                        "subscription": "sub_usd_mo",
                        "customer_email": "usd@example.com",
                        "metadata": {
                            "platform": "windows",
                            "amount_pence": "300",
                            "currency": "usd",
                            "billing_interval": "month",
                        },
                    }
                },
            },
            now=ts,
        )
        self.assertTrue(token, "USD catalog presentment must unlock KEYGEN")
        self.assertTrue(pay.connect_entitlement_allows("cs_usd_mo_real"))
        grant = pay.lookup_download_token(token)
        self.assertIsNotNone(grant)
        assert grant is not None
        # Raskul books GBP catalog anchor, not raw USD cents
        self.assertEqual(grant["amount_pence"], pay.PRICE_PENCE)

    def test_amount_total_1_with_metadata_300_does_not_unlock(self) -> None:
        """Underpay cash (total=1) must not unlock even if metadata claims 300."""
        pay = self.pay
        token = pay.process_checkout_completed_event(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_spoof_meta_300",
                        "mode": "subscription",
                        "payment_status": "paid",
                        "amount_total": 1,
                        "currency": "gbp",
                        "client_reference_id": "windows|month",
                        "subscription": "sub_spoof_meta",
                        "customer_email": "spoof@example.com",
                        "metadata": {
                            "platform": "windows",
                            "amount_pence": "300",
                            "currency": "gbp",
                            "billing_interval": "month",
                        },
                    }
                },
            }
        )
        self.assertIsNone(token)
        self.assertIsNone(pay.get_connect_entitlement("cs_spoof_meta_300"))
        self.assertFalse(pay.connect_entitlement_allows("cs_spoof_meta_300"))

    def test_paid_missing_amount_total_ignores_metadata_300(self) -> None:
        """Paid with no amount_total must fail closed even if metadata says 300."""
        pay = self.pay
        token = pay.process_checkout_completed_event(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_no_total_meta_300",
                        "mode": "subscription",
                        "payment_status": "paid",
                        # amount_total omitted — sole cash truth absent
                        "currency": "gbp",
                        "client_reference_id": "windows|month",
                        "subscription": "sub_no_total",
                        "customer_email": "nototal@example.com",
                        "metadata": {
                            "platform": "windows",
                            "amount_pence": "300",
                            "currency": "gbp",
                        },
                    }
                },
            }
        )
        self.assertIsNone(token)
        self.assertFalse(pay.connect_entitlement_allows("cs_no_total_meta_300"))


class TestFindPaidPurchaseYearly(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(
            os.environ, {"RPT_PAYMENT_DATA_DIR": self._td.name}, clear=False
        )
        self.env.start()
        import payments as pay

        pay.init_db()
        self.pay = pay

    def tearDown(self) -> None:
        self.env.stop()
        self._td.cleanup()

    def test_yearly_purchase_reissue_lookup(self) -> None:
        pay = self.pay
        tok = pay.mint_download_token(
            filename=pay.platform_filename("windows") or "",
            platform="windows",
            session_id="cs_yr_reissue",
            amount_pence=pay.PRICE_YEARLY_PENCE,
            purchase_id="RPT-YYYY-EEEE-AAAA",
        )
        found = pay.find_paid_purchase_by_id("RPT-YYYY-EEEE-AAAA")
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(int(found["amount_pence"]), 3000)
        self.assertEqual(found["token"], tok)


if __name__ == "__main__":
    unittest.main()
