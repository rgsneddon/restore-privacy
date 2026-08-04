"""Windows Settings kill-switch panel must use white text on dark red."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestKillSwitchSettingsContrast(unittest.TestCase):
    def test_app_py_ks_panel_uses_white_on_dark_red(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        # Panel background
        self.assertIn('#3A1014', src)
        # Body / enable label high-contrast white (not theme text on maroon)
        self.assertIn('_KS_FG_WHITE', src)
        self.assertIn('#FFFFFF', src)
        # Body label must use white constant, not t["text"] on the KS panel
        # Structural: white fg assigned for SETTINGS_BODY and ENABLE label
        self.assertIn("KILL_SWITCH_SETTINGS_BODY", src)
        self.assertIn("KILL_SWITCH_ENABLE_SWITCH_LABEL", src)
        # Label that paints SETTINGS_BODY (not the import line)
        marker = "text=KILL_SWITCH_SETTINGS_BODY"
        self.assertIn(marker, src)
        body_idx = src.index(marker)
        window = src[body_idx : body_idx + 350]
        self.assertIn("_KS_FG_WHITE", window)
        self.assertNotIn('fg=t["text"]', window)
        emarker = "text=KILL_SWITCH_ENABLE_SWITCH_LABEL"
        self.assertIn(emarker, src)
        enable_idx = src.index(emarker)
        ewin = src[enable_idx : enable_idx + 300]
        self.assertIn("_KS_FG_WHITE", ewin)


if __name__ == "__main__":
    unittest.main()
