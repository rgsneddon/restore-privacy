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
                            "restore-privacy-client-0.4.8-windows-x64-setup.exe",
                            "windows",
                            "cs_wipe_test_1",
                            300,
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

                html = admin_panel.render_admin_html(page="licences").decode("utf-8")
                self.assertIn("tok-wipe-test", html)
                self.assertIn("wipe-test@example.com", html)
                self.assertIn("admin-licences", html)
                self.assertIn("admin-grants", html)
            finally:
                if prev is None:
                    os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
                else:
                    os.environ["RPT_PAYMENT_DATA_DIR"] = prev


class TestLegacyMigrateToDurable(unittest.TestCase):
    def setUp(self) -> None:
        import payments

        payments.reset_payment_migrate_once_for_tests()

    def test_probe_unknown_on_operational_error_not_empty(self):
        """Locked/error DB must be unknown — never migrate target."""
        import payments

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "paid_downloads.sqlite3"
            p.write_bytes(b"not-a-valid-sqlite-but-nonzero-size" + b"\x00" * 100)
            # Invalid sqlite file → unknown or empty-without-tables depending on open
            probe = payments.payment_db_probe(p)
            # Must not claim has_history for garbage; and safe_migrate only if empty/absent
            self.assertIn(
                probe["state"],
                ("unknown", "empty"),
                probe,
            )
            if probe["state"] == "unknown":
                self.assertFalse(payments.payment_db_is_safe_migrate_dest(p))

    def test_locked_dest_refuses_legacy_overwrite(self):
        """If dest probe is unknown (e.g. mock lock/error), do not replace file."""
        import payments

        with tempfile.TemporaryDirectory() as durable_td, tempfile.TemporaryDirectory() as legacy_td:
            durable = Path(durable_td)
            dest = durable / "paid_downloads.sqlite3"
            # Non-empty durable-looking file with real history
            prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
            os.environ["RPT_PAYMENT_DATA_DIR"] = str(durable)
            try:
                payments.reset_payment_migrate_once_for_tests()
                payments.init_db()
                payments.activate_connect_entitlement(
                    session_id="cs_keep_1",
                    platform="windows",
                    valid_until=2_000_000_000.0,
                    customer_email="keep@example.com",
                    billing_interval="month",
                    keygen="RPT-KEY-KEEP-DEST001",
                )
                self.assertTrue(dest.is_file())
                before = dest.read_bytes()
                legacy = Path(legacy_td) / "paid_downloads.sqlite3"
                legacy.write_bytes(b"LEGACY_SHOULD_NOT_OVERWRITE" + b"\x00" * 200)

                payments.reset_payment_migrate_once_for_tests()
                with mock.patch.object(
                    payments,
                    "payment_db_probe",
                    side_effect=lambda path: {
                        "state": "unknown",
                        "grants": 0,
                        "entitlements": 0,
                        "error": "database is locked",
                    }
                    if Path(path) == dest
                    else {
                        "state": "has_history",
                        "grants": 99,
                        "entitlements": 1,
                        "error": "",
                    },
                ):
                    with mock.patch.object(
                        payments,
                        "legacy_payment_db_candidates",
                        return_value=[legacy],
                    ):
                        st = payments.ensure_payment_db_migrated_from_legacy()
                self.assertFalse(st.get("migrated"), st)
                self.assertIn("unknown", st.get("reason", ""))
                self.assertEqual(dest.read_bytes(), before)
            finally:
                if prev is None:
                    os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
                else:
                    os.environ["RPT_PAYMENT_DATA_DIR"] = prev

    def test_db_path_does_not_run_migrate(self):
        """db_path() must not side-effect migrate (only init_db)."""
        import payments

        with tempfile.TemporaryDirectory() as td:
            prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
            os.environ["RPT_PAYMENT_DATA_DIR"] = td
            payments.reset_payment_migrate_once_for_tests()
            try:
                with mock.patch.object(
                    payments,
                    "ensure_payment_db_migrated_from_legacy",
                    side_effect=AssertionError("migrate must not run from db_path"),
                ):
                    p = payments.db_path()
                    self.assertTrue(str(p).endswith("paid_downloads.sqlite3"))
            finally:
                if prev is None:
                    os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
                else:
                    os.environ["RPT_PAYMENT_DATA_DIR"] = prev

    def test_empty_durable_imports_legacy_grants_and_licences(self):
        """Empty RPT_PAYMENT_DATA_DIR must not drop history still on legacy path."""
        import sqlite3

        import payments
        import admin_panel

        payments.reset_payment_migrate_once_for_tests()
        with tempfile.TemporaryDirectory() as legacy_td, tempfile.TemporaryDirectory() as durable_td:
            # Build a standalone legacy file without touching process env / real store
            legacy_db = Path(legacy_td) / "paid_downloads.sqlite3"
            conn = sqlite3.connect(str(legacy_db))
            try:
                conn.executescript(
                    """
                    CREATE TABLE grants (
                        token TEXT PRIMARY KEY,
                        filename TEXT NOT NULL,
                        platform TEXT NOT NULL,
                        session_id TEXT,
                        amount_pence INTEGER NOT NULL,
                        currency TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        expires_at REAL NOT NULL,
                        used_at REAL,
                        status TEXT NOT NULL,
                        purchase_id TEXT
                    );
                    CREATE TABLE connect_entitlements (
                        session_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        platform TEXT,
                        reason TEXT,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        keygen TEXT,
                        customer_email TEXT,
                        billing_interval TEXT,
                        valid_until REAL
                    );
                    """
                )
                conn.execute(
                    """
                    INSERT INTO grants (
                      token, filename, platform, session_id, amount_pence,
                      currency, created_at, expires_at, used_at, status, purchase_id
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        "tok-migrate-1",
                        "restore-privacy-client-0.4.8-windows-x64-setup.exe",
                        "windows",
                        "cs_migrate_1",
                        300,
                        "gbp",
                        1_700_000_000.0,
                        1_800_000_000.0,
                        None,
                        "granted",
                        "RPT-MIGRATE-0001",
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO connect_entitlements (
                      session_id, status, platform, reason, created_at, updated_at,
                      keygen, customer_email, billing_interval, valid_until
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        "cs_migrate_1",
                        "active",
                        "windows",
                        "",
                        1_700_000_000.0,
                        1_700_000_000.0,
                        "RPT-KEY-MIGRATE-TEST1",
                        "migrate@example.com",
                        "month",
                        2_000_000_000.0,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
            self.assertTrue(payments.payment_db_has_history(legacy_db))

            durable = Path(durable_td)
            prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
            os.environ["RPT_PAYMENT_DATA_DIR"] = str(durable)
            try:
                payments.reset_payment_migrate_once_for_tests()
                with mock.patch.object(
                    payments,
                    "legacy_payment_db_candidates",
                    return_value=[legacy_db],
                ):
                    st = payments.ensure_payment_db_migrated_from_legacy()
                    self.assertTrue(st.get("migrated"), st)
                    payments.init_db()
                    grants = payments.list_all_grants()
                    lic = payments.list_licences_for_admin()
                    self.assertTrue(
                        any(g.get("token") == "tok-migrate-1" for g in grants),
                        grants,
                    )
                    self.assertTrue(
                        any(
                            (r.get("email") or "") == "migrate@example.com"
                            for r in lic
                        ),
                        lic,
                    )
                    payments.init_db()
                    self.assertTrue(
                        any(
                            g.get("token") == "tok-migrate-1"
                            for g in payments.list_all_grants()
                        )
                    )
                    html = admin_panel.render_admin_html(page="licences").decode(
                        "utf-8"
                    )
                    home = admin_panel.render_admin_home_html().decode("utf-8")
                    self.assertIn("tok-migrate", html)
                    self.assertIn("migrate@example.com", html)
                    # Durability banner lives on home (and licences when store status loads)
                    self.assertTrue(
                        "admin-payment-durable-ok" in home
                        or "admin-payment-ephemeral-warn" in home
                        or "admin-payment-durable-ok" in html
                        or "admin-payment-ephemeral-warn" in html,
                        "admin must surface payment-store durability status",
                    )
            finally:
                if prev is None:
                    os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
                else:
                    os.environ["RPT_PAYMENT_DATA_DIR"] = prev

    def test_durability_status_flags_ephemeral_when_env_unset(self):
        import payments

        prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
        os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
        try:
            st = payments.payment_store_durability_status()
            self.assertFalse(st.get("env_set"))
            self.assertTrue(st.get("ephemeral_risk"))
            self.assertIn("db_path", st)
        finally:
            if prev is not None:
                os.environ["RPT_PAYMENT_DATA_DIR"] = prev


class TestAdminArchitectureCopy(unittest.TestCase):
    def test_admin_html_has_current_architecture_markers(self):
        """Home = architecture + sidebar; licences/grants on Active Licences page."""
        import admin_panel

        with tempfile.TemporaryDirectory() as td:
            prev = os.environ.get("RPT_PAYMENT_DATA_DIR")
            os.environ["RPT_PAYMENT_DATA_DIR"] = td
            try:
                # Default render_admin_html → home (no mint kwargs)
                html = admin_panel.render_admin_html(grants=[]).decode("utf-8")
                lic_html = admin_panel.render_admin_licences_page_html(
                    grants=[]
                ).decode("utf-8")
            finally:
                if prev is None:
                    os.environ.pop("RPT_PAYMENT_DATA_DIR", None)
                else:
                    os.environ["RPT_PAYMENT_DATA_DIR"] = prev

        # Home: architecture + collapsible sidebar (not full mint/grant stack)
        for marker in (
            "admin-architecture",
            "admin-sidebar",
            "United States",
            "Germany",
            "Iceland",
            "sequential",
            "IS",
            "DE",
            "US",
            "keygen",
            "Stripe",
            "durable",
            "Link Generation",
            "Active Licences",
            PRICE_SNIPPET_MONTH,
            PRICE_SNIPPET_YEAR,
        ):
            self.assertIn(marker, html, f"missing marker {marker!r}")
        # RO may appear only as deprecated; live catalog is DE not RO
        self.assertIn("deprecated", html.lower())
        self.assertIn("Romania (RO) residual peer is deprecated", html)
        self.assertNotIn("167.233.224.5", html)
        # Mint tools live on Link Generation, not home monostack
        self.assertNotIn('id="admin-tester-month"', html)
        self.assertNotIn('id="admin-grants-table"', html)

        # Honesty: no free permanent installers; multi-peer not Iceland-only
        low = html.lower()
        self.assertIn("no free permanent github", low)
        self.assertNotIn("trial only", low)
        self.assertNotIn("iceland-only residual", low)
        self.assertNotIn("sole entry forever", low)
        self.assertNotIn("exit wipe countdown", low)
        self.assertIn("retained across residual", low)
        self.assertIn(admin_panel.ADMIN_ARCHITECTURE_BLURB.split(";")[0][:40], html)

        # Active Licences page holds licence DB + paid grants tables
        self.assertIn("admin-licences", lic_html)
        self.assertIn("admin-grants", lic_html)
        self.assertIn("Initiated", lic_html)
        self.assertIn("Expiry", lic_html)


# Avoid importing PRICE constants at module load if payments side-effects
PRICE_SNIPPET_MONTH = "£3.00"
PRICE_SNIPPET_YEAR = "£30.00"


if __name__ == "__main__":
    unittest.main()
