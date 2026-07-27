"""Admin one-month free tester mint: download + keygen, grants/licence filters.

Drives shipped status_page.payments + admin_panel + app paths (no re-implemented
oracles). Temp payment DB only.
"""

from __future__ import annotations

import io
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


class _TempPaymentDB(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        import payments

        self.pay = payments
        self.pay.init_db()

    def tearDown(self):
        self._td.cleanup()
        os.environ.pop("RPT_PAYMENT_DATA_DIR", None)


class TestAdminMintOneMonthTester(_TempPaymentDB):
    def test_mint_payload_keygen_download_ppi_and_month_expiry(self):
        t0 = 1_700_000_000.0
        platforms = ("windows", "linux", "macos", "android")
        for plat in platforms:
            with self.subTest(platform=plat):
                out = self.pay.admin_mint_one_month_tester(
                    plat,
                    now=t0,
                    base_url="https://restoreprivacy.online",
                )
                self.assertTrue(out.get("admin_tester_month"))
                self.assertEqual(out["platform"], plat)
                self.assertEqual(out["ppi"], self.pay.TESTER_MONTH_PPI)
                self.assertEqual(out["purchase_id"], self.pay.TESTER_MONTH_PPI)
                self.assertEqual(out["ppi"], "TESTER - one month")
                kg = out["keygen"]
                self.assertTrue(str(kg).startswith(self.pay.KEYGEN_PREFIX))
                self.assertTrue(out["download_path"].startswith("/download?token="))
                self.assertTrue(
                    out["download_url"].startswith(
                        "https://restoreprivacy.online/download?token="
                    )
                )
                self.assertNotIn("github.com", out["download_url"].lower())
                self.assertNotIn("releases/download", out["download_url"].lower())
                expected_vu = self.pay.period_end_for_billing_interval(
                    t0, self.pay.BILLING_INTERVAL_MONTH
                )
                self.assertAlmostEqual(float(out["valid_until"]), expected_vu, places=0)
                # Connect allowed before expiry
                ent = self.pay.get_connect_entitlement(out["session_id"], now=t0 + 60)
                self.assertIsNotNone(ent)
                self.assertTrue(ent.get("connect_allowed"))
                # Denied after period end
                after = expected_vu + 120.0
                ent2 = self.pay.get_connect_entitlement(out["session_id"], now=after)
                self.assertIsNotNone(ent2)
                self.assertFalse(ent2.get("connect_allowed"))
                self.assertTrue(
                    str(out["session_id"]).startswith(
                        self.pay.TESTER_MONTH_SESSION_PREFIX
                    )
                )

    def test_unknown_platform_fails_closed(self):
        with self.assertRaises(ValueError):
            self.pay.admin_mint_one_month_tester("commodore64")

    def test_paid_grants_list_excludes_tester(self):
        # Paid-like grant via normal mint
        paid = self.pay.admin_mint_download_for_platform(
            "windows", base_url="https://restoreprivacy.online"
        )
        tester = self.pay.admin_mint_one_month_tester(
            "linux", base_url="https://restoreprivacy.online"
        )
        grants = self.pay.list_all_grants()
        sessions = {str(g.get("session_id") or "") for g in grants}
        tokens = {str(g.get("token") or "") for g in grants}
        self.assertIn(paid["session_id"], sessions)
        self.assertIn(paid["token"], tokens)
        self.assertNotIn(tester["session_id"], sessions)
        self.assertNotIn(tester["token"], tokens)
        for g in grants:
            self.assertFalse(self.pay.is_tester_month_grant(g))
            self.assertNotEqual(g.get("purchase_id"), self.pay.TESTER_MONTH_PPI)
        # Token still redeemable (fulfilment path)
        looked = self.pay.lookup_download_token(tester["token"])
        self.assertIsNotNone(looked)
        self.assertEqual(looked and looked.get("platform"), "linux")

    def test_licence_list_only_after_keygen_activation(self):
        # Use wall clock so list_licences_for_admin (time.time()) sees unexpired
        t0 = time.time()
        out = self.pay.admin_mint_one_month_tester(
            "windows",
            now=t0,
            base_url="https://restoreprivacy.online",
        )
        kg = out["keygen"]
        sid = out["session_id"]
        # Before activation: not in licence database
        before = self.pay.list_licences_for_admin()
        sids_before = {str(r.get("session_id") or "") for r in before}
        self.assertNotIn(sid, sids_before)
        kgs_before = {str(r.get("keygen") or "") for r in before}
        self.assertNotIn(kg, kgs_before)
        # Client activation path (same as /api/connect-entitlement?keygen=)
        ent = self.pay.get_connect_entitlement_by_keygen(kg, now=t0 + 10)
        self.assertIsNotNone(ent)
        self.assertTrue(ent.get("connect_allowed"))
        after = self.pay.list_licences_for_admin()
        match = [r for r in after if r.get("session_id") == sid]
        self.assertEqual(len(match), 1, after)
        row = match[0]
        self.assertEqual(row["keygen"], kg)
        self.assertEqual(row["ppi"], "TESTER - one month")
        self.assertEqual(row["purchase_id"], self.pay.TESTER_MONTH_PPI)
        self.assertEqual(row["platform"], "windows")
        self.assertEqual(row["licence_status"], "OK")
        self.assertIsNotNone(row.get("keygen_activated_at"))

    def test_project_grants_for_admin_excludes_tester(self):
        from admin_panel import project_grants_for_admin

        self.pay.admin_mint_one_month_tester(
            "macos", base_url="https://restoreprivacy.online"
        )
        paid = self.pay.admin_mint_download_for_platform(
            "ios", base_url="https://restoreprivacy.online"
        )
        rows = project_grants_for_admin()
        sids = {str(r.get("session_id") or "") for r in rows}
        self.assertIn(paid["session_id"], sids)
        self.assertFalse(any(self.pay.is_tester_month_session(s) for s in sids))


class TestAdminTesterMonthHtml(_TempPaymentDB):
    def test_admin_html_has_tester_section_and_platforms(self):
        from admin_panel import render_admin_html

        page = render_admin_html().decode("utf-8")
        self.assertIn('id="admin-tester-month"', page)
        self.assertIn('id="admin-tester-month-form"', page)
        self.assertIn('action="/admin/mint-tester-month"', page)
        self.assertIn('id="tester_month_platform"', page)
        self.assertIn("admin-tester-month-submit", page)
        self.assertIn("TESTER - one month", page)
        for p in ("windows", "linux", "macos", "ios", "android"):
            self.assertIn(f'value="{p}"', page)

    def test_tester_section_immediately_below_keygen_failsafe(self):
        """Product placement: one-month tester sits just under Generate KEYGEN failsafe."""
        from admin_panel import render_admin_html

        page = render_admin_html().decode("utf-8")
        ik = page.find('id="admin-keygen-failsafe"')
        it = page.find('id="admin-tester-month"')
        self.assertGreaterEqual(ik, 0, "keygen failsafe section missing")
        self.assertGreaterEqual(it, 0, "tester month section missing")
        self.assertLess(
            ik,
            it,
            "tester must render after Generate KEYGEN (admin failsafe)",
        )
        # No intervening mint cards between the two sections
        between = page[ik:it]
        self.assertNotIn('id="admin-ondemand-mint"', between)
        self.assertNotIn('id="admin-reissue"', between)
        self.assertNotIn('id="admin-seed-purchase"', between)
        self.assertNotIn('id="admin-grants"', between)
        self.assertNotIn('id="admin-licences"', between)
        # Nav link present next to keygen failsafe
        self.assertIn('href="#admin-tester-month"', page)
        nav_k = page.find('href="#admin-keygen-failsafe"')
        nav_t = page.find('href="#admin-tester-month"')
        self.assertGreaterEqual(nav_k, 0)
        self.assertGreater(nav_t, nav_k)

    def test_success_render_shows_download_keygen_ppi(self):
        from admin_panel import render_admin_tester_month_section_html

        minted = self.pay.admin_mint_one_month_tester(
            "windows", base_url="https://restoreprivacy.online"
        )
        html = render_admin_tester_month_section_html(
            result=minted, platform="windows"
        )
        self.assertIn('id="tester-month-result"', html)
        self.assertIn('id="tester-month-keygen"', html)
        self.assertIn(minted["keygen"], html)
        self.assertIn('id="tester-month-download-link"', html)
        self.assertIn(minted["download_url"], html)
        self.assertIn('id="tester-month-ppi"', html)
        self.assertIn("TESTER - one month", html)

    def test_post_requires_auth(self):
        import app as status_app

        body = b"platform=windows"

        class FakeHandler(status_app.Handler):
            def __init__(self):
                self.headers = {"Content-Length": str(len(body))}
                self.rfile = io.BytesIO(body)
                self.wfile = io.BytesIO()
                self.path = "/admin/mint-tester-month"
                self.command = "POST"
                self.request_version = "HTTP/1.1"
                self.client_address = ("127.0.0.1", 0)
                self._code = None

            def send_response(self, code, message=None):
                self._code = code

            def send_header(self, *a):
                return

            def end_headers(self):
                return

            def log_message(self, *a):
                return

        with mock.patch.object(status_app, "admin_enabled", return_value=True):
            with mock.patch.object(status_app, "is_authenticated", return_value=False):
                h = FakeHandler()
                h.do_POST()
        out = h.wfile.getvalue().decode("utf-8", errors="replace")
        self.assertIn("admin-login-form", out)
        self.assertNotIn("tester-month-download-link", out)

    def test_post_mints_when_authenticated(self):
        from admin_panel import mint_session_token, SESSION_COOKIE
        import app as status_app

        body = b"platform=android"
        session = mint_session_token()

        class FakeHandler(status_app.Handler):
            def __init__(self):
                self.headers = {
                    "Content-Length": str(len(body)),
                    "Cookie": f"{SESSION_COOKIE}={session}",
                }
                self.rfile = io.BytesIO(body)
                self.wfile = io.BytesIO()
                self.path = "/admin/mint-tester-month"
                self.command = "POST"
                self.request_version = "HTTP/1.1"
                self.client_address = ("127.0.0.1", 0)
                self._code = None

            def send_response(self, code, message=None):
                self._code = code

            def send_header(self, *a):
                return

            def end_headers(self):
                return

            def log_message(self, *a):
                return

        with mock.patch.object(status_app, "admin_enabled", return_value=True):
            with mock.patch.object(status_app, "is_authenticated", return_value=True):
                h = FakeHandler()
                h.do_POST()
        out = h.wfile.getvalue().decode("utf-8", errors="replace")
        self.assertEqual(h._code, 200)
        self.assertIn("tester-month-download-link", out)
        self.assertIn("tester-month-keygen", out)
        self.assertIn("TESTER - one month", out)
        self.assertIn("android", out.lower())


if __name__ == "__main__":
    unittest.main()
