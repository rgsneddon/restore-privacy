"""Current per-device package assurance + pre-commit install (shipped path)."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT / "scripts"))

from downloads import (  # noqa: E402
    RELEASE_VERSION,
    assure_current_catalog_packages,
    list_catalog_platform_packages,
)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestAssureCurrentCatalog(unittest.TestCase):
    def test_ok_on_shipped_tree(self):
        result = assure_current_catalog_packages()
        self.assertTrue(result["ok"], result.get("errors"))
        self.assertEqual(result["catalog_version"], RELEASE_VERSION)
        self.assertEqual(len(result["platforms"]), 5)
        plats = [p["platform"] for p in result["platforms"]]
        self.assertEqual(
            plats, ["windows", "android", "macos", "ios", "linux"]
        )
        for p in result["platforms"]:
            self.assertIn(RELEASE_VERSION, p["filename"])

    def test_cli_check_and_list_exit_zero(self):
        mod = _load(
            "assure_current_packages",
            ROOT / "scripts" / "assure_current_packages.py",
        )
        self.assertEqual(mod.main(["--list"]), 0)
        self.assertEqual(mod.main(["--check"]), 0)

    def test_fail_when_product_pin_mismatches(self):
        with mock.patch(
            "downloads.product_client_version", return_value="9.9.9"
        ):
            # assure imports current_catalog_version from same module
            from downloads import assure_current_catalog_packages as assure

            result = assure()
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("9.9.9" in e or "client/VERSION" in e for e in result["errors"]),
            result["errors"],
        )

    def test_fail_when_platform_missing(self):
        short = list_catalog_platform_packages()[:3]
        with mock.patch(
            "downloads.list_catalog_platform_packages", return_value=short
        ):
            from downloads import assure_current_catalog_packages as assure

            result = assure()
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("missing platform" in e or "expected 5" in e for e in result["errors"]),
            result["errors"],
        )

    def test_cli_check_nonzero_on_pin_mismatch(self):
        mod = _load(
            "assure_current_packages",
            ROOT / "scripts" / "assure_current_packages.py",
        )
        with mock.patch(
            "downloads.assure_current_catalog_packages",
            return_value={
                "ok": False,
                "catalog_version": RELEASE_VERSION,
                "product_pin": "0.0.0",
                "platforms": list_catalog_platform_packages(),
                "errors": ["catalog pin mismatch"],
            },
        ):
            # re-bind the name the CLI imported at load time
            with mock.patch.object(
                mod,
                "assure_current_catalog_packages",
                return_value={
                    "ok": False,
                    "catalog_version": RELEASE_VERSION,
                    "product_pin": "0.0.0",
                    "platforms": list_catalog_platform_packages(),
                    "errors": ["catalog pin mismatch"],
                },
            ):
                code = mod.main(["--check"])
        self.assertEqual(code, 1)


class TestInstallCommitHook(unittest.TestCase):
    def test_install_writes_pre_commit_invoking_assure(self):
        mod = _load(
            "install_commit_package_task",
            ROOT / "scripts" / "install_commit_package_task.py",
        )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".git" / "hooks").mkdir(parents=True)
            path = mod.install_pre_commit(repo_root=root, force=True)
            self.assertTrue(path.is_file())
            self.assertEqual(path.name, "pre-commit")
            self.assertTrue(mod.hook_invokes_assure(path))
            self.assertTrue(mod.hook_invokes_downloads_map_refresh(path))
            text = path.read_text(encoding="utf-8")
            self.assertIn("assure_current_packages.py", text)
            self.assertIn("--check", text)
            self.assertIn("refresh_downloads_map_inventory.py", text)

    def test_install_cli_on_repo(self):
        mod = _load(
            "install_commit_package_task",
            ROOT / "scripts" / "install_commit_package_task.py",
        )
        # Install into the real repo (force so re-runs are idempotent)
        code = mod.main(["--force"])
        self.assertEqual(code, 0)
        hook = mod.hooks_dir(ROOT) / "pre-commit"
        self.assertTrue(hook.is_file())
        self.assertTrue(mod.hook_invokes_assure(hook))
        self.assertTrue(mod.hook_invokes_downloads_map_refresh(hook))


if __name__ == "__main__":
    unittest.main()
