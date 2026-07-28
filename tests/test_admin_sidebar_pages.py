"""Admin multi-page shell: sidebar, architecture home, link gen, licences dates."""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestAdminSidebarPages(unittest.TestCase):
    def test_home_has_sidebar_architecture_only(self):
        from admin_panel import render_admin_home_html, ADMIN_ARCHITECTURE_BLURB

        page = render_admin_home_html().decode("utf-8")
        self.assertIn('id="admin-sidebar"', page)
        self.assertIn("Link Generation", page)
        self.assertIn("Active Licences", page)
        self.assertIn('id="admin-architecture"', page)
        self.assertIn('id="admin-architecture-full"', page)
        self.assertIn(ADMIN_ARCHITECTURE_BLURB.split(";")[0][:40], page)
        # Mint stack not on home
        self.assertNotIn('id="admin-tester-month"', page)
        self.assertNotIn('id="admin-reissue"', page)
        self.assertNotIn('id="admin-grants-table"', page)
        self.assertIn('class="sb-btn', page)

    def test_link_generation_has_four_tools(self):
        from admin_panel import render_admin_link_generation_html

        page = render_admin_link_generation_html().decode("utf-8")
        self.assertIn('id="admin-reissue"', page)
        self.assertIn('id="admin-ondemand-mint"', page)
        self.assertIn('id="admin-keygen-failsafe"', page)
        self.assertIn('id="admin-tester-month"', page)
        self.assertIn("/admin/mint-download", page)
        self.assertIn("/admin/mint-keygen", page)
        self.assertIn("/admin/mint-tester-month", page)
        self.assertIn("/admin/reissue-download", page)

    def test_licences_page_has_dates_columns(self):
        from admin_panel import render_admin_licences_page_html

        page = render_admin_licences_page_html().decode("utf-8")
        self.assertIn('id="admin-licences"', page)
        self.assertIn('id="admin-grants"', page)
        self.assertIn("Initiated", page)
        self.assertIn("Expiry", page)
        self.assertIn('id="admin-licences-table"', page)
        self.assertIn('id="admin-grants-table"', page)
        # Column headers present even when empty
        self.assertIn("<th>Initiated</th>", page)
        self.assertIn("<th>Expiry</th>", page)


class TestLicenceGrantEndedDates(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(
            os.environ, {"RPT_PAYMENT_DATA_DIR": self._td.name}, clear=False
        )
        self.env.start()
        import payments as pay

        pay.init_db()
        self.pay = pay
        self.now = 1_705_320_000.0

    def tearDown(self):
        self.env.stop()
        self._td.cleanup()

    def test_expired_licence_listed_as_ended_with_dates(self):
        pay = self.pay
        pe = self.now + 100
        pay.activate_connect_entitlement(
            "cs_ended_1",
            platform="windows",
            valid_until=pe,
            billing_interval="month",
            now=self.now,
        )
        after = pe + 50
        # Force list_licences to use wall clock — patch time.time
        with mock.patch.object(pay.time, "time", return_value=after):
            rows = pay.list_licences_for_admin()
        match = [r for r in rows if r.get("session_id") == "cs_ended_1"]
        self.assertEqual(len(match), 1, rows)
        row = match[0]
        self.assertEqual(row["licence_status"], "ENDED")
        self.assertTrue(row.get("initiated_date"))
        self.assertTrue(row.get("expiry_date"))
        self.assertEqual(
            row["initiated_date"],
            pay.format_admin_unix_date(self.now),
        )
        self.assertEqual(row["expiry_date"], pay.format_admin_unix_date(pe))

    def test_active_licence_ok(self):
        pay = self.pay
        pe = self.now + 30 * 86400
        pay.activate_connect_entitlement(
            "cs_ok_1",
            platform="linux",
            valid_until=pe,
            billing_interval="month",
            now=self.now,
        )
        with mock.patch.object(pay.time, "time", return_value=self.now + 10):
            rows = pay.list_licences_for_admin()
        match = [r for r in rows if r.get("session_id") == "cs_ok_1"]
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0]["licence_status"], "OK")

    def test_grant_ended_when_entitlement_expired(self):
        pay = self.pay
        pe = self.now + 50
        pay.activate_connect_entitlement(
            "cs_g_end",
            platform="android",
            valid_until=pe,
            billing_interval="month",
            now=self.now,
        )
        tok = pay.mint_download_token(
            filename=pay.platform_filename("android") or "x.apk",
            platform="android",
            session_id="cs_g_end",
            amount_pence=pay.PRICE_PENCE,
            now=self.now,
        )
        self.assertTrue(tok)
        with mock.patch.object(pay.time, "time", return_value=pe + 100):
            grants = pay.list_all_grants()
        match = [g for g in grants if g.get("session_id") == "cs_g_end"]
        self.assertEqual(len(match), 1, grants)
        self.assertEqual(match[0]["status"], "ENDED")
        self.assertTrue(match[0].get("initiated_date"))
        self.assertTrue(match[0].get("expiry_date"))


if __name__ == "__main__":
    unittest.main()
