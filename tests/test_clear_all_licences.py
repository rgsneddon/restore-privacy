"""Clear-all admin licences: confirm guard + empty list_licences_for_admin."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class TestClearAllLicencesForAdmin(unittest.TestCase):
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
            p.clear_all_licences_for_admin(confirm="")
        self.assertIn("refused", str(ctx.exception).lower())
        with self.assertRaises(ValueError):
            p.clear_all_licences_for_admin(confirm="yes")
        with self.assertRaises(ValueError):
            p.clear_all_licences_for_admin(confirm="clear_all_licences")

    def test_seed_clear_empties_list_licences_for_admin(self) -> None:
        """Real path: activate entitlements → clear → admin list empty."""
        p = self._payments()
        p.init_db()
        kg1 = p.activate_connect_entitlement(
            "cs_test_clear_all_1",
            platform="windows",
            keygen="RPT-KEY-CLEAR-TEST-0001",
        )
        kg2 = p.activate_connect_entitlement(
            "cs_test_clear_all_2",
            platform="android",
            keygen="RPT-KEY-CLEAR-TEST-0002",
        )
        self.assertTrue(kg1)
        self.assertTrue(kg2)
        try:
            p.bind_device_entitlement(
                "cs_test_clear_all_1",
                "aa" * 32,
            )
        except Exception:
            pass

        before = p.list_licences_for_admin()
        self.assertGreaterEqual(len(before), 2)

        result = p.clear_all_licences_for_admin(confirm=p.CLEAR_ALL_LICENCES_CONFIRM)
        self.assertTrue(result.get("ok"))
        self.assertGreaterEqual(int(result["deleted_connect_entitlements"]), 2)
        self.assertEqual(int(result["remaining_connect_entitlements"]), 0)
        self.assertEqual(int(result["remaining_device_entitlements"]), 0)

        after = p.list_licences_for_admin()
        self.assertEqual(after, [], msg=f"expected empty licence table, got {after!r}")

        from admin_panel import render_admin_licences_section_html

        html = render_admin_licences_section_html()
        self.assertIn("No licences yet", html)
        self.assertIn("admin-clear-licences-form", html)
        self.assertIn("CLEAR_ALL_LICENCES", html)

    def test_admin_route_wires_clear_handler(self) -> None:
        root = Path(__file__).resolve().parents[1]
        app = (root / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/admin/clear-licences", app)
        self.assertIn("clear_all_licences_for_admin", app)
        pay = (root / "status_page" / "payments.py").read_text(encoding="utf-8")
        self.assertIn("def clear_all_licences_for_admin", pay)
        self.assertIn("DELETE FROM connect_entitlements", pay)
        self.assertIn("DELETE FROM device_entitlements", pay)


if __name__ == "__main__":
    unittest.main()
