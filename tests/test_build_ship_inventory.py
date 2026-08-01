"""Ship inventory: monopin packages, Windows breadcrumbs, free-download docs."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT / "scripts"))


class TestCatalogMonopinAndPackages(unittest.TestCase):
    def test_required_suite_packages_exist(self) -> None:
        from downloads import RELEASE_VERSION, list_catalog_platform_packages

        pin = RELEASE_VERSION
        self.assertEqual(pin, (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip())
        pkgs = list_catalog_platform_packages(version=pin)
        self.assertEqual(len(pkgs), 5)
        for p in pkgs:
            rel = p["relative_path"]
            # relative_path is under releases/ or version-only — try both
            cands = [
                ROOT / "releases" / rel,
                ROOT / "releases" / pin / p["filename"],
                ROOT / "status_page" / "assets" / pin / p["filename"],
            ]
            found = next((c for c in cands if c.is_file() and c.stat().st_size > 1000), None)
            self.assertIsNotNone(found, f"missing package for {p['platform']}: {p['filename']}")
            self.assertIn(pin, p["filename"])


class TestBrandInventorySlots(unittest.TestCase):
    def test_brand_inventory_has_suite_and_companions(self) -> None:
        from brand_package_inventory import list_brand_installer_packages

        rows = list_brand_installer_packages(repo_root=ROOT)
        kinds = {r["kind"] for r in rows}
        for need in ("suite_client", "browser", "rpos", "rpos_app"):
            self.assertIn(need, kinds)
        # companion files under releases/
        for r in rows:
            if r["kind"] not in ("suite_client", "browser", "rpos", "rpos_app"):
                continue
            fp = ROOT / "releases" / r["relative_path"]
            self.assertTrue(
                fp.is_file() and fp.stat().st_size > 0,
                f"missing brand slot {r['kind']} {r['relative_path']}",
            )


class TestWindowsBreadcrumbsMonopin(unittest.TestCase):
    def test_windows_handoff_and_release_breadcrumbs(self) -> None:
        from downloads import RELEASE_VERSION

        pin = RELEASE_VERSION
        handoff = ROOT / "client" / "windows" / f"WINDOWS_HANDOFF_{pin}.md"
        self.assertTrue(handoff.is_file(), f"missing {handoff}")
        text = handoff.read_text(encoding="utf-8")
        self.assertIn(pin, text)
        pe = f"restore-privacy-client-{pin}-windows-x64-setup.exe"
        self.assertIn(pe, text)
        self.assertIn("build_windows_multihop", text)
        self.assertIn("host_paid_assets_vps", text)
        self.assertIn("135.181.152.10", text)

        crumbs = ROOT / "releases" / pin / "WINDOWS_BREADCRUMBS.md"
        self.assertTrue(crumbs.is_file())
        ctext = crumbs.read_text(encoding="utf-8")
        self.assertIn(pin, ctext)
        self.assertIn(pe, ctext)

        vault = ROOT / "dist" / "breadcrumbs" / "current" / "WINDOWS_HANDOFF.md"
        if vault.is_file():
            v = vault.read_text(encoding="utf-8")
            self.assertIn(pin, v)
            self.assertIn(pe, v)


class TestFreeDownloadDoc(unittest.TestCase):
    def test_suite_free_download_doc_monopin(self) -> None:
        from downloads import RELEASE_VERSION

        pin = RELEASE_VERSION
        doc = (ROOT / "docs" / "SUITE_FREE_DOWNLOAD.md").read_text(encoding="utf-8")
        self.assertIn(pin, doc)
        self.assertIn("/suite/download", doc)
        self.assertIn(f"restore-privacy-client-{pin}-windows-x64-setup.exe", doc)
        self.assertIn("host_paid_assets_vps", doc)
        self.assertIn("WINDOWS_HANDOFF", doc)


if __name__ == "__main__":
    unittest.main()
