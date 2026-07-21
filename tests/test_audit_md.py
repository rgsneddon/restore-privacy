"""Structural checks for repo-root AUDIT.md (code & policy audit deliverable)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "AUDIT.md"


class TestAuditMd(unittest.TestCase):
    def test_audit_md_exists_and_substantial(self):
        self.assertTrue(AUDIT.is_file(), "AUDIT.md must exist at repo root")
        # GitHub (case-sensitive) must see uppercase path — not only Windows-insensitive open
        self.assertEqual(AUDIT.name, "AUDIT.md")
        text = AUDIT.read_text(encoding="utf-8")
        self.assertGreater(len(text), 3000, "AUDIT.md should be a non-trivial audit")
        self.assertIn("# Restore Privacy", text)
        self.assertIn("Executive summary", text)
        self.assertIn("Findings", text)

    def test_audit_covers_code_and_policies(self):
        text = AUDIT.read_text(encoding="utf-8")
        # Code areas
        for needle in (
            "residual",
            "secrets",
            "client/windows",
            "client/linux",
            "node/",
            "status_page",
        ):
            self.assertIn(needle, text, f"missing code citation area: {needle}")
        # Policies
        for needle in (
            "PRIVACY_POLICY",
            "LICENSE",
            "README",
            "CREDITS",
        ):
            self.assertIn(needle, text, f"missing policy citation: {needle}")

    def test_audit_has_severity_and_version(self):
        text = AUDIT.read_text(encoding="utf-8")
        # Current paid catalog
        self.assertIn("0.3.1", text)
        self.assertIn("82.221.101.241", text)
        self.assertIn("private", text.lower())
        self.assertIn("restoreprivacy.online", text)
        self.assertNotIn("public packages + operator tree", text)
        self.assertNotIn("tests_0.3.1.log", text)
        # Severity labels used in findings
        for sev in ("High", "Medium", "Low", "Info"):
            self.assertIn(sev, text)
        # At least one real path citation beyond headers
        self.assertTrue(
            re.search(r"client/[a-z_/\.]+", text),
            "expected path-like citations under client/",
        )
        self.assertIn("residual_ip_capture", text.lower() + text)

    def test_audit_threat_scenarios_present(self):
        text = AUDIT.read_text(encoding="utf-8")
        self.assertIn("Threat model scenarios", text)
        self.assertIn("VPS compromise", text)
        self.assertIn("device seizure", text.lower())
        self.assertIn("ISP", text)
        self.assertIn("traffic analysis", text.lower())


if __name__ == "__main__":
    unittest.main()

