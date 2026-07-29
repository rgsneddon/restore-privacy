"""Native Apple seal for monopin 0.5.4 — drives shipped CFBundle gate on real zip."""

from __future__ import annotations

import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MONOPIN = "0.5.4"
MACOS_ZIP = ROOT / "releases" / MONOPIN / f"restore-privacy-client-{MONOPIN}-macos.zip"
IOS_ZIP = ROOT / "releases" / MONOPIN / f"restore-privacy-client-{MONOPIN}-ios.zip"


class TestApple054NativeSeal(unittest.TestCase):
    def test_macos_cfbundle_matches_monopin_via_audit_gate(self):
        if not MACOS_ZIP.is_file():
            self.skipTest(f"missing {MACOS_ZIP} (native seal not staged in this checkout)")
        import sys

        sys.path.insert(0, str(ROOT / "status_page"))
        from apple_package_audit import require_macos_zip_matches_monopin

        ver = require_macos_zip_matches_monopin(MACOS_ZIP, MONOPIN)
        self.assertEqual(ver, MONOPIN)
        self.assertGreater(MACOS_ZIP.stat().st_size, 1_000_000)

    def test_ios_zip_has_runner_and_monopin_plist(self):
        if not IOS_ZIP.is_file():
            self.skipTest(f"missing {IOS_ZIP}")
        self.assertGreater(IOS_ZIP.stat().st_size, 100_000)
        with zipfile.ZipFile(IOS_ZIP) as zf:
            names = zf.namelist()
            self.assertTrue(
                any(n.endswith("Runner.app/Info.plist") for n in names),
                "iOS zip must contain Runner.app/Info.plist",
            )
            # monopin in Info.plist as CFBundleShortVersionString
            plist_name = next(n for n in names if n.endswith("Runner.app/Info.plist"))
            raw = zf.read(plist_name)
            # binary or XML plist — monopin string must appear
            self.assertIn(MONOPIN.encode("utf-8"), raw)


if __name__ == "__main__":
    unittest.main()
