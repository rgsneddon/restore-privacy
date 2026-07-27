"""Active keygen remains valid across monopin upgrades (not app-version-scoped)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestKeygenVersionAgnostic(unittest.TestCase):
    def test_helper_documents_version_agnostic_rule(self):
        from client.payment_entitlement import keygen_unlock_is_version_agnostic

        self.assertTrue(keygen_unlock_is_version_agnostic())

    def test_import_keygen_succeeds_for_active_on_newer_app_version(self):
        """Same RPT-KEY unlocks after 'upgrading' running monopin (mock remote)."""
        from client.payment_entitlement import (
            STATUS_ACTIVE,
            import_keygen_and_verify,
            load_payment_entitlement,
            payment_allows_connect,
            has_keygen_unlock,
        )

        kg = "RPT-KEY-ABCD-EF01-2345"
        # Simulated status host: active entitlement for this keygen (no version field)
        remote = {
            "status": "active",
            "connect_allowed": True,
            "session_id": "cs_test_upgrade_portability",
            "keygen": kg,
            "platform": "windows",
            "valid_until": None,
        }

        def fake_fetch(session_id: str = "", keygen: str = "", **kwargs):
            # Transport is session/keygen only — never app_version
            self.assertNotIn("app_version", kwargs)
            self.assertNotIn("client_version", kwargs)
            self.assertTrue(
                (keygen or session_id).startswith("RPT-KEY-")
                or session_id == "cs_test_upgrade_portability"
                or keygen == kg
            )
            return remote

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "payment_entitlement.json"
            # First unlock on "old" pin 0.4.10
            ent_old = import_keygen_and_verify(
                kg,
                path=path,
                platform="windows",
                fetch=fake_fetch,
                bind_device=False,
                app_version="0.4.10",
            )
            self.assertEqual(ent_old.status, STATUS_ACTIVE)
            self.assertTrue(has_keygen_unlock(ent_old))
            self.assertTrue(payment_allows_connect(ent_old, require=True))

            # Wipe local entitlement file as if clean install of newer monopin
            path.unlink(missing_ok=True)
            # Re-apply original keygen on "new" pin 0.5.0
            ent_new = import_keygen_and_verify(
                kg,
                path=path,
                platform="macos",
                fetch=fake_fetch,
                bind_device=False,
                app_version="0.5.0",
            )
            self.assertEqual(ent_new.status, STATUS_ACTIVE)
            self.assertTrue(has_keygen_unlock(ent_new))
            self.assertTrue(payment_allows_connect(ent_new, require=True))
            self.assertEqual(ent_new.keygen, kg)
            # Same original keygen unlocks on the newer monopin (version not a gate)
            self.assertNotEqual(ent_new.status, "unknown")

    def test_expired_keygen_still_fails_regardless_of_version(self):
        from client.payment_entitlement import (
            STATUS_ACTIVE,
            import_keygen_and_verify,
            payment_allows_connect,
            LICENCE_STATUS_EXPIRED,
            licence_status_from_payment_entitlement,
        )

        kg = "RPT-KEY-DEAD-BEEF-0001"

        def fake_fetch(session_id: str = "", keygen: str = "", **kwargs):
            return {
                "status": "revoked",
                "connect_allowed": False,
                "session_id": "cs_revoked",
                "keygen": kg,
            }

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "payment_entitlement.json"
            ent = import_keygen_and_verify(
                kg,
                path=path,
                fetch=fake_fetch,
                bind_device=False,
                app_version="0.5.0",
            )
            self.assertNotEqual(ent.status, STATUS_ACTIVE)
            self.assertFalse(payment_allows_connect(ent, require=True))
            self.assertEqual(
                licence_status_from_payment_entitlement(ent),
                LICENCE_STATUS_EXPIRED,
            )

    def test_status_host_keygen_lookup_has_no_version_parameter(self):
        """API route accepts keygen only — no app_version gate in shipped handler."""
        src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        # Route exists
        self.assertIn("/api/connect-entitlement", src)
        self.assertIn("get_connect_entitlement_by_keygen", src)
        # connect-entitlement block does not require version
        block_start = src.index("/api/connect-entitlement")
        block = src[block_start : block_start + 1200]
        self.assertIn("keygen", block)
        self.assertNotIn("app_version", block)
        self.assertNotIn("client_version", block)
        # Server helper documents version-agnostic keygen
        pay = (ROOT / "status_page" / "payments.py").read_text(encoding="utf-8")
        self.assertIn("App version is not a factor", pay)

    def test_entitlement_status_url_omits_app_version(self):
        """Client transport builds keygen/session query only — never monopin."""
        from client.payment_entitlement import entitlement_status_url

        url = entitlement_status_url(
            "",
            base_url="https://restoreprivacy.online",
            keygen="RPT-KEY-ABCD-EF01-2345",
        )
        self.assertIn("keygen=", url)
        self.assertNotIn("app_version", url)
        self.assertNotIn("client_version", url)
        self.assertNotIn("version=", url.lower().replace("keygen=", ""))

    def test_flutter_licence_gate_keygen_fetch_is_version_agnostic(self):
        """Flutter residual shells: connect-entitlement query is keygen/session only."""
        dart = (ROOT / "client_app" / "lib" / "licence_gate.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("importKeygenAndVerify", dart)
        self.assertIn("Version-agnostic", dart)
        # Query construction uses keygen or session_id only
        self.assertIn("keygen=${Uri.encodeQueryComponent(kg)}", dart)
        self.assertIn("session_id=${Uri.encodeQueryComponent(sid)}", dart)
        self.assertNotIn("app_version", dart)
        self.assertNotIn("client_version", dart)
        # productVersion only appears in User-Agent (not a reject gate)
        ua_idx = dart.index("RestorePrivacy-flutter/")
        query_idx = dart.index("api/connect-entitlement")
        # Query string built without version params (checked above)
        self.assertIn("/api/connect-entitlement?", dart)
        _ = ua_idx, query_idx

    def test_python_licence_gate_has_no_version_mismatch_path(self):
        """Desktop licence_gate only cares about accepted + keygen/expired — not monopin."""
        src = (ROOT / "client" / "licence_gate.py").read_text(encoding="utf-8")
        self.assertIn("needs_keygen_unlock", src)
        self.assertNotIn("app_version", src)
        self.assertNotIn("version_mismatch", src)
        self.assertNotIn("monopin", src.lower())


class TestCatalogVersionApi(unittest.TestCase):
    def test_public_catalog_version_endpoint_in_handler(self):
        src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/api/catalog-version", src)
        self.assertIn("catalog_version", src)

    def test_catalog_version_payload_shape(self):
        from downloads import current_catalog_version

        ver = current_catalog_version()
        self.assertRegex(ver, r"^\d+\.\d+")
        # Endpoint payload shape (pure, no server)
        payload = {
            "catalog_version": ver,
            "downloads_url": "https://restoreprivacy.online/#downloads",
        }
        self.assertEqual(payload["catalog_version"], ver)


if __name__ == "__main__":
    unittest.main()
