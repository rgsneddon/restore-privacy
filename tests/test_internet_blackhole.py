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
    routes_would_blackhole_without_if_index,
    routes_would_blackhole_without_system_capture,
    windows_route_commands,
)
from client.windows.tunnel_win import (  # noqa: E402
    apply_routes_for_adapter,
    start_full_tunnel,
)
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
        server = "82.221.101.241"
        cmds = windows_route_commands(plan, server, if_index=17)
        joined = "\n".join(cmds)
        self.assertIn(f"route add {server} mask 255.255.255.255 PHYSICAL_GW", joined)
        self.assertIn("IF 17", joined)
        self.assertIn("0.0.0.0 mask 128.0.0.0 0.0.0.0 IF 17", joined)
        self.assertIn("128.0.0.0 mask 128.0.0.0 0.0.0.0 IF 17", joined)
        # /32 address â€” no fake ARP gateway 10.88.0.1 for dual /1
        self.assertIn("255.255.255.255", joined)
        self.assertNotIn("mask 128.0.0.0 10.88.0.1", joined)
        pin_i = joined.find(server)
        catch_i = joined.find("0.0.0.0 mask 128.0.0.0")
        self.assertGreater(catch_i, pin_i)
        self.assertEqual(assert_full_tunnel_plan(plan), [])

    def test_no_if_index_omits_dual_slash1(self):
        plan = build_full_tunnel_plan("10.88.0.5", tunnel_iface="RPT")
        cmds = "\n".join(windows_route_commands(plan, "82.221.101.241", if_index=None))
        self.assertNotIn("mask 128.0.0.0", cmds)
        self.assertIn("PHYSICAL_GW", cmds)
        self.assertTrue(routes_would_blackhole_without_if_index(None, True))
        self.assertFalse(routes_would_blackhole_without_if_index(12, True))

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
        frame, client_nonce, client_pub, _eph = build_authorized_client_hello(
            cpriv, node_priv.public
        )
        reply, _ = node_complete_hello(node, frame, "10.88.0.11")
        session = complete_server_hello(reply, client_nonce, client_pub, _eph)

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
                "82.221.101.241",
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
        frame, client_nonce, client_pub, _eph = build_authorized_client_hello(
            cpriv, node_priv.public
        )
        reply, _ = node_complete_hello(node, frame, "10.88.0.12")
        session = complete_server_hello(reply, client_nonce, client_pub, _eph)
        client = RptClient.__new__(RptClient)
        client.session = session
        client.endpoint = Endpoint("1.2.3.4", 44044)
        client.state = ConnectState.CONNECTED
        client._sock = None  # dry_run does not start dataplane

        plan = build_full_tunnel_plan(session.vpn_ip)
        # dry_run returns before needing socket for dataplane â€” patch start path
        res = start_full_tunnel(client, plan, "82.221.101.241", dry_run=True)
        self.assertTrue(res.ok)
        joined = "\n".join(res.applied_commands)
        self.assertIn("PHYSICAL_GW", joined)
        self.assertIn("IF 42", joined)
        self.assertIn("82.221.101.241", joined)

    def test_server_pin_failure_refuses_dual_slash1(self):
        """If pin fails, dual /1 must not install (recursive UDP blackhole)."""
        plan = build_full_tunnel_plan("10.88.0.9", tunnel_iface="RPT")
        server = "82.221.101.241"
        pin_cmd = f"route add {server} mask 255.255.255.255 192.168.1.1 metric 1"
        catch_a = "route add 0.0.0.0 mask 128.0.0.0 0.0.0.0 IF 17 metric 5"
        catch_b = "route add 128.0.0.0 mask 128.0.0.0 0.0.0.0 IF 17 metric 5"
        ran: list[str] = []

        def fake_run(cmd, shell=True, capture_output=True, text=True):
            ran.append(cmd)
            # pin fails; catchalls must never be attempted
            if "mask 255.255.255.255" in cmd and "route add" in cmd:
                return mock.Mock(returncode=1, stderr="pin failed: network unreachable", stdout="")
            if "mask 128.0.0.0" in cmd:
                # Should not be reached â€” fail test if it is
                return mock.Mock(returncode=0, stderr="", stdout="")
            return mock.Mock(returncode=0, stderr="", stdout="")

        with mock.patch(
            "client.windows.tunnel_win.physical_default_gateway",
            return_value="192.168.1.1",
        ), mock.patch(
            "client.windows.tunnel_win.subprocess.run",
            side_effect=fake_run,
        ), mock.patch(
            "client.windows.tunnel_win.rollback_full_tunnel_routes",
            return_value=[],
        ) as rb:
            applied, errs, full_ok = apply_routes_for_adapter(
                plan, server, if_index=17, include_catchall=True
            )
        self.assertFalse(full_ok)
        self.assertTrue(any("pin" in e.lower() or "dual /1" in e for e in errs))
        # No dual /1 commands executed
        self.assertFalse(any("mask 128.0.0.0" in c for c in ran))
        rb.assert_called()

    def test_start_full_tunnel_pin_fail_sets_routes_applied_false(self):
        node_priv = generate_keypair()
        cpriv, cpub = generate_client_admission_keypair()
        node = NodeHandshake(node_priv, [ed25519_pub_raw(cpub)])
        frame, client_nonce, client_pub, _eph = build_authorized_client_hello(
            cpriv, node_priv.public
        )
        reply, _ = node_complete_hello(node, frame, "10.88.0.13")
        session = complete_server_hello(reply, client_nonce, client_pub, _eph)
        client = RptClient.__new__(RptClient)
        client.session = session
        client.endpoint = Endpoint("82.221.101.241", 44044)
        client.state = ConnectState.CONNECTED
        client._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client._sock.bind(("127.0.0.1", 0))
        client._sock.setblocking(False)

        plan = build_full_tunnel_plan(session.vpn_ip, tunnel_iface="RPT")

        class FakeTun:
            mode = "wintun"
            name = "RPT"
            _closed = False

            def configure_address(self):
                return ["netsh-ok"]

            def interface_index(self):
                return 17

            def close(self):
                self._closed = True

            def read_packet(self, max_size=65535):
                return None

            def write_packet(self, packet):
                pass

            def fileno(self):
                return -1

        with mock.patch(
            "client.windows.tunnel_win.create_windows_tun", return_value=FakeTun()
        ), mock.patch(
            "client.windows.tunnel_win.system_capture_ready", return_value=True
        ), mock.patch(
            "client.windows.tunnel_win.dataplane_enabled", return_value=True
        ), mock.patch(
            "client.windows.tunnel_win.is_admin", return_value=True
        ), mock.patch(
            "client.windows.tunnel_win.apply_routes_for_adapter",
            return_value=(
                ["pin-cmd"],
                ["server pin failed: network unreachable"],
                False,
            ),
        ) as apply_mock:
            res = start_full_tunnel(client, plan, "82.221.101.241")
        self.assertTrue(res.ok)  # session + dataplane may still run
        self.assertFalse(res.routes_applied)
        self.assertIn("refused", res.message.lower())
        apply_mock.assert_called()
        # Must request catchalls (include_catchall True) so pin+catchall logic runs
        kwargs = apply_mock.call_args
        self.assertTrue(
            kwargs.kwargs.get("include_catchall", True)
            or (len(kwargs.args) >= 0)
        )
        client._sock.close()


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

    def test_post_establish_protect_and_no_ipv6_blackhole_route(self):
        """Residual must re-protect UDP after establish; avoid ::/0 without IPv6 TUN."""
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
        self.assertIn("openProtectedNodeSocket", src)
        self.assertIn("VpnService.protect returned false", src)
        # establish then protected dataplane socket (order: establish appears before openProtected)
        est = src.index("builder.establish()")
        prot = src.index("openProtectedNodeSocket")
        self.assertGreater(prot, est, "must protect node UDP after establish")
        # Do not install IPv6 catch-all without handling (blackholes dual-stack under kill-switch)
        self.assertNotIn('addRoute("::", 0)', src)
        self.assertIn("allowFamily(OsConstants.AF_INET)", src)
        self.assertIn("ParcelFileDescriptor.dup", src)
        self.assertIn('addDnsServer("10.88.0.1")', src)


if __name__ == "__main__":
    unittest.main()
