"""Windows installer: progress GUI + VERSION written for product clients."""

from __future__ import annotations

import sys
import tempfile
import traceback
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
                inst, "START_MENU", Path(td) / "start"
            ), mock.patch.object(
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
                path = inst.install(
                    launch=False, progress_cb=cb, install_dir=install_dir
                )

            self.assertTrue(path.is_file() or path.exists())
            self.assertTrue((install_dir / "VERSION").is_file())
            ver = (install_dir / "VERSION").read_text(encoding="utf-8").strip()
            self.assertEqual(ver, inst.VERSION)
            self.assertNotEqual(ver, "0.0.0")
            self.assertNotEqual(ver, "0.3.6")
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
        # Seamless setup: no black console host before Tk progress UI
        self.assertIn("--windowed", recipe)
        self.assertIn("--noconsole", recipe)
        self.assertNotIn('"--console"', recipe)
        # Bootloader splash so onefile unpack is not a blank hang
        self.assertIn("--splash", recipe)
        self.assertIn("installer_splash", recipe)

    def test_install_uses_fast_copy_and_batched_shortcuts(self):
        src = (ROOT / "client" / "windows" / "installer.py").read_text(encoding="utf-8")
        self.assertIn("robocopy", src)
        self.assertIn("_create_shortcuts_batch", src)
        self.assertIn("_close_pyi_splash", src)
        # No full-tree rglob in hot install paths
        self.assertNotIn('root.rglob("*.priv")', src)
        self.assertNotIn('root.rglob("*.exe")', src)

    def test_product_version_pin_not_stale_036(self):
        """Frozen/missing VERSION must not fall back to historical 0.3.6."""
        self.assertNotEqual(inst.PRODUCT_VERSION_EMBEDDED, "0.3.6")
        self.assertNotEqual(inst.VERSION, "0.3.6")
        src = (ROOT / "client" / "windows" / "installer.py").read_text(encoding="utf-8")
        self.assertIn("PRODUCT_VERSION_EMBEDDED", src)
        self.assertIn("_MEIPASS", src)
        # Stale default removed from fallback path
        self.assertNotRegex(src, r'return\s+"0\.3\.6"')


class TestInstallerFailureUi(unittest.TestCase):
    def test_format_install_failure_status_includes_message(self):
        s = inst.format_install_failure_status("copy failed: Access is denied")
        self.assertIn("Installation failed", s)
        self.assertIn("Access is denied", s)

    def test_failure_callback_uses_captured_strings_not_exc(self):
        """Shipped done_err must not close over bare ``exc`` (Python clears it)."""
        src = (ROOT / "client" / "windows" / "installer.py").read_text(encoding="utf-8")
        self.assertIn("format_install_failure_status", src)
        self.assertIn("err_msg = str(exc)", src)
        work = src[src.index("def work") : src.index("threading.Thread(target=work")]
        self.assertIn("fail_status = format_install_failure_status(err_msg)", work)
        done = work[work.index("def done_err") :]
        # Deferred callback must use pre-bound strings only
        self.assertIn("fail_status", done)
        self.assertIn("fail_detail", done)
        self.assertNotIn("{exc}", done)
        self.assertNotIn("status_var.set(f\"Installation failed:\\n{exc}\")", src)
        # Failure must NOT auto-destroy (user reads error + Close)
        self.assertNotIn("root.destroy", done)

    def test_deferred_failure_path_no_nameerror(self):
        """Same capture pattern as run_installer_progress_ui work()/done_err."""
        result: dict = {"error": None, "code": 1}
        known = "Could not copy product files to X (Access is denied)"
        try:
            raise RuntimeError(known)
        except Exception as exc:
            err_msg = str(exc) or exc.__class__.__name__
            err_tb = traceback.format_exc()
            result["error"] = err_msg
            result["code"] = 1
            fail_status = inst.format_install_failure_status(err_msg)
            fail_detail = (err_tb or "")[:500]

            def done_err() -> str:
                # Must not reference ``exc`` — would NameError after except ends
                return fail_status

        # After except block, deferred callback still works
        shown = done_err()
        self.assertIn("Installation failed", shown)
        self.assertIn(known, shown)
        self.assertEqual(result["error"], known)
        self.assertIn("RuntimeError", fail_detail)

    def test_install_surfaces_copy_failure_message(self):
        with tempfile.TemporaryDirectory() as td:
            fake_payload = Path(td) / "payload"
            fake_payload.mkdir()
            (fake_payload / f"{inst.APP_NAME}-{inst.VERSION}.exe").write_bytes(b"MZ")
            install_dir = Path(td) / "install"

            with mock.patch.object(inst, "_payload_root", return_value=fake_payload), mock.patch.object(
                inst, "_copy_tree", side_effect=RuntimeError("Could not copy product files")
            ):
                with self.assertRaises(RuntimeError) as cm:
                    inst.install(launch=False, install_dir=install_dir)
            self.assertIn("Could not copy", str(cm.exception))
            # Failure formatter still works for UI
            ui = inst.format_install_failure_status(str(cm.exception))
            self.assertIn("Installation failed", ui)
            self.assertIn("Could not copy", ui)


class TestInstallerAutoCloseOnSuccess(unittest.TestCase):
    def test_policy_autoclose_on_success(self):
        self.assertTrue(inst.should_autoclose_installer_on_success())
        self.assertGreater(inst.installer_success_autoclose_ms(), 0)
        self.assertLessEqual(inst.installer_success_autoclose_ms(), 5000)

    def test_success_status_formatter(self):
        s = inst.format_install_success_status(Path(r"C:\Programs\RestorePrivacy"), "app.exe")
        self.assertIn("Installation complete", s)
        self.assertIn("RestorePrivacy", s)
        self.assertIn("app.exe", s)

    def test_done_ok_schedules_destroy_on_success(self):
        src = (ROOT / "client" / "windows" / "installer.py").read_text(encoding="utf-8")
        work = src[src.index("def work") : src.index("threading.Thread(target=work")]
        self.assertIn("format_install_success_status", work)
        self.assertIn("should_autoclose_installer_on_success", work)
        done_ok = work[work.index("def done_ok") : work.index("def done_err")]
        self.assertIn("root.destroy", done_ok)
        self.assertIn("root.after(autoclose_ms, root.destroy)", done_ok)
        # Failure branch must not schedule destroy
        done_err = work[work.index("def done_err") :]
        self.assertNotIn("root.destroy", done_err)
        self.assertIn("fail_status", done_err)


if __name__ == "__main__":
    unittest.main()
