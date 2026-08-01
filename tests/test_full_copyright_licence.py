"""Shipped full-copyright licence replaces MIT product grant."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.licence_gate import (  # noqa: E402
    CURRENT_LICENCE_ID,
    short_licence_summary,
)


class TestFullCopyrightLicenceShipped(unittest.TestCase):
    def test_canonical_licence_themes(self):
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertGreater(len(text), 1500)
        self.assertNotIn("MIT License", text)
        self.assertNotRegex(
            text,
            re.compile(r"Permission is hereby granted, free of charge", re.I),
        )
        self.assertIn("FULL COPYRIGHT", text.upper())
        self.assertIn("All rights reserved", text)
        self.assertIn("Architecture", text)
        self.assertIn("copy", text.lower())
        self.assertIn("transmission", text.lower())
        self.assertIn("AS IS", text)
        self.assertIn("WITHOUT WARRANTY", text.upper())
        self.assertIn("Restore Privacy Suite", text)
        self.assertNotIn("Restore Privacy VPN", text)
        self.assertIn("Client Package", text)
        # Public mirror byte-equal
        pub = (ROOT / "status_page" / "public" / "LICENSE").read_text(encoding="utf-8")
        self.assertEqual(text, pub)

    def test_licence_gate_id_bumped_and_summary(self):
        self.assertNotIn("MIT", CURRENT_LICENCE_ID)
        self.assertIn("COPYRIGHT", CURRENT_LICENCE_ID.upper())
        summary = short_licence_summary().lower()
        self.assertIn("full copyright", summary)
        self.assertIn("no warranty", summary)
        self.assertIn("vpn", summary)
        self.assertIn("architecture", summary)
        self.assertNotIn("mit licence", summary)

    def test_flutter_short_summary_matches_full_copyright(self):
        """Shipped Dart kShortLicenceSummary must not claim MIT product grant."""
        dart = (ROOT / "client_app" / "lib" / "licence_gate.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("kShortLicenceSummary", dart)
        self.assertIn("FULL-COPYRIGHT-2026", dart)
        # Extract the const string body for theme checks
        self.assertIn("full copyright", dart.lower())
        self.assertIn("AS IS", dart)
        self.assertIn("architecture", dart.lower())
        self.assertIn("VPN", dart)
        self.assertNotIn("MIT licence", dart)
        self.assertNotIn("MIT license", dart.lower().replace("mit-style", ""))
        # Product claim must not say provided under the MIT
        self.assertNotIn("under the MIT", dart)
        self.assertNotIn("under the mit", dart.lower())

    def test_docs_not_claim_mit_for_product(self):
        for rel in (
            "README.md",
            "status_page/public/README.md",
            "CREDITS.md",
            "status_page/public/CREDITS.md",
            "sundries.txt",
            "client_app/lib/licence_gate.dart",
            "client/licence_gate.py",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            # Product grant must not be advertised as MIT
            self.assertNotIn("MIT License", text)
            self.assertNotIn("under the MIT", text)
            self.assertNotIn("MIT for original project code", text)
            self.assertNotIn("Project license for original code: **MIT**", text)
            if rel.endswith(".md") or rel.endswith(".txt"):
                self.assertNotRegex(
                    text,
                    re.compile(
                        r"License\s*\|\s*\[LICENSE\]\(LICENSE\)\s*\(MIT\)",
                        re.I,
                    ),
                )


if __name__ == "__main__":
    unittest.main()
