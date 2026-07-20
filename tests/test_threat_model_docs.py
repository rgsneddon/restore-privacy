"""Structural gates: shipped threat-model docs (audit, privacy policy, README)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    path = ROOT / name
    assert path.is_file(), f"missing shipped file: {name}"
    text = path.read_text(encoding="utf-8")
    assert len(text) > 500, f"{name} too short"
    return text


class TestAuditThreatScenarios(unittest.TestCase):
    def test_threat_model_section_and_scenarios(self):
        text = _read("AUDIT.md")
        # Section exists (heading)
        self.assertTrue(
            re.search(r"(?im)^#+ .*threat model", text)
            or "Threat model scenarios" in text,
            "AUDIT.md must have a threat model / scenarios section",
        )
        self.assertIn("Threat model scenarios", text)

        # Scenario A — VPS compromise (substantive, not bare list)
        self.assertIn("VPS compromise", text)
        self.assertIn("Scenario A", text)
        vps_idx = text.index("Scenario A")
        vps_chunk = text[vps_idx : vps_idx + 1600].lower()
        self.assertIn("vps compromise", vps_chunk)
        self.assertIn("residual risk", vps_chunk)
        self.assertTrue(
            "no-log" in vps_chunk or "nolog" in vps_chunk or "no log" in vps_chunk
        )
        self.assertTrue("memory" in vps_chunk or "in-memory" in vps_chunk)

        # Scenario B — ISP / traffic analysis
        self.assertIn("Scenario B", text)
        self.assertTrue(
            "traffic analysis by ISP" in text
            or "Traffic analysis by ISP" in text
            or (
                "ISP" in text
                and "traffic analysis" in text.lower()
            ),
            "audit must document ISP traffic analysis scenario",
        )
        isp_chunk = text[text.index("Scenario B") : text.index("Scenario B") + 1200].lower()
        self.assertIn("isp", isp_chunk)
        self.assertIn("traffic analysis", isp_chunk)
        self.assertIn("residual risk", isp_chunk)

        # Scenario C — client device seizure
        self.assertIn("Scenario C", text)
        self.assertTrue(
            "device seizure" in text.lower() or "client device seizure" in text.lower(),
            "audit must document client device seizure",
        )
        seiz_idx = text.index("Scenario C")
        seiz_chunk = text[seiz_idx : seiz_idx + 1200].lower()
        self.assertIn("device seizure", seiz_chunk)
        self.assertIn("device key", seiz_chunk)
        self.assertTrue("local" in seiz_chunk or "disk" in seiz_chunk)

        # Anti over-claim
        low = text.lower()
        self.assertNotIn("dpi-undetectable", low)
        self.assertNotIn("guarantees undetectability", low)
        self.assertNotIn("multi-hop residual is active", low)


class TestPrivacyThreatModel(unittest.TestCase):
    def test_threat_model_heading_protects_and_limits(self):
        text = _read("PRIVACY_POLICY.md")
        self.assertTrue(
            re.search(r"(?im)^#+ .*threat model", text),
            "PRIVACY_POLICY.md must have a Threat model heading",
        )
        low = text.lower()
        self.assertIn("what it protects against", low)
        self.assertTrue(
            "what it does **not** protect against" in low
            or "what it does not protect against" in low
            or "does **not** protect" in low
            or "does not protect against" in low,
            "policy must state what it does not protect against",
        )
        self.assertIn("endpoint correlation", low)
        self.assertIn("behavioral analysis", low)
        # Scenario families at policy level
        self.assertIn("vps", low)
        self.assertIn("isp", low)
        self.assertTrue("seizure" in low or "device seizure" in low)
        # Honesty
        self.assertNotIn("dpi-undetectable", low)
        self.assertIn("mitigation", low)
        self.assertIn("AUDIT.md", text)


class TestReadmeThreatModel(unittest.TestCase):
    def test_readme_threat_model_section(self):
        text = _read("README.md")
        self.assertTrue(
            re.search(r"(?im)^#+ .*threat model", text),
            "README.md must have a Threat model heading",
        )
        low = text.lower()
        self.assertIn("what it protects against", low)
        self.assertTrue(
            "what it does **not** protect against" in low
            or "what it does not protect against" in low
            or "does **not** protect against" in low
            or "does not protect against" in low
        )
        self.assertIn("endpoint correlation", low)
        self.assertIn("behavioral analysis", low)
        self.assertIn("PRIVACY_POLICY", text)
        self.assertIn("AUDIT.md", text)
        self.assertNotIn("dpi-undetectable", low)
        self.assertNotIn("impossible to detect", low)


class TestThreatModelNoOverclaim(unittest.TestCase):
    def test_three_docs_share_honesty(self):
        for name in ("AUDIT.md", "PRIVACY_POLICY.md", "README.md"):
            text = _read(name).lower()
            self.assertNotIn("dpi-undetectable", text)
            self.assertNotIn("perfect anonymity", text)
            # multi-hop residual must not be claimed as shipped product routing
            self.assertNotIn("multi-hop residual is active", text)
            self.assertNotIn("multi-hop residual routing is implemented", text)


if __name__ == "__main__":
    unittest.main()
