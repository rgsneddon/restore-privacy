"""Licence acceptance gate: local store, may_connect, no upload."""

from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path

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
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "licence_acceptance.json"
            st = accept_licence(path, ts=1_700_000_000.0)
            self.assertTrue(st.accepted)
            self.assertEqual(st.licence_id, CURRENT_LICENCE_ID)
            self.assertTrue(has_accepted_licence(path))
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
            accept_licence(path, licence_id="OLD-ID")
            self.assertFalse(has_accepted_licence(path))
            self.assertFalse(may_connect(path))

    def test_clear_blocks_again(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "licence_acceptance.json"
            accept_licence(path)
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


if __name__ == "__main__":
    unittest.main()
