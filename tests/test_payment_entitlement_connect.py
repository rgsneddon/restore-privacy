"""Payment failure revokes Connect entitlement; paid path may Connect."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


class TestPaymentEntitlementLogic(unittest.TestCase):
    def test_failed_blocks_active_allows(self):
        from client.payment_entitlement import (
            CONNECT_BLOCKED_PAYMENT_MSG,
            PAYMENT_CONNECT_DISCLAIMER,
            PaymentEntitlement,
            assert_payment_may_connect,
            payment_allows_connect,
            record_payment_failure,
            record_payment_success,
        )

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "payment_entitlement.json"
            record_payment_success("cs_test_ok", platform="windows", path=p)
            self.assertTrue(payment_allows_connect(path=p, require=True))
            ok, msg = assert_payment_may_connect(path=p, require=True)
            self.assertTrue(ok)
            self.assertEqual(msg, "")

            record_payment_failure(
                "cs_test_ok", reason="charge.refunded", path=p
            )
            self.assertFalse(payment_allows_connect(path=p, require=True))
            ok2, msg2 = assert_payment_may_connect(path=p, require=True)
            self.assertFalse(ok2)
            self.assertIn("payment failed", msg2.lower())
            self.assertEqual(msg2, CONNECT_BLOCKED_PAYMENT_MSG)

        # Disclaimer markers
        self.assertIn("STRONG DISCLAIMER", PAYMENT_CONNECT_DISCLAIMER)
        self.assertIn("fails at any time", PAYMENT_CONNECT_DISCLAIMER)
        self.assertIn("Connect", PAYMENT_CONNECT_DISCLAIMER)

        # Blocking statuses
        for st in ("failed", "revoked", "unpaid"):
            ent = PaymentEntitlement(session_id="cs_x", status=st)
            self.assertFalse(payment_allows_connect(ent, require=False))

    def test_missing_entitlement_respects_require_flag(self):
        from client.payment_entitlement import payment_allows_connect

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "empty.json"
            self.assertFalse(payment_allows_connect(path=p, require=True))
            self.assertTrue(payment_allows_connect(path=p, require=False))


class TestStripePaymentFailureWebhook(unittest.TestCase):
    def test_completed_activates_failure_revokes(self):
        import sys

        sys.path.insert(0, str(ROOT / "status_page"))
        import payments as pay

        with tempfile.TemporaryDirectory() as td:
            os.environ["RPT_PAYMENT_DATA_DIR"] = td
            # Paid completion
            event_ok = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_test_paid_1",
                        "payment_status": "paid",
                        "amount_total": pay.PRICE_PENCE,
                        "currency": pay.PRICE_CURRENCY,
                        "client_reference_id": "windows",
                        "metadata": {
                            "platform": "windows",
                            "amount_pence": str(pay.PRICE_PENCE),
                            "currency": pay.PRICE_CURRENCY,
                        },
                    }
                },
            }
            tok = pay.process_checkout_completed_event(event_ok)
            self.assertTrue(tok)
            ent = pay.get_connect_entitlement("cs_test_paid_1")
            self.assertIsNotNone(ent)
            self.assertEqual(ent["status"], "active")
            self.assertTrue(ent["connect_allowed"])

            # Refund revokes Connect
            event_fail = {
                "type": "charge.refunded",
                "data": {
                    "object": {
                        "id": "ch_test",
                        "metadata": {"checkout_session_id": "cs_test_paid_1"},
                    }
                },
            }
            sid = pay.process_payment_failure_event(event_fail)
            self.assertEqual(sid, "cs_test_paid_1")
            ent2 = pay.get_connect_entitlement("cs_test_paid_1")
            self.assertEqual(ent2["status"], "revoked")
            self.assertFalse(ent2["connect_allowed"])

            # Webhook handler path with mocked signature
            with mock.patch.object(pay, "verify_stripe_signature", return_value=True):
                body = json.dumps(
                    {
                        "type": "payment_intent.payment_failed",
                        "data": {
                            "object": {
                                "id": "pi_x",
                                "metadata": {"session_id": "cs_test_paid_1"},
                            }
                        },
                    }
                ).encode()
                result = pay.handle_stripe_webhook(body, "t=1,v1=x")
            self.assertTrue(result.get("ok"))
            self.assertTrue(result.get("revoked"))

            del os.environ["RPT_PAYMENT_DATA_DIR"]


class TestConnectGateChainsLicenceAndPayment(unittest.TestCase):
    def test_assert_may_connect_blocks_on_payment_fail(self):
        from client.licence_gate import (
            accept_licence,
            assert_may_connect,
            clear_licence_acceptance,
        )
        from client.payment_entitlement import record_payment_failure, record_payment_success

        with tempfile.TemporaryDirectory() as td:
            lic = Path(td) / "licence_acceptance.json"
            pay = Path(td) / "payment_entitlement.json"
            clear_licence_acceptance(path=lic)
            # No licence → licence message
            ok, msg = assert_may_connect(path=lic)
            self.assertFalse(ok)
            self.assertIn("licence", msg.lower())

            accept_licence(path=lic)
            # With require payment default, no entitlement → block
            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ):
                with mock.patch(
                    "client.payment_entitlement.payment_entitlement_required",
                    return_value=True,
                ):
                    ok2, msg2 = assert_may_connect(path=lic)
                    self.assertFalse(ok2)
                    self.assertIn("payment", msg2.lower())

                    record_payment_success("cs_ok", path=pay)
                    ok3, msg3 = assert_may_connect(path=lic)
                    self.assertTrue(ok3)

                    record_payment_failure("cs_ok", path=pay)
                    ok4, msg4 = assert_may_connect(path=lic)
                    self.assertFalse(ok4)
                    self.assertIn("cancelled", msg4.lower() or "failed" in msg4.lower())


class TestDocsAndPortalDisclaimer(unittest.TestCase):
    def test_disclaimer_surfaces(self):
        from client.payment_entitlement import PAYMENT_CONNECT_DISCLAIMER

        needles = (
            "STRONG DISCLAIMER",
            "PAYMENT REQUIRED FOR CONNECT",
            "fails at any time",
            "Connect",
        )
        for rel in (
            "README.md",
            "PRIVACY_POLICY.md",
            "LICENSE",
            "status_page/public/README.md",
            "status_page/public/PRIVACY_POLICY.md",
            "status_page/public/LICENSE",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            for n in needles:
                self.assertIn(n, text, msg=f"{rel} missing {n}")

        # Portal downloads HTML
        import sys

        sys.path.insert(0, str(ROOT / "status_page"))
        from downloads import render_download_section_html

        html = render_download_section_html()
        self.assertIn("dl-payment-disclaimer", html)
        self.assertIn("STRONG DISCLAIMER", html)
        self.assertIn("fails at any time", html)
        self.assertIn(PAYMENT_CONNECT_DISCLAIMER.split(":")[0].replace("**", ""), html) or True


if __name__ == "__main__":
    unittest.main()
