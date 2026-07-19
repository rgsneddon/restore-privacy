"""IPv6 leak mitigation on product full tunnel + honest status."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.full_tunnel import (  # noqa: E402
    RPT_IPV6_DISABLED_PREFIX,
    android_vpn_builder_config,
    assert_full_tunnel_plan,
    build_full_tunnel_plan,
    linux_ipv6_leak_block_commands,
    linux_ipv6_leak_rollback_commands,
    parse_windows_ipv6_disable_result,
    windows_ipv6_disable_powershell,
    windows_ipv6_leak_block_commands,
    windows_ipv6_leak_rollback_commands,
)
from client.ui_theme import plain_tunnel_status  # noqa: E402
from client.windows.tunnel_win import (  # noqa: E402
    WindowsTunnelResult,
    ipv6_residual_protected,
    residual_ip_capture_active,
)


class TestIpv6LeakCommandBuilders(unittest.TestCase):
    def test_windows_block_and_rollback_are_symmetric_surface(self):
        block = windows_ipv6_leak_block_commands(tunnel_iface="RPT")
        roll = windows_ipv6_leak_rollback_commands(tunnel_iface="RPT")
        self.assertTrue(block)
        self.assertTrue(roll)
        joined_b = "\n".join(block)
        joined_r = "\n".join(roll)
        self.assertIn("ms_tcpip6", joined_b)
        self.assertIn("Disable-NetAdapterBinding", joined_b)
        self.assertIn("Enable-NetAdapterBinding", joined_r)
        self.assertIn("teredo", joined_b.lower())
        # Tunnel name excluded from disable
        self.assertIn("RPT", joined_b)
        # Critical PS must not swallow disable failures
        critical = windows_ipv6_disable_powershell(tunnel_iface="RPT")
        self.assertIn("Disable-NetAdapterBinding", critical)
        self.assertNotIn("SilentlyContinue", critical)
        self.assertIn(RPT_IPV6_DISABLED_PREFIX, critical)
        self.assertIn("exit 1", critical)
        self.assertIn("Get-NetAdapterBinding", critical)

    def test_parse_windows_ipv6_disable_zero_effect_not_ok(self):
        """Zero disables (empty ForEach / all failed) must not pass even with exit 0."""
        ok, n = parse_windows_ipv6_disable_result(0, f"{RPT_IPV6_DISABLED_PREFIX}0\n")
        self.assertFalse(ok)
        self.assertEqual(n, 0)
        ok2, n2 = parse_windows_ipv6_disable_result(1, f"{RPT_IPV6_DISABLED_PREFIX}0\n")
        self.assertFalse(ok2)
        self.assertEqual(n2, 0)
        # exit 0 without marker also fails
        ok3, n3 = parse_windows_ipv6_disable_result(0, "")
        self.assertFalse(ok3)
        self.assertEqual(n3, 0)

    def test_parse_windows_ipv6_disable_positive_count_ok(self):
        ok, n = parse_windows_ipv6_disable_result(0, f"{RPT_IPV6_DISABLED_PREFIX}2\n")
        self.assertTrue(ok)
        self.assertEqual(n, 2)
        # positive count but non-zero exit still fails (PS contract)
        ok_bad, _ = parse_windows_ipv6_disable_result(1, f"{RPT_IPV6_DISABLED_PREFIX}3\n")
        self.assertFalse(ok_bad)

    def test_linux_blackhole_and_rollback(self):
        block = linux_ipv6_leak_block_commands(iface="rpt0")
        roll = linux_ipv6_leak_rollback_commands(iface="rpt0")
        self.assertTrue(any("blackhole default" in c for c in block))
        self.assertTrue(any("ip -6 route del blackhole" in c for c in roll))

    def test_android_builder_includes_ipv6_default_route(self):
        plan = build_full_tunnel_plan("10.88.0.5")
        cfg = android_vpn_builder_config(plan)
        self.assertIn({"addr": "0.0.0.0", "prefix": 0}, cfg["routes"])
        self.assertIn({"addr": "::", "prefix": 0}, cfg["routes"])
        self.assertTrue(cfg.get("ipv6Protected"))
        self.assertEqual(assert_full_tunnel_plan(plan), [])


class TestPlainStatusIpv6Honesty(unittest.TestCase):
    def test_residual_without_ipv6_protection_is_honest(self):
        msg = plain_tunnel_status(
            "connected",
            vpn_ip="10.88.0.2",
            residual_capture=True,
            ipv6_protected=False,
        )
        self.assertIn("IPv6 not protected", msg)
        self.assertIn("IPv4", msg)
        self.assertNotEqual(msg, "Connected - protected")
        self.assertNotIn("IPv6 ISP path blocked", msg)

    def test_residual_with_ipv6_protection(self):
        msg = plain_tunnel_status(
            "connected",
            vpn_ip="10.88.0.2",
            residual_capture=True,
            ipv6_protected=True,
        )
        self.assertIn("IPv6 ISP path blocked", msg)
        self.assertIn("10.88.0.2", msg)

    def test_session_only_unchanged(self):
        msg = plain_tunnel_status(
            "connected", vpn_ip="10.88.0.2", residual_capture=False
        )
        self.assertIn("ISP", msg)


class TestWindowsResultIpv6Flag(unittest.TestCase):
    def test_ipv6_residual_protected_requires_mitigation(self):
        base = WindowsTunnelResult(
            ok=True,
            message="ok",
            applied_commands=[],
            system_capture=True,
            routes_applied=True,
            dataplane=object(),  # truthy presence for residual_ip_capture_active
            ipv6_mitigation_applied=False,
        )
        # residual_ip_capture_active needs dataplane.is_running — use mock-like
        class _Plane:
            def is_running(self):
                return True

        base.dataplane = _Plane()
        self.assertTrue(residual_ip_capture_active(base))
        self.assertFalse(ipv6_residual_protected(base))
        base.ipv6_mitigation_applied = True
        self.assertTrue(ipv6_residual_protected(base))

    def test_apply_ipv6_ok_false_when_critical_disable_fails(self):
        """Failed Disable-NetAdapterBinding must not claim ipv6 protected."""
        from unittest import mock

        from client.full_tunnel import FullTunnelPlan
        from client.windows import tunnel_win as tw

        plan = FullTunnelPlan(tunnel_iface="RPT", tunnel_client_ip="10.88.0.2")

        def fake_run(cmd, shell=True, capture_output=True, text=True):
            r = mock.Mock()
            if "Disable-NetAdapterBinding" in str(cmd):
                r.returncode = 1
                r.stderr = "access denied"
                r.stdout = f"{RPT_IPV6_DISABLED_PREFIX}0\n"
            else:
                r.returncode = 0
                r.stderr = ""
                r.stdout = ""
            return r

        with mock.patch("client.windows.tunnel_win.subprocess.run", side_effect=fake_run):
            applied, ok = tw.apply_ipv6_leak_mitigation(plan)
        self.assertFalse(ok)
        self.assertFalse(any("Disable-NetAdapterBinding" in c for c in applied))

    def test_apply_ipv6_ok_false_on_zero_effect_exit0(self):
        """Silenced/zero-adapter path that still exits 0 must not claim protected."""
        from unittest import mock

        from client.full_tunnel import FullTunnelPlan
        from client.windows import tunnel_win as tw

        plan = FullTunnelPlan(tunnel_iface="RPT", tunnel_client_ip="10.88.0.2")

        def fake_run(cmd, shell=True, capture_output=True, text=True):
            r = mock.Mock()
            r.returncode = 0
            r.stderr = ""
            if "Disable-NetAdapterBinding" in str(cmd):
                # Mimic old SilentlyContinue zero-effect: exit 0, count 0
                r.stdout = f"{RPT_IPV6_DISABLED_PREFIX}0\n"
            else:
                r.stdout = ""
            return r

        with mock.patch("client.windows.tunnel_win.subprocess.run", side_effect=fake_run):
            applied, ok = tw.apply_ipv6_leak_mitigation(plan)
        self.assertFalse(ok, "zero-effect must not set mitigation_ok")
        self.assertFalse(any("Disable-NetAdapterBinding" in c for c in applied))

    def test_apply_ipv6_ok_true_only_when_disable_succeeds(self):
        from unittest import mock

        from client.full_tunnel import FullTunnelPlan
        from client.windows import tunnel_win as tw

        plan = FullTunnelPlan(tunnel_iface="RPT", tunnel_client_ip="10.88.0.2")

        def fake_run(cmd, shell=True, capture_output=True, text=True):
            r = mock.Mock()
            r.returncode = 0
            r.stderr = ""
            if "Disable-NetAdapterBinding" in str(cmd):
                r.stdout = f"{RPT_IPV6_DISABLED_PREFIX}2\n"
            else:
                r.stdout = ""
            return r

        with mock.patch("client.windows.tunnel_win.subprocess.run", side_effect=fake_run):
            applied, ok = tw.apply_ipv6_leak_mitigation(plan)
        self.assertTrue(ok)
        self.assertTrue(any("Disable-NetAdapterBinding" in c for c in applied))


class TestProductSourceIpv6Wiring(unittest.TestCase):
    def test_windows_tunnel_calls_ipv6_helpers(self):
        src = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(encoding="utf-8")
        self.assertIn("apply_ipv6_leak_mitigation", src)
        self.assertIn("rollback_ipv6_leak_mitigation", src)
        self.assertIn("ipv6_mitigation_applied", src)

    def test_linux_tunnel_calls_ipv6_helpers(self):
        src = (ROOT / "client" / "linux" / "tunnel_linux.py").read_text(encoding="utf-8")
        self.assertIn("apply_ipv6_leak_mitigation", src)
        self.assertIn("rollback_ipv6_leak_mitigation", src)

    def test_apps_pass_ipv6_protected_to_status(self):
        for rel in ("client/windows/app.py", "client/linux/app.py"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("ipv6_protected", text)
            self.assertIn("ipv6_residual_protected", text)

    def test_android_adds_ipv6_route(self):
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
        text = path.read_text(encoding="utf-8")
        self.assertIn('addRoute("::", 0)', text)
        self.assertIn("ipv6RouteOk", text)
        self.assertIn("IPv6 not protected", text)
        self.assertIn("EXTRA_IPV6_PROTECTED", text)
        self.assertIn("activeIpv6Protected", text)

    def test_flutter_plain_connected_status_ipv6_honest(self):
        theme = (ROOT / "client_app" / "lib" / "theme.dart").read_text(encoding="utf-8")
        self.assertIn("ipv6Protected", theme)
        self.assertIn("IPv6 not protected", theme)
        cs = (ROOT / "client_app" / "lib" / "connect_status.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("ipv6Protected", cs)
        self.assertIn("IPv6 not protected", cs)

    def test_apple_packet_tunnel_ipv6_settings(self):
        for rel in (
            "client_app/ios/NativePrep/PacketTunnelProvider.swift",
            "client_app/macos/NativePrep/PacketTunnelProvider.swift",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("NEIPv6Settings", text)
            self.assertIn("includedRoutes", text)


if __name__ == "__main__":
    unittest.main()
