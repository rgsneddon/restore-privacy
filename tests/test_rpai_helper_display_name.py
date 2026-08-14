"""Current rpAI helper display name is GOD (not Ned)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT))


class TestRpaiHelperDisplayName(unittest.TestCase):
    def test_admin_rps_product_constant_is_god(self) -> None:
        from admin_rps import (
            RPAI_HELPER_DISPLAY_NAME,
            apply_current_helper_display_name,
            ned_growth_public_snapshot,
        )

        self.assertEqual(RPAI_HELPER_DISPLAY_NAME, "GOD")
        self.assertNotEqual(RPAI_HELPER_DISPLAY_NAME.lower(), "ned")
        stale = {"product": "Ned · rpAI · Restore Privacy Helper", "nodes_online": 1}
        fixed = apply_current_helper_display_name(stale)
        self.assertIn("GOD", fixed["product"])
        self.assertNotIn("Ned", fixed["product"])
        snap = ned_growth_public_snapshot(stale)
        self.assertIn("GOD", str(snap.get("product") or ""))
        self.assertNotIn("Ned", str(snap.get("product") or ""))

    def test_admin_rps_html_says_god(self) -> None:
        from admin_rps import render_admin_rps_page_html

        raw = render_admin_rps_page_html()
        html = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
        self.assertIn("GOD", html)
        self.assertNotIn("Ned · rpAI", html)
        self.assertNotIn("rpS · Ned", html)

    def test_privacy_policy_current_name_is_god(self) -> None:
        text = (ROOT / "PRIVACY_POLICY.md").read_text(encoding="utf-8")
        pub = (ROOT / "status_page" / "public" / "PRIVACY_POLICY.md").read_text(
            encoding="utf-8"
        )
        for blob in (text, pub):
            self.assertIn("rpAI (GOD)", blob)
            self.assertIn("rpAI · GOD", blob)
            self.assertNotIn("rpAI (Ned)", blob)
            self.assertNotIn("rpAI · Ned", blob)

    def test_flutter_display_const_is_god(self) -> None:
        src = (ROOT / "client_app" / "lib" / "suite_rpai_tab.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("static const String kNedName = 'GOD';", src)
        self.assertIn("I\\'m GOD, your Restore Privacy Helper", src)
        self.assertNotIn("kNedName = 'Ned'", src)

    def test_rpos_helper_name_const_is_god(self) -> None:
        from rpos.installer import NED_NAME

        self.assertEqual(NED_NAME, "GOD")


if __name__ == "__main__":
    unittest.main()
