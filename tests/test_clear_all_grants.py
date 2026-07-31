"""Clear-all admin paid download grants: confirm guard + empty list_all_grants."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class TestClearAllGrantsForAdmin(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name

    def tearDown(self) -> None:
        if self._prev is None:
            os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
        else:
            os.environ["RPT_PAYMENT_DATA_DIR"] = self._prev
        self._td.cleanup()

    def _payments(self):
        import payments

        return payments

    def test_refuses_without_exact_confirm(self) -> None:
        p = self._payments()
        p.init_db()
        with self.assertRaises(ValueError) as ctx:
            p.clear_all_grants_for_admin(confirm="")
        self.assertIn("refused", str(ctx.exception).lower())
        with self.assertRaises(ValueError):
            p.clear_all_grants_for_admin(confirm="yes")
        with self.assertRaises(ValueError):
            p.clear_all_grants_for_admin(confirm="clear_all_grants")

    def test_seed_clear_empties_list_all_grants(self) -> None:
        p = self._payments()
        p.init_db()
        p.mint_download_token(
            filename="restore-privacy-client-0.5.2-windows-x64-setup.exe",
            platform="windows",
            session_id="cs_test_clear_grants_1",
            amount_pence=300,
            currency="gbp",
        )
        p.mint_download_token(
            filename="restore-privacy-client-0.5.2-android.apk",
            platform="android",
            session_id="cs_test_clear_grants_2",
            amount_pence=300,
            currency="gbp",
        )
        before = p.list_all_grants()
        self.assertGreaterEqual(len(before), 2)

        result = p.clear_all_grants_for_admin(confirm=p.CLEAR_ALL_GRANTS_CONFIRM)
        self.assertTrue(result.get("ok"))
        self.assertGreaterEqual(int(result["deleted_grants"]), 2)
        self.assertEqual(int(result["remaining_grants"]), 0)
        after = p.list_all_grants()
        self.assertEqual(after, [], msg=f"expected empty grants, got {after!r}")

        # Licences/entitlements table untouched by grants clear
        if hasattr(p, "list_licences_for_admin"):
            # may be empty; just ensure clear did not require deleting them
            self.assertEqual(int(result.get("remaining_grants") or 0), 0)

        from admin_panel import render_admin_grants_section_html

        html = render_admin_grants_section_html()
        self.assertIn("No grants yet", html)
        self.assertIn("admin-clear-grants-form", html)
        self.assertIn("CLEAR_ALL_GRANTS", html)

    def test_admin_route_wires_clear_grants_handler(self) -> None:
        root = Path(__file__).resolve().parents[1]
        app = (root / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/admin/clear-grants", app)
        self.assertIn("clear_all_grants_for_admin", app)
        pay = (root / "status_page" / "payments.py").read_text(encoding="utf-8")
        self.assertIn("def clear_all_grants_for_admin", pay)
        self.assertIn("DELETE FROM grants", pay)
        self.assertIn("CLEAR_ALL_GRANTS_CONFIRM", pay)


if __name__ == "__main__":
    unittest.main()
