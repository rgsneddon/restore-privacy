"""Windows installer: progress GUI + VERSION written for product clients."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.windows import installer as inst  # noqa: E402


class TestInstallerProgressWiring(unittest.TestCase):
    def test_main_prefers_progress_ui(self):
        src = (ROOT / "client" / "windows" / "installer.py").read_text(encoding="utf-8")
        self.assertIn("run_installer_progress_ui", src)
        self.assertIn("ttk.Progressbar", src)
        self.assertIn("determinate", src)
        self.assertIn("Preparing install", src)
        self.assertIn("SHORTCUT_DISPLAY_NAME", src)
        # main entry uses GUI on Windows
        main = src[src.index("def main") :]
        self.assertIn("run_installer_progress_ui", main)

    def test_install_step_count_positive(self):
        self.assertGreaterEqual(inst.install_step_count(), 4)

    def test_install_calls_progress_callback(self):
        steps: list[tuple[int, int, str]] = []

        def cb(step: int, total: int, status: str) -> None:
            steps.append((step, total, status))

        with tempfile.TemporaryDirectory() as td:
            fake_payload = Path(td) / "payload"
            fake_payload.mkdir()
            exe = fake_payload / f"{inst.APP_NAME}-{inst.VERSION}.exe"
            exe.write_bytes(b"MZ")
            # Minimal tree
            (fake_payload / "secrets").mkdir()
            install_dir = Path(td) / "install"

            with mock.patch.object(inst, "_payload_root", return_value=fake_payload), mock.patch.object(
                inst, "INSTALL_DIR", install_dir
            ), mock.patch.object(inst, "START_MENU", Path(td) / "start"), mock.patch.object(
                inst, "DESKTOP", Path(td) / "desk"
            ), mock.patch.object(
                inst, "_create_shortcut"
            ), mock.patch.object(
                inst, "_provision_secrets", return_value=["node"]
            ), mock.patch.object(
                inst, "strip_all_private_keys", return_value=[]
            ), mock.patch.object(
                inst.subprocess, "Popen"
            ):
                path = inst.install(launch=False, progress_cb=cb)

            self.assertTrue(path.is_file() or path.exists())
            self.assertTrue((install_dir / "VERSION").is_file())
            ver = (install_dir / "VERSION").read_text(encoding="utf-8").strip()
            self.assertEqual(ver, inst.VERSION)
            self.assertNotEqual(ver, "0.0.0")
            self.assertGreaterEqual(len(steps), inst.install_step_count())
            # Status text present
            texts = " ".join(s[2] for s in steps)
            self.assertIn("Copying", texts)
            self.assertIn("shortcut", texts.lower() or texts)

    def test_pyinstaller_recipe_bundles_version_file(self):
        recipe = (ROOT / "scripts" / "build_release_0.0.8.py").read_text(encoding="utf-8")
        self.assertIn("VERSION", recipe)
        self.assertIn("client", recipe)
        self.assertIn("add-data", recipe.replace("_", "-") or recipe)
        self.assertIn("ver_file", recipe)


if __name__ == "__main__":
    unittest.main()
