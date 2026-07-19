"""Windows install: same-version reinstall skips bulk tree copy."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.windows.installer import (  # noqa: E402
    VERSION,
    read_installed_version,
    should_skip_bulk_tree_copy,
    install,
)


class TestSameVersionSkipCopy(unittest.TestCase):
    def test_read_installed_version(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertIsNone(read_installed_version(root))
            (root / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
            self.assertEqual(read_installed_version(root), VERSION)

    def test_skip_when_same_version_and_exe(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            install_dir = root / "install"
            payload = root / "payload"
            install_dir.mkdir()
            payload.mkdir()
            (install_dir / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
            (install_dir / f"RestorePrivacy-{VERSION}.exe").write_bytes(b"MZ")
            (payload / f"RestorePrivacy-{VERSION}.exe").write_bytes(b"MZ")
            self.assertTrue(
                should_skip_bulk_tree_copy(payload, install_dir, version=VERSION)
            )

    def test_no_skip_on_version_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            install_dir = root / "install"
            payload = root / "payload"
            install_dir.mkdir()
            payload.mkdir()
            (install_dir / "VERSION").write_text("0.0.1\n", encoding="utf-8")
            (install_dir / f"RestorePrivacy-{VERSION}.exe").write_bytes(b"MZ")
            (payload / f"RestorePrivacy-{VERSION}.exe").write_bytes(b"MZ")
            self.assertFalse(
                should_skip_bulk_tree_copy(payload, install_dir, version=VERSION)
            )

    def test_no_skip_without_exe(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            install_dir = root / "install"
            payload = root / "payload"
            install_dir.mkdir()
            payload.mkdir()
            (install_dir / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
            (payload / f"RestorePrivacy-{VERSION}.exe").write_bytes(b"MZ")
            self.assertFalse(
                should_skip_bulk_tree_copy(payload, install_dir, version=VERSION)
            )

    def test_install_invokes_skip_and_avoids_copy_tree(self):
        """Shipped install() must call should_skip and not _copy_tree when True."""
        src = (ROOT / "client" / "windows" / "installer.py").read_text(encoding="utf-8")
        self.assertIn("should_skip_bulk_tree_copy", src)
        self.assertIn("skip_copy", src)
        self.assertIn("skipping bulk file copy", src)
        body = src[src.index("def install") : src.index("def run_installer_progress_ui")]
        self.assertIn("if skip_copy:", body)
        self.assertIn("_copy_tree", body)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            install_dir = root / "Programs" / "RestorePrivacy"
            payload = root / "payload"
            payload.mkdir(parents=True)
            install_dir.mkdir(parents=True)
            exe_name = f"RestorePrivacy-{VERSION}.exe"
            (payload / exe_name).write_bytes(b"MZfake")
            (install_dir / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
            (install_dir / exe_name).write_bytes(b"MZinstalled")
            (install_dir / "secrets").mkdir()
            # Minimal node pub so provision does not explode paths
            from client.windows.installer import NODE_PUB

            (payload / "secrets").mkdir(exist_ok=True)
            (payload / "secrets" / NODE_PUB).write_bytes(b"pub")

            with mock.patch(
                "client.windows.installer._payload_root", return_value=payload
            ), mock.patch(
                "client.windows.installer.INSTALL_DIR", install_dir
            ), mock.patch(
                "client.windows.installer._copy_tree"
            ) as copy_tree, mock.patch(
                "client.windows.installer._create_shortcut"
            ), mock.patch(
                "client.windows.installer.subprocess.Popen"
            ):
                install(launch=False)
            copy_tree.assert_not_called()


if __name__ == "__main__":
    unittest.main()
