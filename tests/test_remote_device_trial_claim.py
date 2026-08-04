"""Desktop free-trial must claim status-host trial before residual HELLO."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestClaimRemoteDeviceTrial(unittest.TestCase):
    def test_claim_posts_device_pub_and_install_id(self) -> None:
        from client.device_trial import claim_remote_device_trial

        captured: dict = {}

        class FakeResp:
            def read(self) -> bytes:
                return json.dumps(
                    {
                        "ok": True,
                        "connect_allowed": True,
                        "kind": "device_trial",
                        "status": "active",
                        "ends_at": 9_999_999_999.0,
                    }
                ).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=12.0):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["body"] = req.data
            captured["timeout"] = timeout
            return FakeResp()

        with tempfile.TemporaryDirectory() as td:
            iid_path = Path(td) / "device_trial_install_id.txt"
            with mock.patch(
                "client.device_trial.default_install_id_path",
                return_value=iid_path,
            ), mock.patch(
                "client.payment_entitlement.local_device_pub_hex",
                return_value="ab" * 32,
            ):
                out = claim_remote_device_trial(
                    device_pub_hex="cd" * 32,
                    base_url="https://restoreprivacy.online",
                    urlopen=fake_urlopen,
                )
        self.assertTrue(out.get("connect_allowed"), out)
        self.assertTrue(out.get("ok"), out)
        self.assertIn("/api/device-trial/claim", captured["url"])
        self.assertEqual(captured["method"], "POST")
        body = json.loads(captured["body"].decode("utf-8"))
        self.assertEqual(body["device_pub"], "cd" * 32)
        self.assertTrue(body.get("install_id"))

    def test_ensure_remote_trial_ok_and_exhausted(self) -> None:
        from client.device_trial import (
            REMOTE_TRIAL_EXHAUSTED_MSG,
            ensure_remote_trial_for_node_hello,
            DeviceTrialState,
            save_device_trial,
        )

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "device_trial.json"
            save_device_trial(DeviceTrialState(), path=path)

            ok, msg = ensure_remote_trial_for_node_hello(
                path=path,
                claim=lambda **kw: {"ok": True, "connect_allowed": True},
            )
            self.assertTrue(ok)
            self.assertEqual(msg, "")

            ok2, msg2 = ensure_remote_trial_for_node_hello(
                path=path,
                claim=lambda **kw: {
                    "ok": False,
                    "connect_allowed": False,
                    "error": "trial_exhausted",
                    "status": "expired",
                },
            )
            self.assertFalse(ok2)
            self.assertEqual(msg2, REMOTE_TRIAL_EXHAUSTED_MSG)

    def test_assert_may_connect_claims_host_trial_on_trial_path(self) -> None:
        """Licence + local trial without KEYGEN must claim remote trial (node HELLO)."""
        from client.licence_gate import accept_licence, assert_may_connect
        from client.device_trial import DeviceTrialState, save_device_trial
        from client.payment_entitlement import PaymentEntitlement, save_payment_entitlement

        with tempfile.TemporaryDirectory() as td:
            lic = Path(td) / "licence_acceptance.json"
            pay = Path(td) / "payment_entitlement.json"
            trial = Path(td) / "device_trial.json"
            accept_licence(lic)
            save_payment_entitlement(PaymentEntitlement(), path=pay)
            save_device_trial(DeviceTrialState(), path=trial)

            claims = {"n": 0}

            def fake_claim(**kw):
                claims["n"] += 1
                return {"ok": True, "connect_allowed": True, "kind": "device_trial"}

            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ), mock.patch(
                "client.device_trial.default_trial_path",
                return_value=trial,
            ), mock.patch(
                "client.device_trial.ensure_remote_trial_for_node_hello",
                side_effect=lambda **kw: (
                    claims.__setitem__("n", claims["n"] + 1) or (True, "")
                ),
            ), mock.patch(
                "client.payment_entitlement.assert_payment_may_connect",
                return_value=(False, "need keygen"),
            ), mock.patch(
                "client.payment_entitlement.load_payment_entitlement",
                return_value=PaymentEntitlement(),
            ), mock.patch(
                "client.payment_entitlement.is_payment_blocking_status",
                return_value=False,
            ):
                ok, msg = assert_may_connect(lic, refresh=False)
            self.assertTrue(ok, msg)
            self.assertEqual(claims["n"], 1)

    def test_assert_may_connect_surfaces_claim_failure(self) -> None:
        from client.licence_gate import accept_licence, assert_may_connect
        from client.device_trial import (
            REMOTE_TRIAL_CLAIM_FAILED_MSG,
            DeviceTrialState,
            save_device_trial,
        )
        from client.payment_entitlement import PaymentEntitlement

        with tempfile.TemporaryDirectory() as td:
            lic = Path(td) / "licence_acceptance.json"
            trial = Path(td) / "device_trial.json"
            accept_licence(lic)
            save_device_trial(DeviceTrialState(), path=trial)

            with mock.patch(
                "client.device_trial.default_trial_path",
                return_value=trial,
            ), mock.patch(
                "client.payment_entitlement.assert_payment_may_connect",
                return_value=(False, "need keygen"),
            ), mock.patch(
                "client.payment_entitlement.load_payment_entitlement",
                return_value=PaymentEntitlement(),
            ), mock.patch(
                "client.payment_entitlement.is_payment_blocking_status",
                return_value=False,
            ), mock.patch(
                "client.device_trial.ensure_remote_trial_for_node_hello",
                return_value=(False, REMOTE_TRIAL_CLAIM_FAILED_MSG),
            ):
                ok, msg = assert_may_connect(lic, refresh=False)
            self.assertFalse(ok)
            self.assertIn("status host", msg.lower())


class TestResidualPostAttachHealth(unittest.TestCase):
    def test_post_attach_ready_pure_gate(self) -> None:
        from client.windows.tunnel_win import residual_post_attach_ready

        self.assertTrue(
            residual_post_attach_ready(
                routes_applied=False,
                dataplane_running=False,
                keepalive_ok=False,
                forward_path_ok=False,
            )
        )
        self.assertFalse(
            residual_post_attach_ready(
                routes_applied=True,
                dataplane_running=True,
                keepalive_ok=True,
                forward_path_ok=False,
                dns_ok=True,
                require_forward_smoke=True,
            )
        )
        self.assertFalse(
            residual_post_attach_ready(
                routes_applied=True,
                dataplane_running=True,
                keepalive_ok=True,
                forward_path_ok=True,
                dns_ok=False,
                require_dns_smoke=True,
            )
        )
        self.assertTrue(
            residual_post_attach_ready(
                routes_applied=True,
                dataplane_running=True,
                keepalive_ok=True,
                forward_path_ok=True,
                dns_ok=True,
                require_forward_smoke=True,
                require_dns_smoke=True,
            )
        )
        self.assertFalse(
            residual_post_attach_ready(
                routes_applied=True,
                dataplane_running=False,
                keepalive_ok=True,
                forward_path_ok=True,
                dns_ok=True,
            )
        )

    def test_forward_path_smoke_uses_connect(self) -> None:
        from client.windows.tunnel_win import residual_forward_path_smoke

        class Sock:
            def close(self):
                pass

        self.assertTrue(
            residual_forward_path_smoke(
                connect_fn=lambda addr, timeout: Sock()
            )
        )

        def boom(addr, timeout):
            raise OSError("no route")

        self.assertFalse(residual_forward_path_smoke(connect_fn=boom))

    def test_tunnel_dns_smoke_accepts_noerror(self) -> None:
        import struct

        from client.windows.tunnel_win import residual_tunnel_dns_smoke

        # Build a minimal NOERROR answer with qd=1 an=1
        # Header: tid, flags=0x8180, qd=1, an=1, ns=0, ar=0
        # Then echo a short name + A rdata (fake)
        name = b"\x07example\x03com\x00"
        q = name + struct.pack("!HH", 1, 1)
        # answer: pointer to name + type A + class IN + ttl + rdlen + ipv4
        ans = b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 60, 4) + bytes([93, 184, 216, 34])
        header = struct.pack("!HHHHHH", 0xA11C, 0x8180, 1, 1, 0, 0)
        payload = header + q + ans

        class FakeSock:
            def settimeout(self, t):
                pass

            def sendto(self, data, addr):
                self._sent = data
                return len(data)

            def recvfrom(self, n):
                return payload, ("10.88.0.1", 53)

            def close(self):
                pass

        self.assertTrue(
            residual_tunnel_dns_smoke(sock_factory=lambda: FakeSock())
        )

        class RefuseSock(FakeSock):
            def recvfrom(self, n):
                # REFUSED, qd=0
                return struct.pack("!HHHHHH", 0xA11C, 0x8105, 0, 0, 0, 0), (
                    "10.88.0.1",
                    53,
                )

        self.assertFalse(
            residual_tunnel_dns_smoke(sock_factory=lambda: RefuseSock())
        )


class TestTimeoutMessageMentionsTrial(unittest.TestCase):
    def test_timeout_copy_mentions_free_trial_registration(self) -> None:
        import socket

        from client.connect import format_connect_failure

        msg = format_connect_failure(
            socket.timeout("timed out"),
            host="178.105.187.178",
            port=44044,
            timeout_s=20.0,
            preferred_host="178.105.187.178",
            tried_hosts=["178.105.187.178", "82.221.101.241"],
        )
        self.assertIn("No reply from VPN node", msg)
        self.assertIn("failover", msg.lower())
        self.assertIn("free trial", msg.lower())
        self.assertIn("status host", msg.lower())


if __name__ == "__main__":
    unittest.main()
