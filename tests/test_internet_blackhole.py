"""Anti-blackhole: full-tunnel routes + dataplane must not trap internet traffic."""

from __future__ import annotations

import socket
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.connect import ClientSession, ConnectState, RptClient  # noqa: E402
from client.dataplane import RptDataPlane  # noqa: E402
from client.endpoint import Endpoint  # noqa: E402
from client.full_tunnel import (  # noqa: E402
    assert_full_tunnel_plan,
    build_full_tunnel_plan,
    routes_would_blackhole_without_system_capture,
    windows_route_commands,
)
from client.windows.tunnel_win import start_full_tunnel  # noqa: E402
from client.connect import complete_server_hello, build_authorized_client_hello  # noqa: E402
from node.elgamal import generate_keypair  # noqa: E402
from node.handshake import (  # noqa: E402
    NodeHandshake,
    ed25519_pub_raw,
    generate_client_admission_keypair,
    node_complete_hello,
)
from node.routing import (  # noqa: E402
    assert_routing_enabled,
    build_nat_masquerade_commands,
    build_sysctl_forward_commands,
    routing_config_block,
)


class TestWindowsAntiBlackholeRoutes(unittest.TestCase):
    def test_route_plan_pins_server_before_catchall_and_uses_if_index(self):
        plan = build_full_tunnel_plan("10.88.0.5", tunnel_iface="RPT")
        server = "104.156.224.47"
        cmds = windows_route_commands(plan, server, if_index=17)
        joined = "\n".join(cmds)
        self.assertIn(f"route add {server} mask 255.255.255.255 PHYSICAL_GW", joined)
        self.assertIn("IF 17", joined)
        self.assertIn("0.0.0.0 mask 128.0.0.0 0.0.0.0 IF 17", joined)
        self.assertIn("128.0.0.0 mask 128.0.0.0 0.0.0.0 IF 17", joined)
        # Address must put gateway on-link (/24), not bare /32 alone
        self.assertIn("255.255.255.0", joined)
        self.assertIn("10.88.0.1", joined)
        pin_i = joined.find(server)
        catch_i = joined.find("0.0.0.0 mask 128.0.0.0")
        self.assertGreater(catch_i, pin_i)
        self.assertEqual(assert_full_tunnel_plan(plan), [])

    def test_routes_would_blackhole_helper(self):
        self.assertTrue(
            routes_would_blackhole_without_system_capture(
                system_capture=False, apply_default_routes=True
            )
        )
        self.assertFalse(
            routes_would_blackhole_without_system_capture(
                system_capture=True, apply_default_routes=True
            )
        )

    def test_queue_tun_does_not_claim_full_tunnel_routes(self):
        """force_queue path must not install dual /1 (would blackhole)."""
        node_priv = generate_keypair()
        cpriv, cpub = generate_client_admission_keypair()
        node = NodeHandshake(node_priv, [ed25519_pub_raw(cpub)])
        frame, client_nonce, client_pub = build_authorized_client_hello(
            cpriv, node_priv.public
        )
        reply, _ = node_complete_hello(node, frame, "10.88.0.11")
        session = complete_server_hello(reply, client_nonce, client_pub)

        client = RptClient.__new__(RptClient)
        client.session = session
        client.endpoint = Endpoint("127.0.0.1", 9)
        client.state = ConnectState.CONNECTED
        client._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client._sock.bind(("127.0.0.1", 0))
        client._sock.setblocking(False)

        plan = build_full_tunnel_plan(session.vpn_ip, tunnel_iface="RPT")
        with mock.patch(
            "client.windows.tunnel_win.apply_routes_for_adapter"
        ) as apply_mock:
            res = start_full_tunnel(
                client,
                plan,
                "104.156.224.47",
                force_queue=True,
                prefer_system_capture=False,
            )
            self.assertTrue(res.ok, res.message)
            self.assertFalse(res.routes_applied)
            apply_mock.assert_not_called()
            self.assertIn("blackhole", res.message.lower())
            self.assertTrue(res.dataplane is not None and res.dataplane.is_running())
            res.dataplane.stop()
        client._sock.close()

    def test_dry_run_includes_if_bound_routes_and_server_pin(self):
        node_priv = generate_keypair()
        cpriv, cpub = generate_client_admission_keypair()
        node = NodeHandshake(node_priv, [ed25519_pub_raw(cpub)])
        frame, client_nonce, client_pub = build_authorized_client_hello(
            cpriv, node_priv.public
        )
        reply, _ = node_complete_hello(node, frame, "10.88.0.12")
        session = complete_server_hello(reply, client_nonce, client_pub)
        client = RptClient.__new__(RptClient)
        client.session = session
        client.endpoint = Endpoint("1.2.3.4", 44044)
        client.state = ConnectState.CONNECTED
        client._sock = None  # dry_run does not start dataplane

        plan = build_full_tunnel_plan(session.vpn_ip)
        # dry_run returns before needing socket for dataplane — patch start path
        res = start_full_tunnel(client, plan, "104.156.224.47", dry_run=True)
        self.assertTrue(res.ok)
        joined = "\n".join(res.applied_commands)
        self.assertIn("PHYSICAL_GW", joined)
        self.assertIn("IF 42", joined)
        self.assertIn("104.156.224.47", joined)


class TestNodeNatStructural(unittest.TestCase):
    def test_masquerade_and_forward_in_shipped_routing(self):
        block = routing_config_block()
        cfg = {"routing": block}
        self.assertEqual(assert_routing_enabled(cfg), [])
        nat = "\n".join(build_nat_masquerade_commands())
        self.assertIn("MASQUERADE", nat)
        self.assertIn("FORWARD", nat)
        self.assertIn("10.88.0.0/24", nat)
        sysctl = "\n".join(build_sysctl_forward_commands())
        self.assertIn("ip_forward=1", sysctl)
        self.assertIn("rp_filter=2", sysctl)

    def test_install_sh_has_nat(self):
        text = (ROOT / "node" / "install.sh").read_text(encoding="utf-8")
        self.assertIn("MASQUERADE", text)
        self.assertIn("ip_forward", text)
        self.assertIn("FORWARD", text)


class TestAndroidTunReadNotAvailableOnly(unittest.TestCase):
    def test_vpn_service_uses_blocking_tun_read(self):
        path = (
            ROOT
            / "client_app"
            / "android"
            / "app"
            / "src"
            / "main"
            / "kotlin"
            / "com"
            / "restoreprivacy"
            / "restore_privacy_client"
            / "RptVpnService.kt"
        )
        src = path.read_text(encoding="utf-8")
        self.assertIn("inTun.read(buf)", src)
        # Must not rely solely on available() for the forward path
        self.assertNotIn("inTun.available()", src)
        self.assertIn("protect(sock)", src)
        self.assertIn("addDisallowedApplication", src)
        self.assertIn("addRoute(\"0.0.0.0\", 0)", src)


if __name__ == "__main__":
    unittest.main()
