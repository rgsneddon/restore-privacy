"""Catalog monopin 0.5.4 surfaces used by shop + Windows ship path."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestCatalogMonopin054(unittest.TestCase):
    def test_client_version_pin(self) -> None:
        pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(pin, "0.5.4")

    def test_downloads_release_version_and_windows_basename(self) -> None:
        import sys

        sp = str(ROOT / "status_page")
        if sp not in sys.path:
            sys.path.insert(0, sp)
        import downloads

        self.assertEqual(downloads.RELEASE_VERSION, "0.5.4")
        self.assertEqual(downloads.RELEASE_TAG, "0.5.4")
        self.assertEqual(
            downloads.WINDOWS_EXE_FILENAME,
            "restore-privacy-client-0.5.4-windows-x64-setup.exe",
        )
        self.assertIn("0.5.4", downloads.WINDOWS_EXE_FILENAME)
        self.assertNotIn("0.5.3", downloads.WINDOWS_EXE_FILENAME)

    def test_installer_embedded_pin(self) -> None:
        src = (ROOT / "client" / "windows" / "installer.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('PRODUCT_VERSION_EMBEDDED = "0.5.4"', src)

    def test_window_foreground_present_for_freeze(self) -> None:
        path = ROOT / "client" / "windows" / "window_foreground.py"
        self.assertTrue(path.is_file())
        from client.windows.window_foreground import bring_tk_window_forward

        self.assertTrue(callable(bring_tk_window_forward))

    def test_recipe_and_hiddenimport(self) -> None:
        recipe = (ROOT / "scripts" / "build_release_0.5.4.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('VERSION = "0.5.4"', recipe)
        self.assertIn('PRIOR_TAG = "0.5.3"', recipe)
        freeze = (ROOT / "scripts" / "build_release_0.0.8.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("client.windows.window_foreground", freeze)

    def test_handoff_and_release_notes(self) -> None:
        handoff = ROOT / "client" / "windows" / "WINDOWS_HANDOFF_0.5.4.md"
        notes = ROOT / "scripts" / "RELEASE_NOTES_0.5.4.md"
        self.assertTrue(handoff.is_file(), handoff)
        self.assertTrue(notes.is_file(), notes)
        h = handoff.read_text(encoding="utf-8")
        self.assertIn("0.5.4", h)
        self.assertIn("window_foreground", h)
        self.assertIn(
            "restore-privacy-client-0.5.4-windows-x64-setup.exe", h
        )

    def test_local_windows_setup_artifact_when_present(self) -> None:
        """If a local PE was built this ship, it must be the 0.5.4 basename."""
        setup = (
            ROOT
            / "releases"
            / "0.5.4"
            / "restore-privacy-client-0.5.4-windows-x64-setup.exe"
        )
        if not setup.is_file():
            self.skipTest("releases/0.5.4 Windows setup not on this host")
        self.assertGreater(setup.stat().st_size, 1_000_000)
        # Must not be a renamed empty stub
        self.assertIn(b"MZ", setup.read_bytes()[:2])


if __name__ == "__main__":
    unittest.main()
