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
    WIN_RULE_PREFIX,
    KillSwitchPolicy,
    android_kill_switch_builder_flags,
    assert_windows_ks_commands_safe,
    assert_windows_ks_rollback_restores_profiles,
    assert_windows_ks_script_safe,
    build_kill_switch_plan,
    decode_powershell_encoded_command,
    default_kill_switch_policy,
    linux_kill_switch_block_commands,
    linux_kill_switch_rollback_commands,
    parse_powershell_script,
    product_kill_switch_enabled,
    run_kill_switch_commands,
    windows_kill_switch_block_commands,
    windows_kill_switch_rollback_commands,
    windows_ks_apply_script,
    windows_ks_rollback_script,
)
from client.leak_protection import (  # noqa: E402
    PUBLIC_DNS_BLOCKLIST,
    assert_no_public_dns_fallback,
    dns_leak_check_plan,
    product_dns_servers,
    webrtc_leak_mitigations,
)

# Explicit opt-in policy for unit tests of rule builders (product default is off).
_KS_ON = KillSwitchPolicy(enabled=True)


class TestKillSwitchBuilders(unittest.TestCase):
    def test_windows_uses_profile_default_not_unscoped_block(self):
        """No unscoped Action=Block rule; fail-closed via DefaultOutboundAction."""
        body = windows_ks_apply_script(server_host="82.221.101.241", policy=_KS_ON)
        self.assertTrue(body)
        self.assertIn("\n", body)  # multi-line, not space-joined
        self.assertIn(WIN_RULE_PREFIX, body)
        self.assertIn("82.221.101.241", body)
        self.assertIn("RemoteAddress", body)
        self.assertIn("InterfaceAlias", body)
        self.assertIn(WIN_CRITICAL_ALLOW_NODE, body)
        self.assertIn(WIN_CRITICAL_ALLOW_TUN, body)
        self.assertIn("Set-NetFirewallProfile", body)
        self.assertIn("DefaultOutboundAction", body)
        self.assertIn("Block", body)
        self.assertNotIn(f"{WIN_RULE_PREFIX}-block-out", body)
        self.assertIn("3478", body)
        self.assertIn("5353", body)
        self.assertIn(
            '"$env:ProgramData\\RestorePrivacy\\ks-outbound-state.json"', body
        )
        violations = assert_windows_ks_script_safe(body)
        self.assertEqual(violations, [], msg=violations)
        # Emission is EncodedCommand wrapping the pure body
        cmds = windows_kill_switch_block_commands(
            server_host="82.221.101.241", policy=_KS_ON
        )
        self.assertEqual(len(cmds), 1)
        self.assertIn("-EncodedCommand", cmds[0])
        decoded = decode_powershell_encoded_command(cmds[0])
        self.assertEqual(decoded, body)
        self.assertEqual(assert_windows_ks_commands_safe(cmds), [])
        roll = windows_kill_switch_rollback_commands()
        rv = assert_windows_ks_rollback_restores_profiles(roll)
        self.assertEqual(rv, [], msg=rv)
        roll_body = windows_ks_rollback_script()
        self.assertIn("DefaultOutboundAction", roll_body)

    def test_assert_rejects_unscoped_block_rule(self):
        """Safety helper fails on New-NetFirewallRule Action=Block with no scope."""
        bad_body = "\n".join(
            [
                "New-NetFirewallRule -DisplayName 'RPT-KS-block-out' "
                "-Direction Outbound -Action Block -Enabled True -Profile Any",
                "New-NetFirewallRule -DisplayName 'RPT-KS-allow-node' "
                "-Direction Outbound -Action Allow -RemoteAddress 1.2.3.4",
                "New-NetFirewallRule -DisplayName 'RPT-KS-allow-tun-if' "
                "-Direction Outbound -Action Allow -InterfaceAlias RPT",
                "Set-NetFirewallProfile -Name Domain -DefaultOutboundAction Block",
            ]
        )
        v = assert_windows_ks_script_safe(bad_body)
        self.assertTrue(
            any("unscoped" in x.lower() or "block-out" in x.lower() for x in v),
            f"expected unscoped block rejection, got {v}",
        )

    def test_assert_windows_ks_rejects_broken_allow_all(self):
        """Safety helper fails if allow rules use remoteip=any without InterfaceAlias."""
        bad_body = "\n".join(
            [
                f'netsh advfirewall firewall add rule name="{WIN_RULE_PREFIX}-allow-tun" '
                f"dir=out action=allow enable=yes interfacetype=any "
                f"localip=any remoteip=any profile=any # iface=RPT",
                f'netsh advfirewall firewall add rule name="{WIN_RULE_PREFIX}-block-out" '
                f"dir=out action=block protocol=any enable=yes",
            ]
        )
        v = assert_windows_ks_script_safe(bad_body)
        self.assertTrue(v, "must reject remoteip=any allow without InterfaceAlias")

    def test_port_scoped_block_is_allowed(self):
        """STUN RemotePort blocks are scoped — not treated as global blackhole."""
        body = windows_ks_apply_script(server_host="1.2.3.4", policy=_KS_ON)
        self.assertIn("RemotePort", body)
        self.assertIn("3478", body)
        self.assertEqual(assert_windows_ks_script_safe(body), [])
        cmds = windows_kill_switch_block_commands(server_host="1.2.3.4", policy=_KS_ON)
        self.assertEqual(assert_windows_ks_commands_safe(cmds), [])

    def test_powershell_apply_and_rollback_parse_clean(self):
        """Real PowerShell AST parse of pure bodies (gates runnability)."""
        apply_body = windows_ks_apply_script(
            server_host="82.221.101.241", tunnel_iface="RPT", policy=_KS_ON
        )
        roll_body = windows_ks_rollback_script()
        for label, body in (("apply", apply_body), ("rollback", roll_body)):
            errs = parse_powershell_script(body)
            self.assertEqual(
                errs,
                [],
                msg=f"{label} script parse errors: {errs}\n--- body ---\n{body[:500]}",
            )
        # EncodedCommand round-trip body is identical and still parses
        cmd = windows_kill_switch_block_commands(
            server_host="82.221.101.241", policy=_KS_ON
        )[0]
        decoded = decode_powershell_encoded_command(cmd)
        self.assertEqual(decoded, apply_body)
        self.assertEqual(parse_powershell_script(decoded), [])

    def test_no_space_joined_command_emission(self):
        """Shipped argv must not use space-collapsed -Command multi-statements."""
        for cmd in windows_kill_switch_block_commands(
            server_host="1.2.3.4", policy=_KS_ON
        ):
            self.assertIn("-EncodedCommand", cmd)
            self.assertNotIn("-Command \"", cmd)
            self.assertNotIn("='Stop' $", cmd)  # classic broken join artifact

    def test_linux_block_and_rollback(self):
        block = linux_kill_switch_block_commands(
            server_host="82.221.101.241", tunnel_iface="rpt0", policy=_KS_ON
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
            "windows",
            server_host="1.2.3.4",
            tunnel_iface="RPT",
            policy=_KS_ON,
        )
        self.assertEqual(w.platform, "windows")
        self.assertTrue(w.apply)
        self.assertEqual(assert_windows_ks_commands_safe(w.apply), [])
        self.assertEqual(assert_windows_ks_rollback_restores_profiles(w.rollback), [])
        self.assertTrue(w.rollback)
        l = build_kill_switch_plan(
            "linux",
            server_host="1.2.3.4",
            tunnel_iface="rpt0",
            policy=_KS_ON,
        )
        self.assertEqual(l.platform, "linux")
        self.assertTrue(l.apply)

    def test_product_default_off(self):
        """Product residual: kill switch is parked — never arms on residual Connect."""
        import os

        from client.kill_switch import product_kill_switch_parked

        self.assertTrue(product_kill_switch_parked())
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RPT_KILL_SWITCH", None)
            self.assertFalse(product_kill_switch_enabled())
            self.assertFalse(default_kill_switch_policy().enabled)
            plan = build_kill_switch_plan(
                "windows", server_host="1.2.3.4", tunnel_iface="RPT"
            )
            self.assertEqual(plan.apply, [])
        # Parked: even explicit env opt-in does not enable product residual KS
        with mock.patch.dict(os.environ, {"RPT_KILL_SWITCH": "1"}, clear=False):
            self.assertFalse(product_kill_switch_enabled())
            self.assertFalse(default_kill_switch_policy().enabled)
            plan_on = build_kill_switch_plan(
                "windows", server_host="1.2.3.4", tunnel_iface="RPT"
            )
            self.assertEqual(plan_on.apply, [])

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

        with mock.patch("client.kill_switch.subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="done", stderr="")
            _, ok2, _ = run_kill_switch_commands(
                ["powershell -Command soft"], platform="windows"
            )
            self.assertFalse(ok2)

    def test_windows_tunnel_gates_kill_switch_on_policy(self):
        src = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("product_kill_switch_enabled", src)
        self.assertIn("run_kill_switch_commands", src)
        self.assertIn("kill_switch_applied", src)

    def test_linux_tunnel_gates_kill_switch_on_policy(self):
        src = (ROOT / "client" / "linux" / "tunnel_linux.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("product_kill_switch_enabled", src)
        self.assertIn("run_kill_switch_commands", src)
        self.assertIn("kill_switch_applied", src)


class TestAndroidKillSwitchNative(unittest.TestCase):
    def test_rpt_vpn_service_no_set_blocking_by_default(self):
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
        # Product residual: kill switch removed — no builder blocking call
        self.assertNotIn(".setBlocking(", text)
        self.assertIn("Kill switch removed", text)
        self.assertIn("Builder()", text)
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
        # Kill switch off by default on product residual
        self.assertFalse(cfg.get("killSwitch"))
        self.assertTrue(cfg.get("allowBypass"))
        self.assertFalse(cfg.get("blocking"))


class TestWebRtcAndIpv6(unittest.TestCase):
    def test_webrtc_mitigations_dict(self):
        m = webrtc_leak_mitigations()
        self.assertFalse(m["kill_switch_required"])
        self.assertFalse(m.get("kill_switch_default_on", True))
        self.assertTrue(m.get("kill_switch_parked"))
        flags = android_kill_switch_builder_flags()
        self.assertFalse(flags["blocking"])
        self.assertTrue(flags["allowBypass"])
        self.assertFalse(flags["killSwitch"])

    def test_ipv6_block_still_present(self):
        self.assertTrue(windows_ipv6_leak_block_commands())
        self.assertTrue(linux_ipv6_leak_block_commands())


if __name__ == "__main__":
    unittest.main()
