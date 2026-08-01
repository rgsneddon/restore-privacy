"""Admin selective package upload: only selected rows stage; unselected missing skip."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "status_page"))


class TestSelectiveBrandStage(unittest.TestCase):
    def test_admin_html_has_package_checkboxes(self) -> None:
        src = (ROOT / "status_page" / "admin_panel.py").read_text(encoding="utf-8")
        self.assertIn("suite-pkg-checkbox", src)
        self.assertIn('name="package"', src)
        self.assertIn("Push selected packages", src)
        self.assertIn("data-package-select", src)

    def test_stage_only_selected_skips_unselected_missing(self) -> None:
        import host_paid_assets_vps as hp

        fake_inv = {
            "suite_version": "1.0.3",
            "total": 2,
            "packages": [
                {
                    "filename": "present.zip",
                    "kind": "suite_client",
                    "platform": "macos",
                    "relative_path": "1.0.3/present.zip",
                    "min_bytes": 1,
                },
                {
                    "filename": "missing-windows.exe",
                    "kind": "suite_client",
                    "platform": "windows",
                    "relative_path": "1.0.3/missing-windows.exe",
                    "min_bytes": 1,
                },
            ],
        }
        td = Path(tempfile.mkdtemp())
        try:
            (td / "status_page" / "assets" / "1.0.3").mkdir(parents=True)
            (td / "releases" / "1.0.3").mkdir(parents=True)
            src = td / "releases" / "1.0.3" / "present.zip"
            src.write_bytes(b"ok-bytes")

            def resolve(row, repo_root=None):  # noqa: ANN001
                p = td / "releases" / "1.0.3" / row["filename"]
                return p if p.is_file() else None

            with mock.patch.object(hp, "ROOT", td), mock.patch.object(
                hp, "STATUS", td / "status_page"
            ):
                with mock.patch(
                    "brand_package_inventory.inventory_with_presence",
                    return_value=fake_inv,
                ):
                    with mock.patch(
                        "brand_package_inventory.resolve_local_path",
                        side_effect=resolve,
                    ):
                        staged = hp.stage_brand_packages(
                            version="1.0.3",
                            only_filenames=["present.zip"],
                        )
                        self.assertEqual([p.name for p in staged], ["present.zip"])
        finally:
            shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
