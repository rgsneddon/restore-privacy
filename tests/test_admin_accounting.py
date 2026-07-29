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

    def test_reissue_same_purchase_id_counts_once(self) -> None:
        """Two download tokens for one purchase_id = one ledger sale (not N)."""
        from datetime import datetime, timezone

        from accounting import (
            OPENING_BALANCE_PENCE,
            build_ledger,
            estimate_stripe_fee_pence,
            sales_from_grants,
        )
        import payments

        payments.init_db()
        t0 = datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc).timestamp()
        t1 = datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc).timestamp()
        pid = "RPT-AAAA-REISSUE-TEST"
        # Original paid grant
        payments.mint_download_token(
            filename="restore-privacy-client-0.5.2-windows-x64-setup.exe",
            platform="windows",
            session_id="cs_live_reissue_parent",
            amount_pence=245,
            currency="gbp",
            now=t0,
            purchase_id=pid,
        )
        # Reissue: second token, same purchase_id + session (real reissue path)
        payments.mint_download_token(
            filename="restore-privacy-client-0.5.2-windows-x64-setup.exe",
            platform="windows",
            session_id="cs_live_reissue_parent",
            amount_pence=245,
            currency="gbp",
            now=t1,
            purchase_id=pid,
        )
        grants = payments.list_all_grants()
        matching = [
            g
            for g in grants
            if str(g.get("purchase_id") or "") == pid
            or str(g.get("session_id") or "") == "cs_live_reissue_parent"
        ]
        self.assertGreaterEqual(len(matching), 2, "fixture must seed two grants")
        sales = sales_from_grants(grants)
        sale_rows = [s for s in sales if s.get("purchase_id") == pid]
        self.assertEqual(
            len(sale_rows),
            1,
            f"expected one sale for reissued purchase, got {sale_rows!r}",
        )
        rows = build_ledger(grants=grants)
        sales_in_ledger = [r for r in rows if r.kind == "sale" and r.purchase_id == pid]
        self.assertEqual(len(sales_in_ledger), 1)
        fee = estimate_stripe_fee_pence(245)
        expected_bal = OPENING_BALANCE_PENCE + (245 - fee)
        self.assertEqual(rows[-1].balance_pence, expected_bal)
        # Not double-counted: −6000 + 2*221 would be −5558 path; one sale is −6000+221
        self.assertNotEqual(
            rows[-1].balance_pence,
            OPENING_BALANCE_PENCE + 2 * (245 - fee),
        )

    def test_admin_ondemand_and_resend_not_sales(self) -> None:
        """Operator recovery mints must not appear as customer revenue."""
        from datetime import datetime, timezone

        from accounting import build_ledger, sales_from_grants
        import payments

        payments.init_db()
        ts = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc).timestamp()
        for sid in (
            "admin_ondemand_deadbeef01",
            "admin_resend_cafebabe02",
            "admin_keygen_ignored03",
        ):
            payments.mint_download_token(
                filename="restore-privacy-client-0.5.2-windows-x64-setup.exe",
                platform="windows",
                session_id=sid,
                amount_pence=245,
                currency="gbp",
                now=ts,
            )
        # One real Checkout-shaped session for control
        payments.mint_download_token(
            filename="restore-privacy-client-0.5.2-android.apk",
            platform="android",
            session_id="cs_live_real_checkout_only",
            amount_pence=245,
            currency="gbp",
            now=ts,
            purchase_id="RPT-REAL-ONLY-0001",
        )
        grants = payments.list_all_grants()
        sales = sales_from_grants(grants)
        sids = {s.get("session_id") for s in sales}
        self.assertNotIn("admin_ondemand_deadbeef01", sids)
        self.assertNotIn("admin_resend_cafebabe02", sids)
        self.assertNotIn("admin_keygen_ignored03", sids)
        self.assertIn("cs_live_real_checkout_only", sids)
        self.assertEqual(len(sales), 1)
        rows = build_ledger(grants=grants)
        self.assertEqual(sum(1 for r in rows if r.kind == "sale"), 1)
        self.assertEqual(rows[-1].session_id, "cs_live_real_checkout_only")


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
        # CSV contains setup costs, Fees header, END BALANCE
        csv_b, _, _ = export_ledger(rows, fmt="csv")
        text = csv_b.decode("utf-8")
        self.assertIn("SET UP COSTS", text)
        self.assertIn("RASKUL" if False else "Paid sale", text)
        self.assertIn("Fees", text.splitlines()[0])
        self.assertIn("END BALANCE", text.splitlines()[0])
        self.assertNotIn("Stripe fee", text.splitlines()[0])
        self.assertIn("-£", text.replace("\ufeff", ""))  # fee or balance negative
        self.assertEqual(rows[0].balance_pence, OPENING_BALANCE_PENCE)


class TestAccountingAdminWiring(unittest.TestCase):
    def test_routes_and_nav_and_render(self) -> None:
        app = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/admin/accounting", app)
        self.assertIn("/admin/accounting/export", app)
        self.assertIn("/admin/accounting/manual-entry", app)
        self.assertIn("/admin/accounting/delete", app)
        self.assertIn("add_manual_entry", app)
        self.assertIn("delete_ledger_row", app)
        self.assertIn("render_admin_accounting_page_html", app)
        self.assertIn("export_ledger", app)
        panel = (ROOT / "status_page" / "admin_panel.py").read_text(encoding="utf-8")
        self.assertIn("admin-nav-accounting", panel)
        self.assertIn("RASKUL LTD", panel)
        self.assertIn("admin-accounting-export", panel)
        self.assertIn("admin-accounting-manual-entry", panel)
        self.assertIn('action="/admin/accounting/manual-entry"', panel)
        self.assertIn('action="/admin/accounting/delete"', panel)
        self.assertIn("Delete row", panel)
        self.assertIn("SET UP COSTS", panel)
        acct = (ROOT / "status_page" / "accounting.py").read_text(encoding="utf-8")
        self.assertIn("1.5%", acct)
        self.assertIn("OPENING_BALANCE_PENCE = -600_000", acct)
        self.assertIn("def add_manual_entry", acct)
        self.assertIn("def delete_ledger_row", acct)

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
        self.assertIn("admin-accounting-manual-entry-form", html)
        self.assertIn('id="export-format"', html)
        self.assertIn("xlsx", html)
        self.assertIn("pdf", html)
        self.assertIn("rtf", html)
        self.assertIn("−£6,000.00", html.replace("-£6,000.00", "−£6,000.00") or html)
        # END BALANCE column + summary
        self.assertIn("admin-accounting-balance-value", html)
        self.assertIn("END BALANCE", html)
        self.assertIn("admin-accounting-end-balance-col", html)
        self.assertIn("Current END BALANCE", html)
        # Fees (not Stripe fee) on table + manual form
        self.assertIn(">Fees</th>", html)
        self.assertNotIn("Stripe fee", html)
        self.assertNotIn('id="manual_net"', html)
        self.assertNotIn('name="net"', html)
        self.assertIn('name="gross_sign"', html)
        self.assertIn('id="manual_gross_sign"', html)
        # Manual entry between export and table
        exp_i = html.find("admin-accounting-export")
        man_i = html.find("admin-accounting-manual-entry")
        tbl_i = html.find("admin-accounting-table")
        self.assertGreater(man_i, exp_i)
        self.assertGreater(tbl_i, man_i)
        self.assertIn("btn-delete-row", html)
        self.assertIn('name="row_id"', html)
        self.assertIn('value="setup"', html)
        # END BALANCE header is last money col before Actions
        thead = html[html.find("<thead>") : html.find("</thead>")]
        end_i = thead.find("END BALANCE")
        act_i = thead.find("Actions")
        self.assertGreater(end_i, 0)
        self.assertGreater(act_i, end_i)
        self.assertNotIn("<th>Balance</th>", thead)


class TestManualEntryAndDelete(unittest.TestCase):
    """Drive shipped add/delete helpers used by admin POST routes."""

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

    def test_parse_money_and_add_updates_balance(self) -> None:
        from accounting import (
            OPENING_BALANCE_PENCE,
            add_manual_entry,
            build_ledger,
            build_ledger_from_payment_store,
            compute_net_pence,
            parse_money_to_pence,
            resolve_manual_gross_pence,
        )
        import payments

        payments.init_db()
        self.assertEqual(parse_money_to_pence("12.34"), 1234)
        self.assertEqual(parse_money_to_pence("-0.24"), -24)
        self.assertEqual(parse_money_to_pence("£1.50"), 150)
        self.assertEqual(resolve_manual_gross_pence("0.01", sign="+"), 1)
        self.assertEqual(resolve_manual_gross_pence("0.01", sign="-"), -1)
        self.assertEqual(resolve_manual_gross_pence("-0.01", sign="+"), -1)
        self.assertEqual(compute_net_pence(1, 0), 1)
        self.assertEqual(compute_net_pence(1000, 35), 1000 - 35)

        prior = build_ledger(sales=[], include_manual_store=True)
        self.assertEqual(len(prior), 1)
        prior_bal = prior[-1].balance_pence
        self.assertEqual(prior_bal, OPENING_BALANCE_PENCE)

        # Same shape as form POST: pounds strings → pence; net always gross ± fees
        gross = resolve_manual_gross_pence("10.00", sign="+")
        fee = parse_money_to_pence("0.35")  # positive; add_manual_entry negates
        added = add_manual_entry(
            date_iso="2026-08-10",
            description="Bank adjustment",
            gross_pence=gross,
            fee_pence=fee,
            net_pence=999999,  # must be ignored
            purchase_id="MANUAL-1",
            platform="n/a",
        )
        self.assertTrue(str(added["id"]).startswith("manual:"))
        self.assertEqual(added["fee_pence"], -35)
        self.assertEqual(added["net_pence"], 1000 - 35)

        rows = build_ledger_from_payment_store()
        manuals = [r for r in rows if r.kind == "manual"]
        self.assertEqual(len(manuals), 1)
        self.assertEqual(manuals[0].description, "Bank adjustment")
        self.assertEqual(manuals[0].row_id, added["id"])
        self.assertEqual(
            rows[-1].balance_pence,
            prior_bal + added["net_pence"],
        )
        # Running END BALANCE consistent
        bal = 0
        for r in rows:
            bal += r.net_pence
            self.assertEqual(r.balance_pence, bal)

    def test_penny_plus_and_minus_update_end_balance(self) -> None:
        """£0.01 + and − must change END BALANCE (the reported live bug)."""
        from accounting import (
            OPENING_BALANCE_PENCE,
            add_manual_entry,
            build_ledger_from_payment_store,
            resolve_manual_gross_pence,
        )
        import payments

        payments.init_db()
        prior = build_ledger_from_payment_store()[-1].balance_pence
        self.assertEqual(prior, OPENING_BALANCE_PENCE)

        g_plus = resolve_manual_gross_pence("0.01", sign="+")
        add_manual_entry(
            date_iso="2026-08-02",
            description="Penny credit",
            gross_pence=g_plus,
            fee_pence=0,
            now=1.0,
        )
        after_plus = build_ledger_from_payment_store()
        self.assertEqual(after_plus[-1].net_pence, 1)
        self.assertEqual(after_plus[-1].balance_pence, prior + 1)
        self.assertEqual(after_plus[-1].kind, "manual")

        g_minus = resolve_manual_gross_pence("0.01", sign="-")
        add_manual_entry(
            date_iso="2026-08-03",
            description="Penny debit",
            gross_pence=g_minus,
            fee_pence=0,
            now=2.0,
        )
        after_minus = build_ledger_from_payment_store()
        self.assertEqual(after_minus[-1].net_pence, -1)
        self.assertEqual(after_minus[-1].balance_pence, prior + 1 - 1)
        # Most recent last
        self.assertEqual(after_minus[-1].description, "Penny debit")
        self.assertLess(after_minus[-2].date_iso, after_minus[-1].date_iso)

        # HTML path shows END BALANCE value
        from admin_panel import render_admin_accounting_page_html

        html = render_admin_accounting_page_html().decode("utf-8")
        self.assertIn("END BALANCE", html)
        self.assertIn("Penny debit", html)
        self.assertIn("end-balance", html)
        self.assertIn("admin-accounting-end-balance-col", html)

    def test_mixed_order_and_running_end_balance(self) -> None:
        from accounting import (
            OPENING_BALANCE_PENCE,
            add_manual_entry,
            build_ledger,
            compute_net_pence,
            estimate_stripe_fee_pence,
        )
        import payments
        from datetime import datetime, timezone

        payments.init_db()
        ts = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc).timestamp()
        payments.mint_download_token(
            filename="restore-privacy-client-0.5.2-windows-x64-setup.exe",
            platform="windows",
            session_id="cs_live_order_bal_1",
            amount_pence=245,
            currency="gbp",
            now=ts,
        )
        add_manual_entry(
            date_iso="2026-09-01",
            description="Later manual",
            gross_pence=100,
            fee_pence=0,
            now=ts + 100,
        )
        rows = build_ledger(grants=payments.list_all_grants(), include_manual_store=True)
        self.assertEqual(rows[0].kind, "setup")
        self.assertEqual(rows[-1].description, "Later manual")
        self.assertEqual(rows[-1].date_iso, "2026-09-01")
        fee_pos = estimate_stripe_fee_pence(245)
        expected = OPENING_BALANCE_PENCE + compute_net_pence(245, -fee_pos) + 100
        self.assertEqual(rows[-1].balance_pence, expected)
        running = 0
        for r in rows:
            running += r.net_pence
            self.assertEqual(r.balance_pence, running)
        # Sale description names Stripe fee (not the Fees column header)
        sale = next(r for r in rows if r.kind == "sale")
        self.assertIn("Stripe fee", sale.description)

    def test_delete_manual_and_hide_setup_recompute(self) -> None:
        from accounting import (
            OPENING_BALANCE_PENCE,
            add_manual_entry,
            build_ledger,
            build_ledger_from_payment_store,
            delete_ledger_row,
            estimate_stripe_fee_pence,
        )
        import payments
        from datetime import datetime, timezone

        payments.init_db()
        ts = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc).timestamp()
        payments.mint_download_token(
            filename="restore-privacy-client-0.5.2-windows-x64-setup.exe",
            platform="windows",
            session_id="cs_live_manual_del_1",
            amount_pence=245,
            currency="gbp",
            now=ts,
        )
        # Expense: negative gross (net override is ignored)
        added = add_manual_entry(
            date_iso="2026-08-20",
            description="Office supplies",
            gross_pence=-500,
            fee_pence=0,
        )
        full = build_ledger_from_payment_store()
        n_before = len(full)
        self.assertGreaterEqual(n_before, 3)  # setup + sale + manual
        fee_pos = estimate_stripe_fee_pence(245)
        expected = OPENING_BALANCE_PENCE + (245 - fee_pos) + (-500)
        self.assertEqual(full[-1].balance_pence, expected)

        # Delete manual via shipped delete path
        delete_ledger_row(added["id"])
        after_manual = build_ledger_from_payment_store()
        self.assertEqual(len(after_manual), n_before - 1)
        self.assertFalse(any(r.row_id == added["id"] for r in after_manual))
        self.assertEqual(
            after_manual[-1].balance_pence,
            OPENING_BALANCE_PENCE + (245 - fee_pos),
        )

        # Delete setup (hide auto row)
        delete_ledger_row("setup")
        after_setup = build_ledger_from_payment_store()
        self.assertEqual(len(after_setup), len(after_manual) - 1)
        self.assertFalse(any(r.kind == "setup" for r in after_setup))
        bal = 0
        for r in after_setup:
            bal += r.net_pence
            self.assertEqual(r.balance_pence, bal)
        self.assertEqual(after_setup[-1].balance_pence, 245 - fee_pos)

        # Delete sale by row_id
        sale = next(r for r in after_setup if r.kind == "sale")
        delete_ledger_row(sale.row_id)
        emptyish = build_ledger_from_payment_store()
        self.assertEqual(len(emptyish), 0)

    def test_invalid_manual_refuses_without_corrupt(self) -> None:
        from accounting import add_manual_entry, build_ledger, list_manual_entries

        with self.assertRaises(ValueError):
            add_manual_entry(date_iso="not-a-date", description="x")
        with self.assertRaises(ValueError):
            add_manual_entry(date_iso="2026-08-01", description="")
        self.assertEqual(list_manual_entries(), [])
        rows = build_ledger(sales=[], include_manual_store=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].kind, "setup")


if __name__ == "__main__":
    unittest.main()
