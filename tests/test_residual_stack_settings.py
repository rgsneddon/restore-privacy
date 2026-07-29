"""Dual-stack residual IPv4/IPv6 Settings prefs → full-tunnel policy."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.full_tunnel import (  # noqa: E402
    IPV6_LEAK_POLICY_ALLOW_ISP,
    IPV6_LEAK_POLICY_BLOCK_ISP,
    android_vpn_builder_config,
    build_full_tunnel_plan,
    linux_route_commands,
    plan_wants_ipv4_catchall,
    windows_route_commands,
)
from client.residual_stack import (  # noqa: E402
    KEY_RESIDUAL_IPV4,
    KEY_RESIDUAL_IPV6,
    ResidualStackPrefs,
    apply_residual_stack_to_plan,
    honesty_ipv6_protected,
    plan_wants_ipv6_isp_block,
    residual_stack_from_mapping,
    residual_stack_from_product_settings,
)


class TestResidualStackPrefs(unittest.TestCase):
    def test_defaults_both_on(self):
        s = ResidualStackPrefs()
        self.assertTrue(s.ipv4_enabled)
        self.assertTrue(s.ipv6_enabled)
        self.assertEqual(
            residual_stack_from_mapping(None), ResidualStackPrefs(True, True)
        )
        self.assertEqual(
            residual_stack_from_mapping({}), ResidualStackPrefs(True, True)
        )

    def test_missing_keys_default_on_explicit_false_honoured(self):
        self.assertFalse(
            residual_stack_from_mapping({KEY_RESIDUAL_IPV4: False}).ipv4_enabled
        )
        self.assertTrue(
            residual_stack_from_mapping({KEY_RESIDUAL_IPV4: False}).ipv6_enabled
        )
        self.assertFalse(
            residual_stack_from_mapping({KEY_RESIDUAL_IPV6: False}).ipv6_enabled
        )

    def test_from_product_settings_attrs(self):
        class S:
            residual_ipv4 = False
            residual_ipv6 = True

        stack = residual_stack_from_product_settings(S())
        self.assertFalse(stack.ipv4_enabled)
        self.assertTrue(stack.ipv6_enabled)

    def test_build_plan_ipv4_off_omits_dual_slash1(self):
        plan = build_full_tunnel_plan("10.88.0.5", ipv4_enabled=False, ipv6_enabled=True)
        self.assertEqual(plan.default_routes, [])
        self.assertFalse(plan.is_full_tunnel())
        self.assertEqual(plan.ipv6_leak_policy, IPV6_LEAK_POLICY_BLOCK_ISP)

    def test_build_plan_ipv6_off_allow_isp(self):
        plan = build_full_tunnel_plan("10.88.0.5", ipv4_enabled=True, ipv6_enabled=False)
        self.assertIn("0.0.0.0/1", plan.default_routes)
        self.assertEqual(plan.ipv6_leak_policy, IPV6_LEAK_POLICY_ALLOW_ISP)
        self.assertFalse(plan_wants_ipv6_isp_block(plan))
        cfg = android_vpn_builder_config(plan)
        routes = cfg.get("routes") or []
        self.assertIn({"addr": "0.0.0.0", "prefix": 0}, routes)
        self.assertNotIn({"addr": "::", "prefix": 0}, routes)
        self.assertFalse(cfg.get("ipv6Protected"))

    def test_apply_stack_to_existing_plan(self):
        base = build_full_tunnel_plan("10.88.0.9")
        off = apply_residual_stack_to_plan(
            base, ResidualStackPrefs(ipv4_enabled=True, ipv6_enabled=False)
        )
        self.assertEqual(off.ipv6_leak_policy, IPV6_LEAK_POLICY_ALLOW_ISP)
        self.assertTrue(base.default_routes)  # original unchanged intent via new plan

    def test_honesty_ipv6_never_true_when_settings_off(self):
        self.assertIs(honesty_ipv6_protected(stack_ipv6_enabled=False, mitigation_applied=True), False)
        self.assertIs(honesty_ipv6_protected(stack_ipv6_enabled=True, mitigation_applied=True), True)
        self.assertIs(honesty_ipv6_protected(stack_ipv6_enabled=True, mitigation_applied=False), False)

    def test_windows_route_commands_omit_dual_slash1_when_ipv4_off(self):
        """Shipped windows_route_commands must honour plan.default_routes (not only include_catchall)."""
        off = build_full_tunnel_plan("10.88.0.5", ipv4_enabled=False, ipv6_enabled=True)
        self.assertFalse(plan_wants_ipv4_catchall(off))
        # include_catchall=True would previously ignore empty default_routes — must not now.
        cmds = windows_route_commands(off, "1.2.3.4", if_index=12, include_catchall=True)
        joined = "\n".join(cmds)
        self.assertNotIn("0.0.0.0 mask 128.0.0.0", joined)
        self.assertNotIn("128.0.0.0 mask 128.0.0.0", joined)
        # Server pin + address still present
        self.assertIn("1.2.3.4", joined)
        self.assertIn("10.88.0.5", joined)
        # IPv4 ON still emits dual /1
        on = build_full_tunnel_plan("10.88.0.5", ipv4_enabled=True, ipv6_enabled=True)
        cmds_on = windows_route_commands(on, "1.2.3.4", if_index=12, include_catchall=True)
        joined_on = "\n".join(cmds_on)
        self.assertIn("0.0.0.0 mask 128.0.0.0 0.0.0.0 IF 12", joined_on)
        self.assertIn("128.0.0.0 mask 128.0.0.0 0.0.0.0 IF 12", joined_on)

    def test_linux_route_commands_omit_dual_slash1_when_ipv4_off(self):
        off = build_full_tunnel_plan(
            "10.88.0.5", tunnel_iface="rpt0", ipv4_enabled=False, ipv6_enabled=True
        )
        cmds = linux_route_commands(
            off,
            "1.2.3.4",
            iface="rpt0",
            physical_dev="eth0",
            physical_gw="192.168.1.1",
            include_catchall=True,
        )
        joined = "\n".join(cmds)
        self.assertNotIn("0.0.0.0/1", joined)
        self.assertNotIn("128.0.0.0/1", joined)
        on = build_full_tunnel_plan(
            "10.88.0.5", tunnel_iface="rpt0", ipv4_enabled=True, ipv6_enabled=False
        )
        cmds_on = linux_route_commands(
            on,
            "1.2.3.4",
            iface="rpt0",
            physical_dev="eth0",
            physical_gw="192.168.1.1",
            include_catchall=True,
        )
        joined_on = "\n".join(cmds_on)
        self.assertIn("0.0.0.0/1", joined_on)
        self.assertIn("128.0.0.0/1", joined_on)

    def test_flutter_native_set_residual_stack_wiring(self):
        """Host channel + Packet Tunnel must persist/honour residual_ipv4/ipv6 (not cosmetic)."""
        for rel in (
            "client_app/macos/NativePrep/RptVpnChannel.swift",
            "client_app/ios/NativePrep/RptVpnChannel.swift",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn('case "setResidualStack"', text)
            self.assertIn("residual_ipv4", text)
            self.assertIn("residual_ipv6", text)
        for rel in (
            "client_app/macos/NativePrep/PacketTunnelProvider.swift",
            "client_app/ios/NativePrep/PacketTunnelProvider.swift",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("loadResidualStackPrefs", text)
            self.assertIn("residual_ipv4", text)
            self.assertIn("residual_ipv6", text)
            # Must not hardcode ipv6Protected:true on tunnel start path only
            self.assertIn("ipv6Protected: stack.ipv6", text)
            self.assertIn("stack.ipv4", text)

    def test_android_vpn_service_reads_residual_stack_prefs(self):
        svc = (
            ROOT
            / "client_app/android/app/src/main/kotlin/com/restoreprivacy/"
            "restore_privacy_client/RptVpnService.kt"
        ).read_text(encoding="utf-8")
        prefs = (
            ROOT
            / "client_app/android/app/src/main/kotlin/com/restoreprivacy/"
            "restore_privacy_client/StartupPrefs.kt"
        ).read_text(encoding="utf-8")
        main = (
            ROOT
            / "client_app/android/app/src/main/kotlin/com/restoreprivacy/"
            "restore_privacy_client/MainActivity.kt"
        ).read_text(encoding="utf-8")
        self.assertIn("residualIpv4Enabled", svc)
        self.assertIn("residualIpv4", svc)
        self.assertIn('addRoute("0.0.0.0", 0)', svc)
        self.assertIn("fullTunnel && residualIpv4", svc)
        self.assertIn("KEY_RESIDUAL_IPV4", prefs)
        self.assertIn('"setResidualStack"', main)

    def test_residual_attach_outcome_matrix(self):
        """Shipped residual_attach_outcome decision table (single source of truth)."""
        from client.residual_stack import (
            ResidualAttachOutcome,
            residual_attach_outcome,
            residual_ip_capture_from_fields,
            session_only_from_fields,
        )
        from client.ui_theme import plain_tunnel_status

        plan_off = build_full_tunnel_plan(
            "10.88.0.5", ipv4_enabled=False, ipv6_enabled=True
        )
        plan_on = build_full_tunnel_plan(
            "10.88.0.5", ipv4_enabled=True, ipv6_enabled=True
        )
        self.assertFalse(plan_wants_ipv4_catchall(plan_off))
        self.assertTrue(plan_wants_ipv4_catchall(plan_on))

        # IPv4-off + pin-only success → SESSION_ONLY_OK (no teardown)
        out_off = residual_attach_outcome(
            ok=True,
            routes_applied=False,
            system_capture=True,
            has_dataplane=True,
            plan=plan_off,
        )
        self.assertEqual(out_off, ResidualAttachOutcome.SESSION_ONLY_OK)
        # even if routes_applied is wrongly True, still session-only (no dual /1 intent)
        self.assertEqual(
            residual_attach_outcome(
                ok=True,
                routes_applied=True,
                system_capture=True,
                has_dataplane=True,
                plan=plan_off,
            ),
            ResidualAttachOutcome.SESSION_ONLY_OK,
        )
        self.assertFalse(
            residual_ip_capture_from_fields(
                ok=True,
                routes_applied=True,
                system_capture=True,
                has_dataplane=True,
                plan=plan_off,
            )
        )
        self.assertTrue(
            session_only_from_fields(ok=True, has_dataplane=True, plan=plan_off)
        )

        # IPv4-on + dual /1 applied → RESIDUAL_OK
        out_ok = residual_attach_outcome(
            ok=True,
            routes_applied=True,
            system_capture=True,
            has_dataplane=True,
            plan=plan_on,
        )
        self.assertEqual(out_ok, ResidualAttachOutcome.RESIDUAL_OK)
        self.assertTrue(
            residual_ip_capture_from_fields(
                ok=True,
                routes_applied=True,
                system_capture=True,
                has_dataplane=True,
                plan=plan_on,
            )
        )

        # IPv4-on + no capture → FAIL (teardown)
        out_fail = residual_attach_outcome(
            ok=True,
            routes_applied=False,
            system_capture=True,
            has_dataplane=True,
            plan=plan_on,
        )
        self.assertEqual(out_fail, ResidualAttachOutcome.FAIL)
        out_fail2 = residual_attach_outcome(
            ok=False,
            routes_applied=True,
            system_capture=True,
            has_dataplane=True,
            plan=plan_on,
        )
        self.assertEqual(out_fail2, ResidualAttachOutcome.FAIL)
        out_fail3 = residual_attach_outcome(
            ok=True,
            routes_applied=True,
            system_capture=True,
            has_dataplane=False,
            plan=plan_on,
        )
        self.assertEqual(out_fail3, ResidualAttachOutcome.FAIL)

        # Honesty strings for session-only vs residual
        st = plain_tunnel_status(
            "connected",
            vpn_ip="10.88.0.5",
            residual_capture=False,
            ipv6_protected=False,
        )
        self.assertIn("Session only", st)
        self.assertNotIn("IPv4 via VPN", st)
        st2 = plain_tunnel_status(
            "connected",
            vpn_ip="10.88.0.5",
            residual_capture=True,
            ipv6_protected=False,
        )
        self.assertIn("IPv4 via VPN", st2)

    def test_windows_start_full_tunnel_gate_uses_residual_attach_outcome(self):
        """Shipped require_system_capture gate must call residual_attach_outcome (not bare capture)."""
        win_src = (ROOT / "client/windows/tunnel_win.py").read_text(encoding="utf-8")
        # Gate must use the pure decision table
        self.assertIn("residual_attach_outcome", win_src)
        self.assertIn("ResidualAttachOutcome", win_src)
        self.assertIn("SESSION_ONLY_OK", win_src)
        # SESSION_ONLY_OK must not tear down (no plane.stop immediately for that branch)
        # Locate the require_system_capture block and ensure SESSION_ONLY keeps session
        idx = win_src.index("if require_system_capture:")
        gate = win_src[idx : idx + 2500]
        self.assertIn("residual_attach_outcome", gate)
        self.assertIn("SESSION_ONLY_OK", gate)
        self.assertIn("FAIL", gate)
        # Fail path still tears down
        self.assertIn("plane.stop()", gate)
        # Session-only path must not return ok=False for IPv4-off
        self.assertIn("residual IPv4 off", gate)


class TestWindowsLinuxSettingsStoreDualStack(unittest.TestCase):
    def test_windows_load_save_defaults_and_flip(self):
        from client.windows import settings_store as ws

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            d = ws.default_settings()
            self.assertTrue(d.residual_ipv4)
            self.assertTrue(d.residual_ipv6)
            ws.save_settings(d, path)
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(raw[ws.KEY_RESIDUAL_IPV4])
            self.assertTrue(raw[ws.KEY_RESIDUAL_IPV6])
            # Missing dual-stack keys still load as ON
            del raw[ws.KEY_RESIDUAL_IPV4]
            del raw[ws.KEY_RESIDUAL_IPV6]
            path.write_text(json.dumps(raw), encoding="utf-8")
            loaded = ws.load_settings(path)
            self.assertTrue(loaded.residual_ipv4)
            self.assertTrue(loaded.residual_ipv6)
            # Independent flip
            flipped = ws.ProductSettings(
                residual_ipv4=False,
                residual_ipv6=True,
            )
            ws.save_settings(flipped, path)
            again = ws.load_settings(path)
            self.assertFalse(again.residual_ipv4)
            self.assertTrue(again.residual_ipv6)

    def test_linux_load_save_defaults_and_flip(self):
        from client.linux import settings_store as ls

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            d = ls.default_settings()
            self.assertTrue(d.residual_ipv4 and d.residual_ipv6)
            flipped = ls.ProductSettings(residual_ipv4=True, residual_ipv6=False)
            ls.save_settings(flipped, path)
            again = ls.load_settings(path)
            self.assertTrue(again.residual_ipv4)
            self.assertFalse(again.residual_ipv6)

    def test_settings_ui_source_contains_ipv4_ipv6_labels(self):
        """Structural: primary platform Settings shells expose dual-stack switches."""
        win = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        linux = (ROOT / "client" / "linux" / "app.py").read_text(encoding="utf-8")
        flutter = (ROOT / "client_app" / "lib" / "settings_screen.dart").read_text(
            encoding="utf-8"
        )
        store = (ROOT / "client_app" / "lib" / "settings_store.dart").read_text(
            encoding="utf-8"
        )
        for label in ("IPv4 residual", "IPv6 residual"):
            self.assertIn(label, win)
            self.assertIn(label, flutter)
        self.assertIn("IPv4 residual", linux)
        self.assertIn("IPv6 residual", linux)
        self.assertIn("residualIpv4", store)
        self.assertIn("residualIpv6", store)
        self.assertIn("residual_ipv4", win)
        self.assertIn("residual_ipv6", win)


if __name__ == "__main__":
    unittest.main()
