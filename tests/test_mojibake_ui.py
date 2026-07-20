"""User-facing installer + downloads strings must be free of mojibake."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from status_page.downloads import (  # noqa: E402
    RELEASE_ASSETS,
    RELEASE_VERSION,
    render_download_section_html,
)
from client.ui_theme import (  # noqa: E402
    BANNER_TITLE,
    STATUS_CONNECTED,
    STATUS_CONNECTING,
    plain_tunnel_status,
)

# Broken UTF-8-as-cp1252 sequences users reported on buttons / version text
MOJIBAKE_MARKERS = (
    "â€",
    "Â·",
    "â†",
    "â€¦",
    "â€”",
    "â€“",
    "Â ",
    "\ufeff",
)


def _assert_clean(text: str, label: str) -> None:
    for m in MOJIBAKE_MARKERS:
        if m in text:
            raise AssertionError(f"{label} contains mojibake {m!r}: {text[:120]!r}")


class TestDownloadsNoMojibake(unittest.TestCase):
    def test_button_labels_ascii_safe(self):
        for a in RELEASE_ASSETS:
            _assert_clean(a.label, a.platform)
            self.assertIn(" - ", a.label)
            self.assertNotRegex(a.label, r"[^\x09\x0a\x0d\x20-\x7e]")

    def test_render_html_clean(self):
        html = render_download_section_html()
        _assert_clean(html, "download html")
        self.assertIn(f"Download client v{RELEASE_VERSION}", html)
        self.assertIn("Windows | Linux | macOS | iOS | Android - Rust host", html)
        self.assertNotIn("apple-prep", html)
        self.assertNotIn("Â·", html)

    def test_downloads_module_source_clean(self):
        src = (ROOT / "status_page" / "downloads.py").read_text(encoding="utf-8")
        _assert_clean(src, "downloads.py source")


class TestInstallerUiNoMojibake(unittest.TestCase):
    def test_installer_progress_strings_clean(self):
        src = (ROOT / "client" / "windows" / "installer.py").read_text(encoding="utf-8")
        _assert_clean(src, "installer.py")
        # Progress / window chrome users see
        self.assertIn("Locating product files...", src)
        self.assertIn("Preparing install...", src)
        self.assertIn('Installer - version', src)
        self.assertNotIn("â€¦", src)

    def test_format_success_failure_clean(self):
        from client.windows.installer import (
            format_install_failure_status,
            format_install_success_status,
            VERSION,
        )

        ok = format_install_success_status(Path("C:/tmp"), "RestorePrivacy.exe")
        bad = format_install_failure_status("disk full")
        _assert_clean(ok, "success status")
        _assert_clean(bad, "failure status")
        self.assertIn("Installation", ok)
        self.assertIn("failed", bad.lower())
        self.assertRegex(VERSION, r"^\d+\.\d+")


class TestAppStatusLabelsClean(unittest.TestCase):
    def test_theme_status_labels(self):
        for s in (BANNER_TITLE, STATUS_CONNECTING, STATUS_CONNECTED):
            _assert_clean(s, s)
        self.assertEqual(STATUS_CONNECTING, "Connecting...")
        self.assertIn("Connected", STATUS_CONNECTED)
        st = plain_tunnel_status("connected", vpn_ip="10.0.0.1")
        _assert_clean(st, "plain connected")
        self.assertIn("10.0.0.1", st)


if __name__ == "__main__":
    unittest.main()
