"""Node residual HELLO refuses non-entitled devices when gate is on."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestNodePaymentHelloGate(unittest.TestCase):
    def setUp(self):
        os.environ["RPT_REQUIRE_PAYMENT_ENTITLEMENT"] = "1"
        from node.payment_entitlement_gate import clear_entitlement_cache

        clear_entitlement_cache()

    def tearDown(self):
        os.environ.pop("RPT_REQUIRE_PAYMENT_ENTITLEMENT", None)
        from node.payment_entitlement_gate import clear_entitlement_cache

        clear_entitlement_cache()

    def test_device_may_connect_respects_remote(self):
        from node.payment_entitlement_gate import device_may_connect

        pub = bytes(range(32))

        def fetch_ok(hex_pub: str):
            self.assertEqual(hex_pub, pub.hex())
            return {"connect_allowed": True, "status": "active"}

        def fetch_no(hex_pub: str):
            return {"connect_allowed": False, "status": "revoked"}

        self.assertTrue(
            device_may_connect(pub, require=True, fetch=fetch_ok, use_cache=False)
        )
        self.assertFalse(
            device_may_connect(pub, require=True, fetch=fetch_no, use_cache=False)
        )
        self.assertTrue(device_may_connect(pub, require=False, fetch=fetch_no))

    def test_hello_refuses_when_not_entitled(self):
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PrivateKey,
            )
        except ImportError:
            self.skipTest("cryptography not installed")

        from node.elgamal import generate_keypair
        from node.handshake import (
            AdmissionError,
            NodeHandshake,
            build_client_hello,
            node_complete_hello,
        )

        node_priv, node_pub = generate_keypair()
        cpriv = Ed25519PrivateKey.generate()
        frame, _, _, _ = build_client_hello(cpriv, node_pub, with_pfs=True)
        hs = NodeHandshake(node_priv, admit_unknown_devices=True, require_pfs=True)

        with mock.patch(
            "node.payment_entitlement_gate.device_may_connect",
            return_value=False,
        ):
            with self.assertRaises(AdmissionError) as ctx:
                node_complete_hello(hs, frame, "10.88.0.20")
            self.assertIn("payment", str(ctx.exception).lower())

        with mock.patch(
            "node.payment_entitlement_gate.device_may_connect",
            return_value=True,
        ):
            reply, result = node_complete_hello(hs, frame, "10.88.0.21")
            self.assertTrue(reply)
            self.assertEqual(len(result.session_id), 8)

    def test_product_server_defaults_require_env(self):
        src = (ROOT / "node" / "server.py").read_text(encoding="utf-8")
        self.assertIn(
            'os.environ.setdefault("RPT_REQUIRE_PAYMENT_ENTITLEMENT", "1")', src
        )


class TestDeviceBindAndSubscriptionPeriod(unittest.TestCase):
    def test_bind_device_and_period_end(self):
        sys.path.insert(0, str(ROOT / "status_page"))
        import payments as pay

        with tempfile.TemporaryDirectory() as td:
            os.environ["RPT_PAYMENT_DATA_DIR"] = td
            pay.activate_connect_entitlement("cs_sub_1", platform="linux")
            pub = "ab" * 32
            bound = pay.bind_device_entitlement("cs_sub_1", pub)
            self.assertTrue(bound.get("ok"))
            dev = pay.get_device_entitlement(pub)
            self.assertTrue(dev.get("connect_allowed"))

            # Cancel at period end — still usable before valid_until
            future = 9_999_999_999.0
            pay.set_entitlement_valid_until(
                "cs_sub_1", future, reason="subscription_cancel_at_period_end"
            )
            ent = pay.get_connect_entitlement("cs_sub_1", now=1_700_000_000.0)
            self.assertTrue(ent["connect_allowed"])
            self.assertEqual(ent["valid_until"], future)

            # After period end — not usable
            ent2 = pay.get_connect_entitlement("cs_sub_1", now=future + 10)
            self.assertFalse(ent2["connect_allowed"])
            self.assertEqual(ent2["status"], "revoked")
            dev2 = pay.get_device_entitlement(pub, now=future + 10)
            self.assertFalse(dev2.get("connect_allowed"))

            # subscription.deleted revokes
            pay.activate_connect_entitlement(
                "cs_sub_2", subscription_id="sub_xyz", platform="windows"
            )
            pay.bind_device_entitlement("cs_sub_2", "cd" * 32)
            ev = {
                "type": "customer.subscription.deleted",
                "data": {"object": {"id": "sub_xyz"}},
            }
            res = pay.process_subscription_lifecycle_event(ev)
            self.assertEqual(res["action"], "revoked")
            self.assertFalse(pay.connect_entitlement_allows("cs_sub_2"))

            # subscription.updated cancel_at_period_end keeps access
            pay.activate_connect_entitlement(
                "cs_sub_3", subscription_id="sub_keep", platform="macos"
            )
            pe = 2_000_000_000.0
            res2 = pay.process_subscription_lifecycle_event(
                {
                    "type": "customer.subscription.updated",
                    "data": {
                        "object": {
                            "id": "sub_keep",
                            "status": "active",
                            "cancel_at_period_end": True,
                            "current_period_end": pe,
                        }
                    },
                },
                now=1_700_000_000.0,
            )
            self.assertIn(res2["action"], ("period_updated", "period_end_scheduled"))
            self.assertTrue(
                pay.connect_entitlement_allows("cs_sub_3", now=1_700_000_000.0)
            )
            self.assertFalse(
                pay.connect_entitlement_allows("cs_sub_3", now=pe + 1)
            )

            del os.environ["RPT_PAYMENT_DATA_DIR"]

    def test_webhook_events_include_subscription(self):
        sys.path.insert(0, str(ROOT / "status_page"))
        import payments as pay

        self.assertIn("customer.subscription.updated", pay.STRIPE_WEBHOOK_EVENTS)
        self.assertIn("customer.subscription.deleted", pay.STRIPE_WEBHOOK_EVENTS)
        self.assertIn("invoice.paid", pay.STRIPE_WEBHOOK_EVENTS)
        guide = pay.stripe_webhook_operator_guidance()
        self.assertIn("customer.subscription.updated", guide["events"])
        self.assertIn("period", guide["note"].lower())
        checklist = (
            ROOT / "status_page" / "docs" / "STRIPE_WEBHOOK_CHECKLIST.md"
        ).read_text(encoding="utf-8")
        self.assertIn("customer.subscription.updated", checklist)
        self.assertIn("current_period_end", checklist)


class TestClientAutoProvisionBind(unittest.TestCase):
    def test_discover_and_installer_provision(self):
        from client.payment_entitlement import (
            ENTITLEMENT_FILENAME,
            provision_entitlement_from_installer_dirs,
            record_payment_success,
        )
        import json

        with tempfile.TemporaryDirectory() as td:
            src_dir = Path(td) / "Downloads"
            dest = Path(td) / "product" / ENTITLEMENT_FILENAME
            src_dir.mkdir()
            (src_dir / ENTITLEMENT_FILENAME).write_text(
                json.dumps(
                    {
                        "session_id": "cs_auto",
                        "status": "active",
                        "updated_at": 1.0,
                    }
                ),
                encoding="utf-8",
            )
            ent = provision_entitlement_from_installer_dirs(
                src_dir, dest_path=dest
            )
            self.assertIsNotNone(ent)
            self.assertEqual(ent.session_id, "cs_auto")
            self.assertTrue(dest.is_file())

    def test_bind_device_posts_json(self):
        from client.payment_entitlement import bind_device_to_remote

        captured = {}

        class FakeResp:
            def read(self):
                return b'{"ok":true,"connect_allowed":true}'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=8.0):
            captured["url"] = req.full_url
            captured["data"] = req.data
            return FakeResp()

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with mock.patch(
                "client.payment_entitlement.local_device_pub_hex",
                return_value="ef" * 32,
            ):
                r = bind_device_to_remote(
                    "cs_bind", base_url="https://example.test"
                )
        self.assertTrue(r.get("ok"))
        self.assertIn("bind-device-entitlement", captured["url"])
        self.assertIn(b"cs_bind", captured["data"])
        self.assertIn(b"ef" * 32, captured["data"])


if __name__ == "__main__":
    unittest.main()
