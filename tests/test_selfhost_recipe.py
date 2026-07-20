"""Self-host one-shot recipe exists and is wired for operators."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestSelfHostRecipe(unittest.TestCase):
    def test_selfhost_script_exists(self):
        script = ROOT / "scripts" / "selfhost_node.sh"
        self.assertTrue(script.is_file(), "scripts/selfhost_node.sh missing")
        text = script.read_text(encoding="utf-8")
        self.assertIn("install.sh", text)
        self.assertIn("install_dns.sh", text)
        self.assertIn("install_host_privacy.sh", text)
        self.assertIn("node_elgamal.priv", text)  # warn never distribute
        self.assertIn("node_elgamal.pub", text)
        lower = text.lower()
        self.assertTrue(
            "no user-info" in lower or "nolog" in lower or "no-log" in lower,
            "selfhost recipe should mention no-log / no user-info posture",
        )
        # Privacy limit honesty
        self.assertIn("VPS provider", text)

    def test_node_install_scripts_present(self):
        for name in (
            "install.sh",
            "install_dns.sh",
            "install_host_privacy.sh",
            "install_disk_encryption.sh",
            "install_shutdown_wipe.sh",
            "rpt_shutdown_wipe.sh",
        ):
            p = ROOT / "node" / name
            self.assertTrue(p.is_file(), f"missing node/{name}")

    def test_sundries_points_at_selfhost(self):
        sundries = (ROOT / "sundries.txt").read_text(encoding="utf-8")
        self.assertTrue(
            "selfhost_node.sh" in sundries or "self-host" in sundries.lower(),
            "sundries should mention self-host recipe",
        )


if __name__ == "__main__":
    unittest.main()
