"""Historical gate: 0.2.9 packaging artifacts may remain in tree.

Current public catalog is 0.3.0 (see test_release_0_3_0_public_signed).
"""
from __future__ import annotations
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestRelease029Historical(unittest.TestCase):
    def test_build_script_still_present_as_archive(self):
        self.assertTrue((ROOT / "scripts" / "build_release_0.2.9.py").is_file())
        self.assertTrue((ROOT / "scripts" / "RELEASE_NOTES_0.2.9.md").is_file())

if __name__ == "__main__":
    unittest.main()
