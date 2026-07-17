"""Tests for shipped status-page download link builders (release 0.0.1)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import app as status_app  # noqa: E402
from downloads import (  # noqa: E402
    RELEASE_VERSION,
    available_downloads,
    render_download_section_html,
)


class TestDownloadCatalog(unittest.TestCase):
    def test_version_is_0_0_1(self):
        self.assertEqual(RELEASE_VERSION, "0.0.1")

    def test_available_downloads_have_https_github_release_urls(self):
        assets = available_downloads()
        self.assertGreaterEqual(len(assets), 2)
        platforms = {a.platform for a in assets}
        self.assertIn("windows", platforms)
        self.assertIn("android", platforms)
        for a in assets:
            self.assertTrue(a.url.startswith("https://"))
            self.assertIn("/releases/download/0.0.1/", a.url)
            self.assertIn(a.filename, a.url)
            self.assertIn("0.0.1", a.filename)

    def test_render_download_section_uses_real_urls(self):
        html = render_download_section_html()
        self.assertIn("Download client v0.0.1", html)
        self.assertIn('class="dl"', html)
        self.assertIn("Windows", html)
        self.assertIn("Android", html)
        for a in available_downloads():
            self.assertIn(a.url, html)
            self.assertNotIn('href="#"', html)

    def test_status_page_html_includes_downloads(self):
        page = status_app.render_html(
            {"title": "RESTORE PRIVACY", "clients_connected": 0}
        ).decode("utf-8")
        self.assertIn("Download client v0.0.1", page)
        self.assertIn(
            "https://github.com/rgsneddon/restore-privacy/releases/download/0.0.1/",
            page,
        )
        self.assertIn("restore-privacy-client-0.0.1-windows-x64.zip", page)
        self.assertIn("restore-privacy-client-0.0.1-android.apk", page)


if __name__ == "__main__":
    unittest.main()
