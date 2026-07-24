"""Product Windows Defender Firewall allows — scoped, safe, residual Connect."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.endpoint import PRODUCT_NODE_HOST, PRODUCT_NODE_PORT  # noqa: E402
from client.kill_switch import (  # noqa: E402
    product_kill_switch_enabled,
    windows_ks_apply_script,
)
from client.kill_switch import KillSwitchPolicy  # noqa: E402
from client.windows.firewall_allow import (  # noqa: E402
    WIN_FW_ALLOW_NODE,
    WIN_FW_ALLOW_PROGRAM,
    WIN_FW_PREFIX,
    assert_windows_fw_allow_commands_safe,
    assert_windows_fw_allow_script_safe,
    apply_windows_fw_allows,
    windows_firewall_connect_hint,
    windows_fw_allow_commands,
    windows_fw_allow_script,
    windows_fw_remove_script,
)


class TestWindowsFwAllowBuilders(unittest.TestCase):
    def test_script_is_scoped_allow_only(self):
        body = windows_fw_allow_script(
            server_host=PRODUCT_NODE_HOST,
            server_port=PRODUCT_NODE_PORT,
            program_path=r"C:\Program Files\RestorePrivacy\RestorePrivacy.exe",
        )
        self.assertIn(WIN_FW_ALLOW_NODE, body)
        self.assertIn(PRODUCT_NODE_HOST, body)
        self.assertIn(str(PRODUCT_NODE_PORT), body)
        self.assertIn("UDP", body)
        self.assertIn("RemoteAddress", body)
        self.assertIn("-Program", body)
        self.assertIn(WIN_FW_PREFIX, body)
        self.assertNotIn("DefaultOutboundAction", body)
        self.assertNotIn("-Action Block", body)
        self.assertNotIn("Action Block", body)
        violations = assert_windows_fw_allow_script_safe(body)
        self.assertEqual(violations, [], msg=violations)
        cmds = windows_fw_allow_commands(
            server_host=PRODUCT_NODE_HOST,
            program_path=r"C:\Apps\RestorePrivacy.exe",
        )
        self.assertEqual(assert_windows_fw_allow_commands_safe(cmds), [])
        self.assertIn("-EncodedCommand", cmds[0])

    def test_assert_rejects_unscoped_block(self):
        bad = (
            "New-NetFirewallRule -DisplayName 'RPT-FW-bad' -Direction Outbound "
            "-Action Block -Enabled True\n"
        )
        v = assert_windows_fw_allow_script_safe(bad)
        self.assertTrue(any("Block" in x for x in v), msg=v)

    def test_kill_switch_default_still_off(self):
        from client.kill_switch import product_kill_switch_parked

        self.assertTrue(product_kill_switch_parked())
        self.assertFalse(product_kill_switch_enabled({}))
        self.assertFalse(product_kill_switch_enabled({"RPT_KILL_SWITCH": "0"}))
        # Parked: RPT_KILL_SWITCH=1 does not enable product residual KS
        self.assertFalse(product_kill_switch_enabled({"RPT_KILL_SWITCH": "1"}))
        # Allow script must not embed KS apply body
        body = windows_fw_allow_script()
        ks = windows_ks_apply_script(
            server_host=PRODUCT_NODE_HOST, policy=KillSwitchPolicy(enabled=True)
        )
        self.assertNotIn("DefaultOutboundAction Block", body)
        self.assertIn("DefaultOutboundAction", ks)

    def test_remove_script_only_touches_rpt_fw(self):
        body = windows_fw_remove_script()
        self.assertIn(f"{WIN_FW_PREFIX}-*", body)
        self.assertNotIn("RPT-KS", body)
        self.assertNotIn("DefaultOutboundAction Block", body)

    def test_connect_hint_mentions_defender_firewall(self):
        hint = windows_firewall_connect_hint()
        self.assertIn("Windows Defender Firewall", hint)
        self.assertIn("AllowFirewall", hint)

    def test_apply_runs_encoded_command(self):
        with mock.patch("subprocess.run") as spr:
            spr.return_value = mock.Mock(
                returncode=0, stdout="RPT_FW_ALLOW_OK\n", stderr=""
            )
            ran, ok, errs = apply_windows_fw_allows(server_host=PRODUCT_NODE_HOST)
        self.assertTrue(ok)
        self.assertEqual(errs, [])
        self.assertTrue(ran)
        self.assertTrue(spr.called)
        self.assertIn("-EncodedCommand", spr.call_args[0][0])


class TestWindowsFwWiring(unittest.TestCase):
    def test_install_and_helpers_ship_allow_firewall(self):
        bat = ROOT / "client" / "windows" / "AllowFirewall.bat"
        self.assertTrue(bat.is_file())
        text = bat.read_text(encoding="utf-8", errors="replace")
        self.assertIn("RPT-FW", text)
        self.assertIn("allow-node-udp", text)
        self.assertIn(PRODUCT_NODE_HOST, text)
        self.assertIn("44044", text)
        inst = (ROOT / "client" / "windows" / "installer.py").read_text(encoding="utf-8")
        self.assertIn("AllowFirewall.bat", inst)
        self.assertIn("apply_windows_fw_allows", inst)
        # Restore Internet failsafe clears stuck KS profile Block (internet blackhole)
        rest = (ROOT / "client" / "windows" / "Restore Internet.bat").read_text(
            encoding="utf-8", errors="replace"
        )
        self.assertIn("RPT-KS", rest)
        self.assertIn("DefaultOutboundAction", rest)
        tun = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(encoding="utf-8")
        self.assertIn("apply_windows_fw_allows", tun)
        self.assertIn("restore_windows_residual_path", tun)
        # Failed residual must full-restore (not leave KS profile Block)
        self.assertIn("run_kill_switch_rollback=True", tun)
        app = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("windows_firewall_connect_hint", app)

    def test_script_profiles_and_port_for_all_users(self):
        body = windows_fw_allow_script(
            server_host=PRODUCT_NODE_HOST,
            server_port=44044,
            program_path=r"C:\Program Files\RestorePrivacy\RestorePrivacy.exe",
        )
        self.assertIn("Profile Any", body)
        self.assertIn("44044", body)
        self.assertIn("UDP", body)
        self.assertIn(WIN_FW_ALLOW_PROGRAM, body)
        # Product allows never change profile DefaultOutboundAction
        self.assertNotIn("Set-NetFirewallProfile", body)


class TestNoInternetBlackholeOnFailedResidual(unittest.TestCase):
    def test_ks_only_after_residual_active_in_source(self) -> None:
        """Kill-switch must not arm before residual_ip_capture_active is proven."""
        tun = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(encoding="utf-8")
        # Residual failure path calls full restore
        fail_idx = tun.find("Could not route device traffic via the VPN node")
        self.assertGreater(fail_idx, 0)
        # restore_windows_residual_path appears before that failure return
        pre = tun[:fail_idx]
        self.assertIn("restore_windows_residual_path", pre)
        # KS apply is after residual check (search for product_kill_switch after residual refuse)
        ks_idx = tun.find("if product_kill_switch_enabled():")
        residual_check = tun.find(
            "require_system_capture and not residual_ip_capture_active"
        )
        self.assertGreater(ks_idx, residual_check, msg="KS must arm after residual check")

    def test_ks_rollback_orphaned_defaults_to_allow(self) -> None:
        from client.kill_switch import windows_ks_rollback_script

        body = windows_ks_rollback_script()
        self.assertIn("RPT-KS", body)
        self.assertIn("DefaultOutboundAction", body)
        self.assertIn("Allow", body)
        self.assertIn("RPT_KS_ROLLBACK_OK", body)
        # Must only remove RPT-KS-* (product allows preserved — comment ok)
        self.assertIn("RPT-KS-*", body)
        self.assertIn("like 'RPT-KS-*'", body.replace('"', "'"))
        # Removal filter is RPT-KS only (not RPT-FW-*)
        self.assertNotRegex(
            body,
            r"like\s+['\"]RPT-FW-\*",
            msg="KS rollback must not remove RPT-FW product allows",
        )


if __name__ == "__main__":
    unittest.main()
