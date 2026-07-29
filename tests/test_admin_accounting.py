"""RASKUL LTD admin accounting: ledger, Stripe fees, exports, routes."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestStripeFeeHelper(unittest.TestCase):
    def test_uk_estimate_1_5_pct_plus_20p(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "status_page"))
        from accounting import estimate_stripe_fee_pence, resolve_stripe_fee_pence

        # £2.45 (245p): 1.5% ≈ 3.675 → 4p + 20p = 24p
        self.assertEqual(estimate_stripe_fee_pence(245), 24)
        # £100.00: 150p + 20p = 170p
        self.assertEqual(estimate_stripe_fee_pence(10000), 170)
        fee, src = resolve_stripe_fee_pence(245)
        self.assertEqual(fee, 24)
        self.assertEqual(src, "estimate")
        fee2, src2 = resolve_stripe_fee_pence(245, stored_fee_pence=30)
        self.assertEqual(fee2, 30)
        self.assertEqual(src2, "stored")
        self.assertEqual(estimate_stripe_fee_pence(0), 0)


class TestLedgerBuild(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        import sys

        sys.path.insert(0, str(ROOT / "status_page"))

    def tearDown(self) -> None:
        if self._prev is None:
            os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
        else:
            os.environ["RPT_PAYMENT_DATA_DIR"] = self._prev
        self._td.cleanup()

    def test_setup_costs_and_sale_net_of_fee(self) -> None:
        from accounting import (
            OPENING_BALANCE_PENCE,
            OPENING_DATE,
            build_ledger,
            estimate_stripe_fee_pence,
            sales_from_grants,
        )
        import payments

        payments.init_db()
        # Sale after opening: use a fixed timestamp on 2026-08-15 UTC
        ts = time.mktime(time.strptime("2026-08-15", "%Y-%m-%d"))
        # Prefer absolute UTC
        from datetime import datetime, timezone

        ts = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc).timestamp()
        payments.mint_download_token(
            filename="restore-privacy-client-0.5.2-windows-x64-setup.exe",
            platform="windows",
            session_id="cs_live_accounting_test_1",
            amount_pence=245,
            currency="gbp",
            now=ts,
        )
        grants = payments.list_all_grants()
        sales = sales_from_grants(grants)
        self.assertGreaterEqual(len(sales), 1)
        rows = build_ledger(grants=grants)
        self.assertEqual(rows[0].kind, "setup")
        self.assertEqual(rows[0].date_iso, OPENING_DATE.isoformat())
        self.assertEqual(rows[0].description, "SET UP COSTS")
        self.assertEqual(rows[0].net_pence, OPENING_BALANCE_PENCE)
        self.assertEqual(rows[0].balance_pence, OPENING_BALANCE_PENCE)
        sale = next(r for r in rows if r.kind == "sale")
        fee_pos = estimate_stripe_fee_pence(245)
        self.assertEqual(sale.gross_pence, 245)
        self.assertEqual(sale.fee_pence, -fee_pos)
        self.assertEqual(sale.net_pence, 245 - fee_pos)
        self.assertLess(sale.net_pence, sale.gross_pence)
        self.assertEqual(
            rows[-1].balance_pence,
            OPENING_BALANCE_PENCE + sale.net_pence,
        )

    def test_pre_opening_grants_excluded(self) -> None:
        from accounting import build_ledger, sales_from_grants
        from datetime import datetime, timezone

        import payments

        payments.init_db()
        ts = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc).timestamp()
        payments.mint_download_token(
            filename="restore-privacy-client-0.5.2-windows-x64-setup.exe",
            platform="windows",
            session_id="cs_live_pre_opening",
            amount_pence=245,
            currency="gbp",
            now=ts,
        )
        sales = sales_from_grants(payments.list_all_grants())
        self.assertEqual(sales, [])
        rows = build_ledger(grants=payments.list_all_grants())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].kind, "setup")


class TestAccountingExport(unittest.TestCase):
    def test_all_formats_nonempty_and_export_filters(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "status_page"))
        from accounting import (
            OPENING_BALANCE_PENCE,
            build_ledger,
            export_ledger,
            filter_ledger_by_period,
            parse_export_period,
        )

        sales = [
            {
                "date_iso": "2026-08-10",
                "description": "Paid sale windows RPT-AAA",
                "gross_pence": 245,
                "fee_pence": -24,
                "net_pence": 221,
                "fee_source": "estimate",
                "session_id": "cs_1",
                "purchase_id": "RPT-AAA",
                "platform": "windows",
                "currency": "GBP",
                "created_at": 1.0,
            },
            {
                "date_iso": "2026-09-05",
                "description": "Paid sale android RPT-BBB",
                "gross_pence": 2793,
                "fee_pence": -62,
                "net_pence": 2731,
                "fee_source": "estimate",
                "session_id": "cs_2",
                "purchase_id": "RPT-BBB",
                "platform": "android",
                "currency": "GBP",
                "created_at": 2.0,
            },
        ]
        rows = build_ledger(sales=sales)
        for fmt in ("csv", "xlsx", "xls", "pdf", "rtf", "html", "json"):
            body, ctype, ext = export_ledger(rows, fmt=fmt)
            self.assertGreater(len(body), 40, fmt)
            self.assertTrue(ctype)
            self.assertEqual(ext, fmt if fmt != "excel" else "xlsx")
        # Month filter: August only → setup + first sale
        aug = filter_ledger_by_period(rows, year=2026, month=8)
        self.assertEqual(len(aug), 2)
        self.assertEqual(aug[0].kind, "setup")
        self.assertEqual(aug[1].purchase_id, "RPT-AAA")
        # Range Aug–Sep
        rng = filter_ledger_by_period(
            rows, from_year=2026, from_month=8, to_year=2026, to_month=9
        )
        self.assertEqual(len(rng), 3)
        period = parse_export_period(
            {"period_mode": "month", "year": "2026", "month": "8"}
        )
        self.assertEqual(period["filter"]["month"], 8)
        self.assertIn("2026-08", period["stem"])
        period2 = parse_export_period(
            {
                "period_mode": "range",
                "from_year": "2026",
                "from_month": "8",
                "to_year": "2026",
                "to_month": "12",
            }
        )
        self.assertEqual(period2["filter"]["to_month"], 12)
        # CSV contains setup costs and fee minus
        csv_b, _, _ = export_ledger(rows, fmt="csv")
        text = csv_b.decode("utf-8")
        self.assertIn("SET UP COSTS", text)
        self.assertIn("RASKUL" if False else "Paid sale", text)
        self.assertIn("-£", text.replace("\ufeff", ""))  # fee or balance negative
        self.assertEqual(rows[0].balance_pence, OPENING_BALANCE_PENCE)


class TestAccountingAdminWiring(unittest.TestCase):
    def test_routes_and_nav_and_render(self) -> None:
        app = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/admin/accounting", app)
        self.assertIn("/admin/accounting/export", app)
        self.assertIn("render_admin_accounting_page_html", app)
        self.assertIn("export_ledger", app)
        panel = (ROOT / "status_page" / "admin_panel.py").read_text(encoding="utf-8")
        self.assertIn("admin-nav-accounting", panel)
        self.assertIn("RASKUL LTD", panel)
        self.assertIn("admin-accounting-export", panel)
        self.assertIn("SET UP COSTS", panel)
        acct = (ROOT / "status_page" / "accounting.py").read_text(encoding="utf-8")
        self.assertIn("1.5%", acct)
        self.assertIn("OPENING_BALANCE_PENCE = -600_000", acct)

        import sys

        sys.path.insert(0, str(ROOT / "status_page"))
        os.environ.setdefault("RPT_PAYMENT_DATA_DIR", tempfile.mkdtemp())
        from admin_panel import render_admin_accounting_page_html
        from accounting import build_ledger

        html = render_admin_accounting_page_html(
            rows=build_ledger(sales=[])
        ).decode("utf-8")
        self.assertIn("RASKUL LTD", html)
        self.assertIn("SET UP COSTS", html)
        self.assertIn("admin-accounting-export-form", html)
        self.assertIn('id="export-format"', html)
        self.assertIn("xlsx", html)
        self.assertIn("pdf", html)
        self.assertIn("rtf", html)
        self.assertIn("−£6,000.00", html.replace("-£6,000.00", "−£6,000.00") or html)
        # balance shown
        self.assertIn("admin-accounting-balance-value", html)


if __name__ == "__main__":
    unittest.main()
