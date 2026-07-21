"""Payment failure revokes Connect entitlement; paid path may Connect.

Drives the *shipped* helpers used by Windows/Linux/Flutter Connect — not a
re-implemented oracle. Covers:
  - post-pay session import → active entitlement → Connect allowed
  - remote refresh on Connect so revoke/refund blocks
  - Stripe failure webhooks including payment_intent without session metadata
  - docs / portal strong disclaimers
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
sys.path.insert(0, str(ROOT))


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
            ok, msg = assert_payment_may_connect(
                path=p, require=True, refresh=False
            )
            self.assertTrue(ok)
            self.assertEqual(msg, "")

            record_payment_failure(
                "cs_test_ok", reason="charge.refunded", path=p
            )
            self.assertFalse(payment_allows_connect(path=p, require=True))
            ok2, msg2 = assert_payment_may_connect(
                path=p, require=True, refresh=False
            )
            self.assertFalse(ok2)
            self.assertIn("payment failed", msg2.lower())
            self.assertEqual(msg2, CONNECT_BLOCKED_PAYMENT_MSG)

        self.assertIn("STRONG DISCLAIMER", PAYMENT_CONNECT_DISCLAIMER)
        self.assertIn("fails at any time", PAYMENT_CONNECT_DISCLAIMER)
        self.assertIn("Connect", PAYMENT_CONNECT_DISCLAIMER)

        for st in ("failed", "revoked", "unpaid"):
            ent = PaymentEntitlement(session_id="cs_x", status=st)
            self.assertFalse(payment_allows_connect(ent, require=False))

    def test_missing_entitlement_respects_require_flag(self):
        from client.payment_entitlement import payment_allows_connect

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "empty.json"
            self.assertFalse(payment_allows_connect(path=p, require=True))
            self.assertTrue(payment_allows_connect(path=p, require=False))

    def test_import_session_and_verify_paid_path(self):
        """After paid checkout, client obtains active entitlement via session id."""
        from client.payment_entitlement import (
            import_session_and_verify,
            payment_allows_connect,
        )

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "payment_entitlement.json"

            def fake_fetch(sid: str):
                self.assertEqual(sid, "cs_live_paid")
                return {
                    "session_id": sid,
                    "status": "active",
                    "connect_allowed": True,
                    "platform": "windows",
                }

            ent = import_session_and_verify(
                "cs_live_paid", path=p, fetch=fake_fetch
            )
            self.assertEqual(ent.status, "active")
            self.assertEqual(ent.session_id, "cs_live_paid")
            self.assertTrue(payment_allows_connect(path=p, require=True))

    def test_refresh_on_connect_observes_remote_revoke(self):
        """assert_payment_may_connect refreshes so refund cancels client Connect."""
        from client.payment_entitlement import (
            assert_payment_may_connect,
            record_payment_success,
        )

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "payment_entitlement.json"
            record_payment_success("cs_revokeme", path=p)

            def fake_fetch(sid: str):
                return {
                    "session_id": sid,
                    "status": "revoked",
                    "reason": "charge.refunded",
                    "connect_allowed": False,
                }

            ok, msg = assert_payment_may_connect(
                path=p, require=True, refresh=True, fetch=fake_fetch
            )
            self.assertFalse(ok)
            self.assertIn("payment failed", msg.lower())
            # Local file updated so subsequent Connect stays blocked offline
            from client.payment_entitlement import load_payment_entitlement

            self.assertEqual(load_payment_entitlement(p).status, "revoked")

    def test_discover_entitlement_file_provisions_install(self):
        from client.payment_entitlement import (
            ENTITLEMENT_FILENAME,
            payment_allows_connect,
            try_discover_entitlement_file,
        )

        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "product" / ENTITLEMENT_FILENAME
            src_dir = Path(td) / "Downloads"
            src_dir.mkdir()
            src = src_dir / ENTITLEMENT_FILENAME
            src.write_text(
                json.dumps(
                    {
                        "session_id": "cs_from_download",
                        "status": "active",
                        "platform": "linux",
                        "reason": "payment_succeeded",
                        "updated_at": 1.0,
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch(
                "client.payment_entitlement.entitlement_discovery_candidates",
                return_value=[src],
            ):
                ent = try_discover_entitlement_file(dest_path=dest)
            self.assertIsNotNone(ent)
            self.assertEqual(ent.session_id, "cs_from_download")
            self.assertTrue(payment_allows_connect(path=dest, require=True))


class TestStripePaymentFailureWebhook(unittest.TestCase):
    def test_completed_activates_failure_revokes(self):
        sys.path.insert(0, str(ROOT / "status_page"))
        import payments as pay

        with tempfile.TemporaryDirectory() as td:
            os.environ["RPT_PAYMENT_DATA_DIR"] = td
            event_ok = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_test_paid_1",
                        "payment_status": "paid",
                        "payment_intent": "pi_test_paid_1",
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

            # Refund with metadata (legacy path)
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

    def test_refund_via_payment_intent_without_session_metadata(self):
        """Payment Link charges often lack checkout_session_id metadata."""
        sys.path.insert(0, str(ROOT / "status_page"))
        import payments as pay

        with tempfile.TemporaryDirectory() as td:
            os.environ["RPT_PAYMENT_DATA_DIR"] = td
            event_ok = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_plink_1",
                        "payment_status": "paid",
                        "payment_intent": "pi_plink_1",
                        "amount_total": pay.PRICE_PENCE,
                        "currency": pay.PRICE_CURRENCY,
                        "client_reference_id": "linux",
                        "metadata": {
                            "platform": "linux",
                            "amount_pence": str(pay.PRICE_PENCE),
                            "currency": pay.PRICE_CURRENCY,
                        },
                    }
                },
            }
            self.assertTrue(pay.process_checkout_completed_event(event_ok))
            self.assertTrue(pay.connect_entitlement_allows("cs_plink_1"))

            # Real-world refund: only payment_intent on charge, no session meta
            event_refund = {
                "type": "charge.refunded",
                "data": {
                    "object": {
                        "id": "ch_plink_refund",
                        "payment_intent": "pi_plink_1",
                        "metadata": {},
                    }
                },
            }
            sid = pay.process_payment_failure_event(event_refund)
            self.assertEqual(sid, "cs_plink_1")
            ent = pay.get_connect_entitlement("cs_plink_1")
            self.assertEqual(ent["status"], "revoked")
            self.assertFalse(ent["connect_allowed"])

            # payment_intent.payment_failed by PI id alone
            pay.activate_connect_entitlement(
                "cs_plink_1",
                platform="linux",
                payment_intent_id="pi_plink_1",
            )
            event_pi_fail = {
                "type": "payment_intent.payment_failed",
                "data": {
                    "object": {
                        "id": "pi_plink_1",
                        "metadata": {},
                    }
                },
            }
            sid2 = pay.process_payment_failure_event(event_pi_fail)
            self.assertEqual(sid2, "cs_plink_1")
            self.assertFalse(pay.connect_entitlement_allows("cs_plink_1"))

            # Entitlement file payload for thank-you download
            pay.activate_connect_entitlement(
                "cs_plink_1", payment_intent_id="pi_plink_1"
            )
            payload = pay.client_entitlement_file_payload("cs_plink_1")
            self.assertIsNotNone(payload)
            self.assertEqual(payload["session_id"], "cs_plink_1")
            self.assertEqual(payload["status"], "active")

            del os.environ["RPT_PAYMENT_DATA_DIR"]


class TestConnectGateChainsLicenceAndPayment(unittest.TestCase):
    def test_assert_may_connect_blocks_on_payment_fail(self):
        from client.licence_gate import (
            accept_licence,
            assert_may_connect,
            clear_licence_acceptance,
        )
        from client.payment_entitlement import (
            record_payment_failure,
            record_payment_success,
        )

        with tempfile.TemporaryDirectory() as td:
            lic = Path(td) / "licence_acceptance.json"
            pay = Path(td) / "payment_entitlement.json"
            clear_licence_acceptance(path=lic)
            ok, msg = assert_may_connect(path=lic)
            self.assertFalse(ok)
            self.assertIn("licence", msg.lower())

            accept_licence(path=lic)
            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ):
                with mock.patch(
                    "client.payment_entitlement.payment_entitlement_required",
                    return_value=True,
                ):
                    # No network bootstrap in this test
                    with mock.patch(
                        "client.payment_entitlement.ensure_entitlement_for_connect",
                        side_effect=lambda **kw: None,
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
                        self.assertTrue(
                            "cancelled" in msg4.lower()
                            or "failed" in msg4.lower()
                        )

    def test_connect_path_refresh_blocks_after_server_revoke(self):
        """Shipped assert_may_connect (Connect path) observes remote revoke."""
        from client.licence_gate import accept_licence, assert_may_connect
        from client.payment_entitlement import record_payment_success

        with tempfile.TemporaryDirectory() as td:
            lic = Path(td) / "licence_acceptance.json"
            pay = Path(td) / "payment_entitlement.json"
            accept_licence(path=lic)
            record_payment_success("cs_was_ok", path=pay)

            def fake_fetch(sid: str):
                return {
                    "status": "failed",
                    "reason": "payment_intent.payment_failed",
                    "connect_allowed": False,
                }

            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ):
                with mock.patch(
                    "client.payment_entitlement.fetch_remote_entitlement_status",
                    side_effect=lambda sid, **kw: fake_fetch(sid),
                ):
                    ok, msg = assert_may_connect(path=lic)
            self.assertFalse(ok)
            self.assertIn("payment", msg.lower())


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

        sys.path.insert(0, str(ROOT / "status_page"))
        from downloads import render_download_section_html
        from payments import render_post_payment_thankyou_html

        html = render_download_section_html()
        self.assertIn("dl-payment-disclaimer", html)
        self.assertIn("STRONG DISCLAIMER", html)
        self.assertIn("fails at any time", html)

        ty = render_post_payment_thankyou_html(
            download_path="/download?token=abc",
            filename="RestorePrivacy-0.3.3-linux.run",
            platform="linux",
            session_id="cs_thankyou_1",
        )
        self.assertIn("connect-session-id", ty)
        self.assertIn("payment_entitlement.json", ty)
        self.assertIn("entitlement-file-link", ty)
        self.assertIn("Settings", ty)
        self.assertIn("STRONG DISCLAIMER", ty)
        self.assertIn(PAYMENT_CONNECT_DISCLAIMER.split(":")[0].replace("**", ""), html)


if __name__ == "__main__":
    unittest.main()
