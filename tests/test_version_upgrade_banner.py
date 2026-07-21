"""Running version must not fall back to 0.0.0; upgrade banner only when behind."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client import ui_theme  # noqa: E402
from client.ui_theme import (  # noqa: E402
    catalog_latest_version,
    embedded_package_version,
    read_running_version,
    upgrade_available,
    upgrade_banner_text,
    upgrade_download_url,
    version_file_candidates,
)


class TestVersionResolution(unittest.TestCase):
    def test_repo_client_version_is_readable(self):
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertRegex(ver, r"^\d+\.\d+")
        self.assertEqual(read_running_version(), ver)
        self.assertNotEqual(read_running_version(), "0.0.0")

    def test_install_dir_version_preferred_over_missing_module_sibling(self):
        """Simulates frozen: real VERSION at install root, not next to ui_theme only."""
        with tempfile.TemporaryDirectory() as td:
            install = Path(td)
            (install / "VERSION").write_text("0.1.8\n", encoding="utf-8")
            with mock.patch.object(
                ui_theme,
                "version_file_candidates",
                return_value=[install / "VERSION", Path(td) / "missing" / "VERSION"],
            ):
                self.assertEqual(read_running_version(), "0.1.8")

    def test_explicit_version_file(self):
        with tempfile.TemporaryDirectory() as td:
            vf = Path(td) / "VERSION"
            vf.write_text("0.9.9\n", encoding="utf-8")
            self.assertEqual(read_running_version(vf), "0.9.9")

    def test_candidates_include_install_and_frozen_shapes(self):
        cands = version_file_candidates()
        joined = "\n".join(str(p) for p in cands)
        self.assertIn("VERSION", joined)
        self.assertTrue(any(p.name == "VERSION" for p in cands))

    def test_embedded_package_version_not_zero(self):
        self.assertNotEqual(embedded_package_version(), "0.0.0")
        self.assertRegex(embedded_package_version(), r"^\d+\.\d+")


class TestUpgradeBanner(unittest.TestCase):
    def test_no_banner_when_current_equals_catalog(self):
        latest = catalog_latest_version()
        self.assertIsNone(upgrade_banner_text(running=latest, latest=latest))
        self.assertFalse(upgrade_available(running=latest, latest=latest))

    def test_banner_when_behind(self):
        msg = upgrade_banner_text(running="0.1.0", latest="0.1.8")
        self.assertIsNotNone(msg)
        assert msg is not None
        self.assertIn("0.1.0", msg)
        self.assertIn("0.1.8", msg)
        self.assertNotIn("0.0.0", msg)
        self.assertTrue(upgrade_available(running="0.1.0", latest="0.1.8"))

    def test_zero_placeholder_does_not_force_upgrade_against_self(self):
        """If something still returns 0.0.0, treat as embedded package version."""
        emb = embedded_package_version()
        # Equal after normalization â†’ no banner
        self.assertFalse(upgrade_available(running="0.0.0", latest=emb))
        self.assertIsNone(upgrade_banner_text(running="0.0.0", latest=emb))

    def test_app_wires_banner_only_when_message(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("upgrade_banner_text", src)
        self.assertIn("if self._upgrade_msg", src)
        self.assertIn("upgrade_frame.pack", src)

    def test_upgrade_download_url_is_paid_not_free_github(self):
        """In-app update must open paid path; free GH release hrefs are gone."""
        url = upgrade_download_url()
        self.assertTrue(url.startswith("http"))
        self.assertNotIn("releases/download", url)
        self.assertNotIn("releases/latest", url)
        # Prefer Stripe payment page for Windows, else status host downloads.
        self.assertTrue(
            "donate.stripe.com" in url
            or "restore-privacy-status.onrender.com" in url
            or "/#downloads" in url,
            msg=f"unexpected upgrade url: {url}",
        )


if __name__ == "__main__":
    unittest.main()
