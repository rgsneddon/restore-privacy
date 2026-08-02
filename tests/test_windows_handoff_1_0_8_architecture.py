"""Windows WINDOWS_HANDOFF_1.0.8 must document full Suite architecture.

Drives the **shipped** handoff markdown path (and monopin from client/VERSION)
— no hard-coded digests; required phrase gates for first-run, trial, Suite parts.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VERSION = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
HANDOFF = ROOT / "client" / "windows" / f"WINDOWS_HANDOFF_{VERSION}.md"
# Fallback pin file for this goal series
HANDOFF_108 = ROOT / "client" / "windows" / "WINDOWS_HANDOFF_1.0.8.md"


class TestWindowsHandoffArchitecture(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = HANDOFF if HANDOFF.is_file() else HANDOFF_108
        if not path.is_file():
            raise unittest.SkipTest(f"missing Windows handoff: {path}")
        cls.path = path
        cls.text = path.read_text(encoding="utf-8")
        cls.low = cls.text.lower()

    def test_monopin_and_pe_basename(self) -> None:
        # Live monopin from client/VERSION drives expected PE basename + handoff name.
        self.assertIn(VERSION, self.text)
        pe = f"restore-privacy-client-{VERSION}-windows-x64-setup.exe"
        self.assertIn(pe, self.text)
        expected_name = f"WINDOWS_HANDOFF_{VERSION}.md"
        if HANDOFF.is_file():
            self.assertEqual(self.path.name, expected_name)

    def test_first_run_account_seed_licence_before_vpn(self) -> None:
        # Order: account → seed → licence before residual VPN permissions
        self.assertIn("account", self.low)
        self.assertIn("12-word", self.low)
        self.assertIn("seed", self.low)
        self.assertIn("licence", self.low)
        self.assertIn("first-run", self.low)
        self.assertIn("before residual VPN permissions", self.text)
        self.assertIn("account → 12-word recovery seed → licence", self.text)
        # Product pointer
        self.assertIn("first_run_gate", self.text)

    def test_trial_72h_keygen_free_stripe_zero(self) -> None:
        self.assertTrue(
            "72" in self.text and ("hour" in self.low or "hours" in self.low),
            "72-hour residual trial required",
        )
        self.assertTrue(
            "3 day" in self.low or "3-day" in self.low or "(3 days)" in self.low,
        )
        self.assertIn("KEYGEN-free", self.text)
        self.assertIn("device_pub", self.text)
        self.assertIn("install_id", self.text)
        self.assertIn("trial_period_days", self.low)
        self.assertIn("CATALOG_TRIAL_PERIOD_DAYS", self.text)
        self.assertTrue(
            "trial_period_days = 0" in self.text
            or "trial_period_days=0" in self.low
            or "CATALOG_TRIAL_PERIOD_DAYS = 0" in self.text,
        )
        self.assertIn("in-app", self.low)
        # No public reinstall-for-trial attack essay required; operator-only ok
        self.assertIn("not public", self.low)

    def test_suite_parts_vpn_percent_evolve_backup_rpai(self) -> None:
        # Major Suite surfaces
        self.assertIn("VPN", self.text)
        self.assertTrue(
            "%" in self.text or "wallet" in self.low or "perccent" in self.low,
            "wallet / % / Perccent required",
        )
        self.assertIn("Evolve", self.text)
        self.assertIn("Analysis", self.text)
        self.assertIn("Voting", self.text)
        self.assertIn("Backup", self.text)
        self.assertTrue("Credit" in self.text or "credit" in self.low)
        self.assertTrue(
            "rpAI" in self.text or "rpai" in self.low or "Ned" in self.text,
            "rpAI / Ned required",
        )
        self.assertIn("suite_nav", self.text)

    def test_residual_peers_is_de_us_retired(self) -> None:
        self.assertIn("IS", self.text)
        self.assertIn("DE", self.text)
        self.assertTrue(
            "retired" in self.low and ("us" in self.low or "united states" in self.low),
            "US residual retired honesty required",
        )
        self.assertIn("node_elgamal.pub", self.text)
        self.assertIn("de_node_elgamal.pub", self.text)

    def test_windows_build_steps_present(self) -> None:
        self.assertIn("Authenticode", self.text)
        self.assertIn("paid_assets", self.text)
        self.assertIn("breadcrumbs_vault", self.text)
        self.assertIn("client/VERSION", self.text)

    def test_ned_oracle_cojoin_and_admin_rps(self) -> None:
        """Ned/rpAI, oracle absorb, co-join roles, and admin rpS are documented."""
        self.assertIn("Ned", self.text)
        self.assertIn("rpAI", self.text)
        self.assertIn("oracle", self.low)
        self.assertIn("oracle_master", self.text)
        self.assertIn("ned_learn", self.low or self.text)
        self.assertTrue(
            "ned_learn_oracle" in self.text or "ned_learn" in self.low,
        )
        self.assertIn("cojoined", self.low or "co-join" in self.low)
        self.assertIn("cojoined_roles", self.text)
        self.assertIn("/admin/rps", self.text)
        self.assertIn("admin_rps", self.text)
        # Co-join trio
        self.assertIn("VPN + rpAI + Perccent", self.text)

    def test_full_admin_sidebar_map(self) -> None:
        """Every major status-host admin surface is named with path."""
        required_paths = (
            "/admin",
            "/admin/link-generation",
            "/admin/licences",
            "/admin/fleet",
            "/admin/node-operator",
            "/admin/rpos",
            "/admin/rps",
            "/admin/perc",
            "/admin/support-tickets",
            "/admin/accounting",
            "/admin/uploads",
            "/admin/processors",
            "/admin/logout",
        )
        for path in required_paths:
            self.assertIn(path, self.text, f"missing admin path {path}")
        # Link generation tools
        for phrase in (
            "Re-issue by purchase ID",
            "Generate download",
            "Generate KEYGEN",
            "One-month tester",
        ):
            self.assertIn(phrase, self.text)
        # UPLOADS dual push
        self.assertIn("Push selected packages to Helsinki", self.text)
        self.assertIn("Push selected updates to clients", self.text)
        self.assertIn("CHECK BREADCRUMBS", self.text)
        self.assertTrue(
            "size-match" in self.low or "size match" in self.low,
            "UPLOADS host/Helsinki size match gate must be described",
        )
        self.assertIn("ned_learn_oracle", self.text)

    def test_brand_companions_and_end_to_end_map(self) -> None:
        self.assertIn("End-to-end product map", self.text)
        self.assertIn("rpOS", self.text)
        self.assertIn("Pens", self.text)
        self.assertIn("paid_assets", self.text)
        self.assertIn("CHECK BREADCRUMBS", self.text)

    def test_breadcrumbs_vault_stages_windows_handoff(self) -> None:
        """Vault stage path references WINDOWS_HANDOFF_{pin}.md (shipped script)."""
        src = (ROOT / "scripts" / "breadcrumbs_vault.py").read_text(encoding="utf-8")
        self.assertIn("WINDOWS_HANDOFF_", src)
        self.assertIn("client/windows", src.replace("\\", "/"))
        # Architecture observe actions for Windows machine
        self.assertIn("observe_first_run_account_seed_licence_before_vpn", src)
        self.assertIn("observe_72h_keygen_free_trial_then_pay", src)
        self.assertIn("observe_suite_shell_vpn_percent_evolve_backup_rpai", src)
        # Handoff must remain the vault Windows file for monopin 1.0.8
        self.assertTrue(
            (ROOT / "client" / "windows" / "WINDOWS_HANDOFF_1.0.8.md").is_file()
        )


if __name__ == "__main__":
    unittest.main()
