"""Product settings: persist run-at-startup + autoconnect; honor launch path."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.windows import settings_store as ss  # noqa: E402
from client.windows.settings_store import (  # noqa: E402
    ProductSettings,
    apply_run_at_startup,
    load_settings,
    save_settings,
    should_autoconnect_on_launch,
    should_run_at_startup,
)


class TestSettingsPersistence(unittest.TestCase):
    def test_defaults_both_off(self):
        d = ss.default_settings()
        self.assertFalse(d.run_at_startup)
        self.assertFalse(d.autoconnect_on_launch)

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            s = ProductSettings(run_at_startup=True, autoconnect_on_launch=True)
            out = save_settings(s, path=path)
            self.assertTrue(out.is_file())
            loaded = load_settings(path=path)
            self.assertTrue(loaded.run_at_startup)
            self.assertTrue(loaded.autoconnect_on_launch)

            s2 = ProductSettings(run_at_startup=False, autoconnect_on_launch=True)
            save_settings(s2, path=path)
            loaded2 = load_settings(path=path)
            self.assertFalse(loaded2.run_at_startup)
            self.assertTrue(loaded2.autoconnect_on_launch)

            # Simulate process restart: new load from same file
            again = load_settings(path=path)
            self.assertEqual(again.autoconnect_on_launch, True)
            self.assertEqual(again.run_at_startup, False)

    def test_corrupt_file_yields_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            path.write_text("{not json", encoding="utf-8")
            s = load_settings(path=path)
            self.assertFalse(s.run_at_startup)
            self.assertFalse(s.autoconnect_on_launch)

    def test_missing_file_yields_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "nope.json"
            s = load_settings(path=path)
            self.assertFalse(s.run_at_startup)
            self.assertFalse(s.autoconnect_on_launch)

    def test_helpers_read_settings(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "settings.json"
            save_settings(
                ProductSettings(run_at_startup=True, autoconnect_on_launch=False),
                path=path,
            )
            s = load_settings(path=path)
            self.assertTrue(should_run_at_startup(s))
            self.assertFalse(should_autoconnect_on_launch(s))


class TestAutoconnectLaunchWiring(unittest.TestCase):
    def test_app_main_honors_settings_autoconnect(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("should_autoconnect_on_launch", src)
        self.assertIn("_settings_autoconnect", src)
        self.assertIn("_start_connect", src)
        main = src[src.index("def main") :]
        self.assertIn("should_autoconnect_on_launch()", main)
        # Must not hard-assert always false anymore
        self.assertNotIn("assert not auto_connect_on_launch_enabled()", main)

    def test_auto_connect_enabled_reads_store(self):
        from client.windows import app as win_app

        with mock.patch(
            "client.windows.app.should_autoconnect_on_launch", return_value=True
        ):
            self.assertTrue(win_app.auto_connect_on_launch_enabled())
        with mock.patch(
            "client.windows.app.should_autoconnect_on_launch", return_value=False
        ):
            self.assertFalse(win_app.auto_connect_on_launch_enabled())


class TestStartupRegistration(unittest.TestCase):
    def test_apply_run_at_startup_enable_disable(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "Startup"
            folder.mkdir()
            link = folder / ss.startup_shortcut_name()
            with mock.patch.object(ss, "startup_folder", return_value=folder), mock.patch.object(
                ss, "resolve_client_launch_target", return_value=(r"C:\x\app.exe", "", r"C:\x")
            ), mock.patch("subprocess.run") as run:
                run.return_value = mock.Mock(returncode=0, stderr="", stdout="")
                # Create empty file to simulate successful shortcut
                def _fake_run(*a, **k):
                    link.write_text("lnk", encoding="utf-8")
                    return mock.Mock(returncode=0, stderr="", stdout="")

                run.side_effect = _fake_run
                st = apply_run_at_startup(True)
                self.assertEqual(st, "enabled")
                self.assertTrue(link.is_file())

                st2 = apply_run_at_startup(False)
                self.assertEqual(st2, "disabled")
                self.assertFalse(link.is_file())

    def test_apply_skipped_non_windows(self):
        with mock.patch.object(ss.sys, "platform", "linux"):
            self.assertEqual(apply_run_at_startup(True), "skipped:non_windows")


class TestSettingsUiWiring(unittest.TestCase):
    def test_windows_cog_and_settings_surface(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("_open_settings", src)
        self.assertIn("⚙", src)
        self.assertIn("Run at device startup", src)
        self.assertIn("Autoconnect on launch", src)
        self.assertIn("BooleanVar", src)
        self.assertIn("save_settings", src)
        self.assertIn("apply_run_at_startup", src)

    def test_flutter_settings_ui(self):
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        screen = (ROOT / "client_app" / "lib" / "settings_screen.dart").read_text(
            encoding="utf-8"
        )
        store = (ROOT / "client_app" / "lib" / "settings_store.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("Icons.settings", main)
        self.assertIn("_openSettings", main)
        self.assertIn("SettingsScreen", main)
        self.assertIn("_maybeAutoconnect", main)
        self.assertIn("SwitchListTile", screen)
        self.assertIn("Run at device startup", screen)
        self.assertIn("Autoconnect on launch", screen)
        self.assertIn("kKeyRunAtStartup", store)
        self.assertIn("kKeyAutoconnectOnLaunch", store)

    def test_android_boot_receiver_wired(self):
        manifest = (
            ROOT
            / "client_app"
            / "android"
            / "app"
            / "src"
            / "main"
            / "AndroidManifest.xml"
        ).read_text(encoding="utf-8")
        self.assertIn("BootLaunchReceiver", manifest)
        self.assertIn("BOOT_COMPLETED", manifest)
        self.assertIn("RECEIVE_BOOT_COMPLETED", manifest)
        boot = (
            ROOT
            / "client_app"
            / "android"
            / "app"
            / "src"
            / "main"
            / "kotlin"
            / "com"
            / "restoreprivacy"
            / "restore_privacy_client"
            / "BootLaunchReceiver.kt"
        )
        self.assertTrue(boot.is_file())
        text = boot.read_text(encoding="utf-8")
        self.assertIn("isRunAtStartupEnabled", text)
        prefs = (
            ROOT
            / "client_app"
            / "android"
            / "app"
            / "src"
            / "main"
            / "kotlin"
            / "com"
            / "restoreprivacy"
            / "restore_privacy_client"
            / "StartupPrefs.kt"
        ).read_text(encoding="utf-8")
        self.assertIn("setRunAtStartup", prefs)
        self.assertIn("COMPONENT_ENABLED_STATE", prefs)


if __name__ == "__main__":
    unittest.main()
