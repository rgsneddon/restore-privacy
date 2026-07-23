"""Licence acceptance gate: local store, may_connect, no upload."""

from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.licence_gate import (  # noqa: E402
    CONNECT_BLOCKED_LICENCE_MSG,
    CURRENT_LICENCE_ID,
    accept_licence,
    assert_may_connect,
    clear_licence_acceptance,
    has_accepted_licence,
    licence_gate_is_local_only,
    load_licence_acceptance,
    may_connect,
)
from client.payment_entitlement import record_payment_success  # noqa: E402


class TestLicenceGateStore(unittest.TestCase):
    def test_default_not_accepted_blocks_connect(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "licence_acceptance.json"
            self.assertFalse(has_accepted_licence(path))
            self.assertFalse(may_connect(path))
            ok, msg = assert_may_connect(path)
            self.assertFalse(ok)
            self.assertIn("licence", msg.lower())
            self.assertEqual(msg, CONNECT_BLOCKED_LICENCE_MSG)

    def test_accept_unlocks_may_connect(self):
        """Licence + active payment entitlement both required for Connect."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "licence_acceptance.json"
            pay = Path(td) / "payment_entitlement.json"
            st = accept_licence(path, ts=1_700_000_000.0)
            self.assertTrue(st.accepted)
            self.assertEqual(st.licence_id, CURRENT_LICENCE_ID)
            self.assertTrue(has_accepted_licence(path))
            # Licence alone is not enough under default payment require
            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ):
                with mock.patch(
                    "client.payment_entitlement.ensure_entitlement_for_connect",
                    return_value=None,
                ):
                    self.assertFalse(may_connect(path))
                    # Active entitlement + keygen unlock required for Connect
                    record_payment_success(
                        "cs_test_licence",
                        path=pay,
                        keygen="RPT-KEY-TEST-LICE-NCE1",
                    )
                    self.assertTrue(may_connect(path))
                    ok, msg = assert_may_connect(path)
                    self.assertTrue(ok)
                    self.assertEqual(msg, "")
            loaded = load_licence_acceptance(path)
            self.assertTrue(loaded.accepted)
            self.assertEqual(loaded.licence_id, CURRENT_LICENCE_ID)

    def test_wrong_licence_id_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "licence_acceptance.json"
            pay = Path(td) / "payment_entitlement.json"
            accept_licence(path, licence_id="OLD-ID")
            record_payment_success("cs_x", path=pay)
            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ):
                self.assertFalse(has_accepted_licence(path))
                self.assertFalse(may_connect(path))

    def test_clear_blocks_again(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "licence_acceptance.json"
            pay = Path(td) / "payment_entitlement.json"
            accept_licence(path)
            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ):
                with mock.patch(
                    "client.payment_entitlement.ensure_entitlement_for_connect",
                    return_value=None,
                ):
                    record_payment_success(
                        "cs_clear",
                        path=pay,
                        keygen="RPT-KEY-CLEAR-TEST-KEY1",
                    )
                    self.assertTrue(may_connect(path))
                    clear_licence_acceptance(path)
                    self.assertFalse(may_connect(path))

    def test_local_only_no_network_imports(self):
        self.assertTrue(licence_gate_is_local_only())
        src = (ROOT / "client" / "licence_gate.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        banned = {"urllib", "requests", "httpx", "socket", "aiohttp"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name.split(".", 1)[0], banned)
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn(node.module.split(".", 1)[0], banned)


class TestLicenceGateUiWiring(unittest.TestCase):
    def test_windows_connect_gated(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        gate = (ROOT / "client" / "licence_gate.py").read_text(encoding="utf-8")
        self.assertIn("assert_may_connect", src)
        self.assertIn("accept_licence", src)
        self.assertIn("LICENCE_ACCEPT_BUTTON", src)
        self.assertIn("Accept licence", gate)
        self.assertIn("may_connect", src)
        # Autoconnect path must not bypass
        self.assertIn("assert_may_connect", src)
        # Payment entitlement / keygen import path (post-pay unlock)
        self.assertIn("import_session_and_verify", src)
        self.assertIn("Payment entitlement", src)
        self.assertIn("keygen", src.lower())

    def test_flutter_connect_gated(self):
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        gate = (ROOT / "client_app" / "lib" / "licence_gate.dart").read_text(
            encoding="utf-8"
        )
        screen = (
            ROOT / "client_app" / "lib" / "settings_screen.dart"
        ).read_text(encoding="utf-8")
        self.assertIn("mayConnect", main + gate)
        self.assertIn("assertMayConnect", main + gate)
        self.assertIn("acceptLicence", main + gate + screen)
        self.assertIn("kLicenceAcceptButton", main + screen)
        self.assertIn("Accept licence", gate)
        self.assertIn("importSessionAndVerify", gate + screen)
        self.assertIn("importKeygenAndVerify", gate + screen)
        self.assertIn("refreshEntitlementFromRemote", gate)
        self.assertIn("Verify keygen", screen)

    def test_linux_connect_gated(self):
        src = (ROOT / "client" / "linux" / "app.py").read_text(encoding="utf-8")
        self.assertIn("assert_may_connect", src)
        self.assertIn("accept_licence", src)
        self.assertIn("LICENCE_ACCEPT_BUTTON", src)
        self.assertIn("_show_licence_prompt", src)
        self.assertIn("_open_settings", src)
        self.assertIn("import_session_and_verify", src)
        self.assertIn("Payment entitlement", src)
        self.assertIn("keygen", src.lower())
        self.assertIn("autoconnect_on_launch", src)
        self.assertIn("LEGAL_DOC_LINKS", src)
        self.assertIn("should_autoconnect_on_launch", src)


if __name__ == "__main__":
    unittest.main()
