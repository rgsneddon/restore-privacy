"""Kill-switch, IPv6, DNS leak, and WebRTC mitigation tests on shipped helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.full_tunnel import (  # noqa: E402
    android_vpn_builder_config,
    build_full_tunnel_plan,
    default_tunnel_dns_servers,
    linux_ipv6_leak_block_commands,
    windows_ipv6_leak_block_commands,
)
from client.kill_switch import (  # noqa: E402
    LINUX_CHAIN,
    WIN_CRITICAL_ALLOW_NODE,
    WIN_CRITICAL_ALLOW_TUN,
    WIN_CRITICAL_BLOCK_OUT,
    WIN_RULE_PREFIX,
    android_kill_switch_builder_flags,
    assert_windows_ks_commands_safe,
    build_kill_switch_plan,
    default_kill_switch_policy,
    linux_kill_switch_block_commands,
    linux_kill_switch_rollback_commands,
    product_kill_switch_enabled,
    run_kill_switch_commands,
    windows_kill_switch_block_commands,
    windows_kill_switch_rollback_commands,
)
from client.leak_protection import (  # noqa: E402
    PUBLIC_DNS_BLOCKLIST,
    assert_no_public_dns_fallback,
    dns_leak_check_plan,
    product_dns_servers,
    webrtc_leak_mitigations,
)


class TestKillSwitchBuilders(unittest.TestCase):
    def test_windows_block_scoped_not_allow_all(self):
        block = windows_kill_switch_block_commands(server_host="82.221.101.241")
        roll = windows_kill_switch_rollback_commands()
        self.assertTrue(block)
        joined = "\n".join(block)
        self.assertIn(WIN_RULE_PREFIX, joined)
        self.assertIn("82.221.101.241", joined)
        # Must scope node allow + InterfaceAlias for tunnel
        self.assertIn("RemoteAddress", joined)
        self.assertIn("InterfaceAlias", joined)
        self.assertIn(WIN_CRITICAL_ALLOW_TUN, joined)
        self.assertIn(WIN_CRITICAL_BLOCK_OUT, joined)
        self.assertIn("3478", joined)  # STUN
        self.assertIn("5353", joined)  # mDNS
        # Fail if unrestricted allow-all
        violations = assert_windows_ks_commands_safe(block)
        self.assertEqual(violations, [], msg=violations)
        self.assertNotIn("remoteip=any", joined.lower())
        self.assertNotIn("localip=any", joined.lower())
        self.assertNotIn("# iface=", joined)
        self.assertTrue(any(WIN_RULE_PREFIX in c for c in roll))

    def test_assert_windows_ks_rejects_broken_allow_all(self):
        """Safety helper fails if allow rules use remoteip=any without InterfaceAlias."""
        bad = [
            f'netsh advfirewall firewall add rule name="{WIN_RULE_PREFIX}-allow-tun" '
            f"dir=out action=allow enable=yes interfacetype=any "
            f"localip=any remoteip=any profile=any # iface=RPT",
            f'netsh advfirewall firewall add rule name="{WIN_RULE_PREFIX}-block-out" '
            f"dir=out action=block protocol=any enable=yes",
        ]
        v = assert_windows_ks_commands_safe(bad)
        self.assertTrue(v, "must reject remoteip=any allow without InterfaceAlias")

    def test_linux_block_and_rollback(self):
        block = linux_kill_switch_block_commands(
            server_host="82.221.101.241", tunnel_iface="rpt0"
        )
        roll = linux_kill_switch_rollback_commands()
        joined = "\n".join(block)
        self.assertIn(LINUX_CHAIN, joined)
        self.assertIn("-o rpt0", joined)
        self.assertIn("82.221.101.241", joined)
        self.assertIn("-j DROP", joined)
        self.assertTrue(any(LINUX_CHAIN in c for c in roll))

    def test_build_plan_windows_linux(self):
        w = build_kill_switch_plan(
            "windows", server_host="1.2.3.4", tunnel_iface="RPT"
        )
        self.assertEqual(w.platform, "windows")
        self.assertTrue(w.apply)
        self.assertEqual(assert_windows_ks_commands_safe(w.apply), [])
        self.assertTrue(w.rollback)
        l = build_kill_switch_plan(
            "linux", server_host="1.2.3.4", tunnel_iface="rpt0"
        )
        self.assertEqual(l.platform, "linux")
        self.assertTrue(l.apply)

    def test_product_default_on(self):
        import os

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RPT_KILL_SWITCH", None)
            self.assertTrue(product_kill_switch_enabled())
            self.assertTrue(default_kill_switch_policy().enabled)

    def test_run_kill_switch_commands_requires_success_marker(self):
        """kill_switch_applied must not be True when subprocess fails."""
        with mock.patch("client.kill_switch.subprocess.run") as run:
            run.return_value = mock.Mock(
                returncode=1, stdout="", stderr="access denied"
            )
            applied, ok, errs = run_kill_switch_commands(
                ["powershell -Command fail"], platform="windows"
            )
            self.assertFalse(ok)
            self.assertTrue(errs)
            self.assertEqual(applied, [])

        with mock.patch("client.kill_switch.subprocess.run") as run:
            run.return_value = mock.Mock(
                returncode=0, stdout="RPT_KS_OK\n", stderr=""
            )
            applied, ok, errs = run_kill_switch_commands(
                ["powershell -Command ok"], platform="windows"
            )
            self.assertTrue(ok)
            self.assertEqual(len(applied), 1)
            self.assertEqual(errs, [])

        # returncode 0 without marker is not success (Windows)
        with mock.patch("client.kill_switch.subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="done", stderr="")
            _, ok2, _ = run_kill_switch_commands(
                ["powershell -Command soft"], platform="windows"
            )
            self.assertFalse(ok2)

    def test_windows_tunnel_wires_kill_switch_success_path(self):
        src = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("run_kill_switch_commands", src)
        self.assertIn("kill_switch_applied", src)
        self.assertIn("ks_applied = bool(ok)", src)

    def test_linux_tunnel_wires_kill_switch_success_path(self):
        src = (ROOT / "client" / "linux" / "tunnel_linux.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("run_kill_switch_commands", src)
        self.assertIn("kill_switch_applied", src)
        self.assertIn("ks_applied = bool(ok)", src)


class TestAndroidKillSwitchNative(unittest.TestCase):
    def test_rpt_vpn_service_calls_set_blocking(self):
        kt = (
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
        self.assertTrue(kt.is_file(), f"missing {kt}")
        text = kt.read_text(encoding="utf-8")
        self.assertIn("setBlocking(true)", text)
        self.assertIn("Builder()", text)
        # Product full-tunnel still uses node DNS only
        self.assertIn('addDnsServer("10.88.0.1")', text)
        self.assertNotIn("1.1.1.1", text)
        self.assertNotIn("8.8.8.8", text)


class TestDnsLeakAndNoPublicFallback(unittest.TestCase):
    def test_dns_leak_check_plan_ok(self):
        plan = dns_leak_check_plan()
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["dns_servers"], ["10.88.0.1"])
        self.assertEqual(plan["public_fallback_violations"], [])

    def test_assert_rejects_public_dns(self):
        v = assert_no_public_dns_fallback(["1.1.1.1", "10.88.0.1"])
        self.assertTrue(any("1.1.1.1" in x for x in v))
        self.assertEqual(assert_no_public_dns_fallback(["10.88.0.1"]), [])

    def test_product_dns_is_gateway_only(self):
        self.assertEqual(product_dns_servers(), ["10.88.0.1"])
        self.assertEqual(default_tunnel_dns_servers(), ["10.88.0.1"])
        for bad in PUBLIC_DNS_BLOCKLIST:
            self.assertNotIn(bad, product_dns_servers())

    def test_full_tunnel_plan_dns_leak_surface(self):
        p = build_full_tunnel_plan("10.88.0.7")
        self.assertEqual(assert_no_public_dns_fallback(p.dns_servers), [])
        cfg = android_vpn_builder_config(p)
        self.assertEqual(cfg["dns"], ["10.88.0.1"])
        self.assertTrue(cfg.get("disallowPublicDnsFallback"))
        self.assertTrue(cfg.get("killSwitch"))
        self.assertFalse(cfg.get("allowBypass"))
        self.assertTrue(cfg.get("blocking"))


class TestWebRtcAndIpv6(unittest.TestCase):
    def test_webrtc_mitigations_dict(self):
        m = webrtc_leak_mitigations()
        self.assertTrue(m["block_stun_udp_3478"])
        self.assertTrue(m["block_mdns_udp_5353"])
        self.assertTrue(m["kill_switch_required"])
        flags = android_kill_switch_builder_flags()
        self.assertTrue(flags["blocking"])
        self.assertFalse(flags["allowBypass"])

    def test_ipv6_block_still_present(self):
        self.assertTrue(windows_ipv6_leak_block_commands())
        self.assertTrue(linux_ipv6_leak_block_commands())


if __name__ == "__main__":
    unittest.main()
