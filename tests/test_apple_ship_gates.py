"""Apple ship gates: residual Team NE wired into monopin --apple-only path.

Drives shipped apple_ship_gates + build_release body (no codesign required).
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestAppleShipGates(unittest.TestCase):
    def test_ship_scripts_present(self):
        gates = _load("apple_ship_gates", "scripts/apple_ship_gates.py")
        missing = gates.assert_ship_scripts_present()
        self.assertEqual(missing, [], f"missing ship scripts: {missing}")

    def test_build_release_wires_residual_team_resign(self):
        gates = _load("apple_ship_gates", "scripts/apple_ship_gates.py")
        # Prefer current monopin script; fall back to any 0.5.x build_release
        candidates = sorted((ROOT / "scripts").glob("build_release_0.5*.py"))
        self.assertTrue(candidates, "expected scripts/build_release_0.5*.py")
        # Current VERSION should have matching build_release
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        br = ROOT / "scripts" / f"build_release_{ver}.py"
        if not br.is_file():
            br = candidates[-1]
        text = br.read_text(encoding="utf-8")
        self.assertTrue(
            gates.ship_path_invokes_residual_team(text),
            f"{br.name} must invoke residual Team NE re-sign "
            "(run_residual_team_resign / apple_ship_gates / sign_macos_residual_team)",
        )
        self.assertIn("RPT_SKIP_RESIDUAL_TEAM", text)
        self.assertIn("sign_and_notarize_macos", text)

    def test_residual_team_app_path_is_sibling_copy(self):
        gates = _load("apple_ship_gates", "scripts/apple_ship_gates.py")
        # Use a non-/tmp path: on macOS Path.resolve() maps /tmp → /private/tmp.
        app = Path("/var/empty/Products/Release/restore_privacy_client.app")
        dest = gates.residual_team_app_path(app)
        self.assertEqual(dest.name, "restore_privacy_client.residual-team.app")
        self.assertEqual(dest.parent, app.resolve().parent)

    def test_docs_name_dual_path_ship_checklist(self):
        handoff = list((ROOT / "client_app").glob("APPLE_HANDOFF_0.5*.md"))
        self.assertTrue(handoff)
        # Latest handoff for current monopin
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        path = ROOT / "client_app" / f"APPLE_HANDOFF_{ver}.md"
        if not path.is_file():
            path = max(handoff, key=lambda p: p.stat().st_mtime)
        text = path.read_text(encoding="utf-8")
        self.assertIn("residual", text.lower())
        self.assertTrue(
            "Team residual" in text
            or "sign_macos_residual_team" in text
            or "residual-team" in text
            or "packet-tunnel" in text.lower(),
            f"{path.name} must document Team residual NE re-sign",
        )
        self.assertTrue(
            "notar" in text.lower() or "DevID" in text or "Developer ID" in text,
            f"{path.name} must document DevID notarize for public zip",
        )


if __name__ == "__main__":
    unittest.main()
