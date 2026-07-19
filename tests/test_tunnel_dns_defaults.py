"""Product full-tunnel DNS defaults: node tunnel gateway, not public resolvers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.full_tunnel import (  # noqa: E402
    DEFAULT_TUNNEL_DNS_SERVERS,
    DEFAULT_TUNNEL_GATEWAY,
    android_vpn_builder_config,
    build_full_tunnel_plan,
    default_tunnel_dns_servers,
    linux_route_commands,
    windows_route_commands,
)


class TestShippedTunnelDnsDefaults(unittest.TestCase):
    def test_constants_point_at_node_gateway(self):
        self.assertEqual(DEFAULT_TUNNEL_GATEWAY, "10.88.0.1")
        self.assertEqual(DEFAULT_TUNNEL_DNS_SERVERS, ("10.88.0.1",))
        self.assertEqual(default_tunnel_dns_servers(), ["10.88.0.1"])
        # Must not ship Cloudflare / Quad9 as product defaults
        for bad in ("1.1.1.1", "9.9.9.9", "8.8.8.8"):
            self.assertNotIn(bad, DEFAULT_TUNNEL_DNS_SERVERS)

    def test_build_full_tunnel_plan_uses_node_dns(self):
        plan = build_full_tunnel_plan("10.88.0.5")
        self.assertEqual(plan.dns_servers, ["10.88.0.1"])
        self.assertEqual(plan.tunnel_gateway, "10.88.0.1")
        self.assertIn("10.88.0.1", plan.dns_servers)
        self.assertNotIn("1.1.1.1", plan.dns_servers)
        self.assertNotIn("9.9.9.9", plan.dns_servers)

    def test_windows_cmds_set_node_dns(self):
        plan = build_full_tunnel_plan("10.88.0.9", tunnel_iface="RPT")
        cmds = "\n".join(windows_route_commands(plan, "203.0.113.10", if_index=12))
        self.assertIn('static 10.88.0.1 validate=no', cmds)
        self.assertNotIn("1.1.1.1", cmds)
        self.assertNotIn("9.9.9.9", cmds)

    def test_android_builder_dns_from_plan(self):
        plan = build_full_tunnel_plan("10.88.0.3")
        cfg = android_vpn_builder_config(plan)
        self.assertEqual(cfg["dns"], ["10.88.0.1"])
        self.assertNotIn("1.1.1.1", cfg["dns"])

    def test_linux_cmds_resolvectl_node_dns(self):
        plan = build_full_tunnel_plan("10.88.0.4", tunnel_iface="rpt0")
        cmds = "\n".join(
            linux_route_commands(
                plan,
                "203.0.113.10",
                iface="rpt0",
                physical_dev="eth0",
                physical_gw="10.0.0.1",
            )
        )
        self.assertIn("resolvectl dns rpt0 10.88.0.1", cmds)
        self.assertNotIn("1.1.1.1", cmds)

    def test_product_sources_no_public_dns_defaults(self):
        """Structural: shipped product surfaces use node DNS, not CF/Quad9 alone."""
        checks = [
            (
                ROOT / "client" / "windows" / "tun_win.py",
                ("default_tunnel_dns_servers",),
                ("addr=1.1.1.1", "addr=9.9.9.9"),
            ),
            (
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
                / "RptVpnService.kt",
                ('addDnsServer("10.88.0.1")',),
                ('addDnsServer("1.1.1.1")', 'addDnsServer("9.9.9.9")'),
            ),
            (
                ROOT / "client_app" / "ios" / "NativePrep" / "PacketTunnelProvider.swift",
                ('servers: ["10.88.0.1"]',),
                ('"1.1.1.1"', '"9.9.9.9"'),
            ),
            (
                ROOT / "client_app" / "macos" / "NativePrep" / "PacketTunnelProvider.swift",
                ('servers: ["10.88.0.1"]',),
                ('"1.1.1.1"', '"9.9.9.9"'),
            ),
        ]
        for path, need, forbid in checks:
            text = path.read_text(encoding="utf-8")
            for n in need:
                self.assertIn(n, text, f"missing {n!r} in {path}")
            for f in forbid:
                self.assertNotIn(f, text, f"stale public DNS default {f!r} in {path}")


class TestNodeDnsOperatorPrep(unittest.TestCase):
    def test_install_dns_script_and_unbound_conf(self):
        script = ROOT / "node" / "install_dns.sh"
        conf = ROOT / "node" / "unbound-rpt.conf"
        install = ROOT / "node" / "install.sh"
        self.assertTrue(script.is_file())
        self.assertTrue(conf.is_file())
        s = script.read_text(encoding="utf-8")
        c = conf.read_text(encoding="utf-8")
        i = install.read_text(encoding="utf-8")
        self.assertIn("10.88.0.1", s)
        self.assertIn("unbound", s.lower())
        self.assertIn("10.88.0.0/24", s)
        self.assertIn("refuse", c)  # not open resolver
        self.assertIn("interface: 10.88.0.1", c)
        self.assertIn("install_dns.sh", i)
        # Must not open public port 53 via ufw (comment warning is OK)
        for line in s.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            self.assertNotIn(
                "ufw allow 53",
                stripped,
                "must not open public DNS via ufw",
            )


if __name__ == "__main__":
    unittest.main()
