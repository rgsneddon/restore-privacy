"""Helsinki perc_chain boot unit + ledger-preserving deploy path."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class TestPercChainHelsinkiBoot(unittest.TestCase):
    def test_unit_enabled_for_boot_and_persistent_data(self) -> None:
        unit = (ROOT / "perc_chain" / "deploy" / "rpt-perc-chain.service").read_text(
            encoding="utf-8"
        )
        self.assertIn("WantedBy=multi-user.target", unit)
        self.assertIn("Restart=always", unit)
        self.assertIn("PERC_DATA_DIR=/opt/restore-privacy/perc_chain/data", unit)
        self.assertIn("ExecStartPre=", unit)
        self.assertIn("/opt/restore-privacy/perc_chain/data", unit)
        self.assertIn("ExecStart=/usr/bin/node src/internet_node.js", unit)
        self.assertIn("After=network-online.target", unit)

    def test_deploy_preserves_ledger_and_enables_unit(self) -> None:
        src = (ROOT / "scripts" / "deploy_perc_chain_helsinki.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("seed_ledger.json.pre_deploy", src)
        self.assertIn("systemctl enable", src)
        self.assertIn("PERC_DATA_DIR", src)
        # Must not wipe durable data dir on install
        for line in src.splitlines():
            if "rm -rf" in line and "data" in line:
                self.fail(f"deploy must not wipe data dir: {line}")

    def test_package_and_dry_run_shipped_entry(self) -> None:
        import deploy_perc_chain_helsinki as d

        plan = d.dry_run_plan()
        self.assertEqual(plan["unit"], "rpt-perc-chain.service")
        self.assertIn("perc_chain", plan["remote_root"])
        tb = d.package_tarball()
        self.assertTrue(tb.is_file())
        self.assertGreater(tb.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
