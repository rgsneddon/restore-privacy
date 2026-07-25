"""Licence + paid grants admin store survives residual wipe; admin copy is current."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestPaymentStoreWipeProtection(unittest.TestCase):
    def test_plan_wipe_never_targets_payment_db(self):
        from node.disk_encryption import (
            is_payment_store_wipe_protected,
            is_safe_wipe_path,
            plan_wipe,
        )
        from payments import payment_store_survives_residual_wipe

        for aggressive in (False, True):
            plan = plan_wipe(
                install_root="/opt/restore-privacy",
                aggressive_secrets=aggressive,
            )
            for t in plan["targets"]:
                self.assertFalse(
                    is_payment_store_wipe_protected(
                        t, install_root="/opt/restore-privacy"
                    ),
                    f"wipe plan must not target payment store: {t}",
                )
                low = str(t).replace("\\", "/").lower()
                self.assertNotIn("paid_downloads.sqlite3", low)
                self.assertNotIn("status_page/data", low)

        # Explicit candidate must be refused by is_safe_wipe_path
        bad = "/opt/restore-privacy/status_page/data/paid_downloads.sqlite3"
        self.assertFalse(
            is_safe_wipe_path(bad, install_root="/opt/restore-privacy")
        )
        self.assertTrue(
            is_payment_store_wipe_protected(
                bad, install_root="/opt/restore-privacy"
            )
        )
        self.assertTrue(payment_store_survives_residual_wipe())

    def test_wipe_targets_exclude_helper(self):
        from payments import wipe_targets_exclude_payment_store

        raw = [
            "/opt/restore-privacy/run/rpt-node.ready",
            "/opt/restore-privacy/status_page/data/paid_downloads.sqlite3",
            "/tmp/rpt-node.tmp",
            "/opt/restore-privacy/status_page/data",
        ]
        kept = wipe_targets_exclude_payment_store(
            raw, install_root="/opt/restore-privacy"
        )
        self.assertEqual(
            kept,
            [
                "/opt/restore-privacy/run/rpt-node.ready",
                "/tmp/rpt-node.tmp",
            ],
        )

    def test_seeded_licence_and_grants_survive_wipe_adjacent_cleanup(self):
        """Shipped list helpers still return rows after residual wipe plan runs
        against a temp install tree (payment dir is separate and protected).
        """
        import payments
        from node.disk_encryption import plan_wipe

        with tempfile.TemporaryDirectory() as pay_td, tempfile.TemporaryDirectory() as install_td:
            pay = Path(pay_td)
            install = Path(install_td)
            # Residual-looking tree that must not hold the only copy of grants
            (install / "status_page" / "data").mkdir(parents=True)
            decoy = install / "status_page" / "data" / "paid_downloads.sqlite3"
            decoy.write_bytes(b"not-the-admin-db")
            # Durable payment store (status host)
            prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
            os.environ["RPT_PAYMENT_DATA_DIR"] = str(pay)
            try:
                payments.init_db()
                # Seed via shipped store APIs where possible
                conn = payments._connect()
                try:
                    conn.execute(
                        """
                        INSERT INTO grants (
                          token, filename, platform, session_id, amount_pence,
                          currency, created_at, expires_at, used_at, status, purchase_id
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            "tok-wipe-test-1",
                            "restore-privacy-client-0.4.5-windows-x64-setup.exe",
                            "windows",
                            "cs_wipe_test_1",
                            245,
                            "gbp",
                            1_700_000_000.0,
                            1_800_000_000.0,
                            None,
                            "granted",
                            "RPT-WIPE-TEST-0001",
                        ),
                    )
                finally:
                    conn.close()
                # Real entitlement writer (adds keygen / email columns via migrations)
                payments.activate_connect_entitlement(
                    session_id="cs_wipe_test_1",
                    platform="windows",
                    valid_until=1_900_000_000.0,
                    customer_email="wipe-test@example.com",
                    billing_interval="month",
                    keygen="RPT-KEY-WIPE-TEST-AAAA",
                )

                grants_before = payments.list_all_grants()
                lic_before = payments.list_licences_for_admin()
                self.assertTrue(any(g.get("token") == "tok-wipe-test-1" for g in grants_before))
                self.assertTrue(
                    any(
                        (r.get("email") or "") == "wipe-test@example.com"
                        for r in lic_before
                    )
                )

                # Apply residual wipe plan: only runtime targets (not payment dir)
                plan = plan_wipe(
                    install_root=str(install).replace("\\", "/"),
                    aggressive_secrets=True,
                )
                for t in plan["targets"]:
                    p = Path(t)
                    if p.is_file() or p.is_symlink():
                        p.unlink(missing_ok=True)
                    elif p.is_dir():
                        # should not include status_page/data
                        self.fail(f"unexpected dir wipe target: {t}")

                # Payment store untouched
                grants_after = payments.list_all_grants()
                lic_after = payments.list_licences_for_admin()
                self.assertTrue(
                    any(g.get("token") == "tok-wipe-test-1" for g in grants_after)
                )
                self.assertTrue(
                    any(
                        (r.get("email") or "") == "wipe-test@example.com"
                        for r in lic_after
                    )
                )
                # Admin HTML still lists them
                import admin_panel

                html = admin_panel.render_admin_html().decode("utf-8")
                self.assertIn("tok-wipe-test", html)
                self.assertIn("wipe-test@example.com", html)
                self.assertIn("admin-licences", html)
                self.assertIn("admin-grants", html)
            finally:
                if prev is None:
                    os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
                else:
                    os.environ["RPT_PAYMENT_DATA_DIR"] = prev


class TestAdminArchitectureCopy(unittest.TestCase):
    def test_admin_html_has_current_architecture_markers(self):
        import admin_panel

        with tempfile.TemporaryDirectory() as td:
            prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
            os.environ["RPT_PAYMENT_DATA_DIR"] = td
            try:
                html = admin_panel.render_admin_html(grants=[]).decode("utf-8")
            finally:
                if prev is None:
                    os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
                else:
                    os.environ["RPT_PAYMENT_DATA_DIR"] = prev

        # Current architecture
        for marker in (
            "admin-architecture",
            "Germany",
            "Romania",
            "Iceland",
            "sequential",
            "IS",
            "RO",
            "DE",
            "keygen",
            "Stripe",
            "durable",
            "admin-licences",
            "admin-grants",
            PRICE_SNIPPET_MONTH,
            PRICE_SNIPPET_YEAR,
        ):
            self.assertIn(marker, html, f"missing marker {marker!r}")

        # Honesty: no free permanent installers; multi-peer not Iceland-only
        low = html.lower()
        self.assertIn("no free permanent github", low)
        self.assertNotIn("trial only", low)
        self.assertNotIn("iceland-only residual", low)
        self.assertNotIn("sole entry forever", low)
        self.assertNotIn("exit wipe countdown", low)
        self.assertIn("retained across residual", low)
        self.assertIn(admin_panel.ADMIN_ARCHITECTURE_BLURB.split(";")[0][:40], html)


# Avoid importing PRICE constants at module load if payments side-effects
PRICE_SNIPPET_MONTH = "£2.45"
PRICE_SNIPPET_YEAR = "£27.93"


if __name__ == "__main__":
    unittest.main()
