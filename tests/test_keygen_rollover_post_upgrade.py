"""Post-upgrade cold start: durable licence + keygen roll over (no re-verify forced)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestShouldForceKeygenAfterUpgrade(unittest.TestCase):
    def test_version_bump_with_active_keygen_does_not_force(self):
        from client.payment_entitlement import should_force_keygen_after_upgrade

        self.assertFalse(
            should_force_keygen_after_upgrade(
                licence_accepted=True,
                has_keygen=True,
                payment_status="active",
                previous_app_version="0.4.10",
                current_app_version="0.5.7",
            )
        )

    def test_no_keygen_forces(self):
        from client.payment_entitlement import should_force_keygen_after_upgrade

        self.assertTrue(
            should_force_keygen_after_upgrade(
                licence_accepted=True,
                has_keygen=False,
                payment_status="active",
                previous_app_version="0.5.0",
                current_app_version="0.5.7",
            )
        )

    def test_expired_does_not_force_keygen_sheet(self):
        from client.payment_entitlement import should_force_keygen_after_upgrade

        self.assertFalse(
            should_force_keygen_after_upgrade(
                licence_accepted=True,
                has_keygen=True,
                payment_status="revoked",
                previous_app_version="0.5.0",
                current_app_version="0.5.7",
            )
        )


class TestPostUpgradeColdStartDurableStore(unittest.TestCase):
    def test_same_store_new_package_version_still_allows_connect(self):
        """Simulated upgrade: only package monopin string changes; durable files stay."""
        from client.licence_gate import (
            accept_licence,
            has_accepted_licence,
            may_connect,
            needs_keygen_unlock,
        )
        from client.payment_entitlement import (
            STATUS_ACTIVE,
            PaymentEntitlement,
            has_keygen_unlock,
            payment_allows_connect,
            save_payment_entitlement,
            should_force_keygen_after_upgrade,
        )

        with tempfile.TemporaryDirectory() as td:
            lic_path = Path(td) / "licence_acceptance.json"
            ent_path = Path(td) / "payment_entitlement.json"
            accept_licence(path=lic_path)
            save_payment_entitlement(
                PaymentEntitlement(
                    session_id="cs_upgrade_rollover",
                    status=STATUS_ACTIVE,
                    platform="macos",
                    keygen="RPT-KEY-ROLL-OVER-01",
                    reason="test_rollover",
                ),
                path=ent_path,
            )
            # "Old" monopin unlock state
            self.assertTrue(has_accepted_licence(lic_path))
            ent = PaymentEntitlement.from_dict(
                json.loads(ent_path.read_text(encoding="utf-8"))
            )
            self.assertTrue(has_keygen_unlock(ent))
            self.assertTrue(payment_allows_connect(ent, require=True))
            self.assertFalse(
                should_force_keygen_after_upgrade(
                    licence_accepted=True,
                    has_keygen=True,
                    payment_status=ent.status,
                    previous_app_version="0.4.8",
                    current_app_version="0.5.7",
                )
            )
            # Cold start after upgrade: same paths (product data dir), new binary version only
            with mock.patch(
                "client.payment_entitlement.load_payment_entitlement",
                return_value=ent,
            ), mock.patch(
                "client.licence_gate.has_accepted_licence",
                return_value=True,
            ):
                self.assertFalse(needs_keygen_unlock(lic_path))
                self.assertTrue(may_connect(lic_path, refresh_payment=False))

    def test_entitlement_and_licence_not_under_install_tree(self):
        """Durable stores use OS user data dirs — install overwrite must not wipe them."""
        from client.licence_gate import default_licence_path, licence_data_dir
        from client.payment_entitlement import (
            default_entitlement_path,
            entitlement_data_dir,
        )

        lic = str(default_licence_path())
        ent = str(default_entitlement_path())
        # Not next to a typical install prefix (Program Files / Applications)
        for p in (lic, ent):
            low = p.lower()
            self.assertNotIn("program files", low)
            self.assertNotIn("/applications/", low)
            self.assertNotIn("restore-privacy/client", low)
        self.assertEqual(licence_data_dir(), entitlement_data_dir())


if __name__ == "__main__":
    unittest.main()
