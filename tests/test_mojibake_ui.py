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
    "—",
    "—",
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
        # Live catalog: platform options + KEYGEN/plan cart (no Coming soon)
        self.assertIn("Windows", html)
        self.assertIn("Linux", html)
        self.assertIn("macOS", html)
        self.assertIn("iOS", html)
        self.assertIn("Android", html)
        self.assertNotIn("paid download only", html)
        self.assertNotIn("Coming soon", html)
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

    def test_banner_title_virtual_private_network_not_uk_vpn(self):
        """Product chrome brands as Virtual Private Network, not UK VPN."""
        self.assertIn("Virtual Private Network", BANNER_TITLE)
        self.assertNotIn("UK VPN", BANNER_TITLE)
        self.assertNotIn("uk vpn", BANNER_TITLE.lower())
        self.assertTrue(BANNER_TITLE.startswith("Restore Privacy"))


class TestFlutterBannerTitleShipped(unittest.TestCase):
    """Flutter kBannerTitle (client_app) matches Virtual Private Network branding."""

    def test_k_banner_title_constant_not_uk_vpn(self):
        theme = (ROOT / "client_app" / "lib" / "theme.dart").read_text(encoding="utf-8")
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        m = re.search(r"const String kBannerTitle = '([^']+)'", theme)
        self.assertIsNotNone(m, "kBannerTitle constant missing from theme.dart")
        assert m is not None
        banner = m.group(1)
        self.assertIn("Virtual Private Network", banner)
        self.assertNotIn("UK VPN", banner)
        self.assertNotIn("uk vpn", banner.lower())
        self.assertTrue(banner.startswith("Restore Privacy"))
        # Live UI must reference the shared constant (not a hard-coded old phrase).
        self.assertIn("kBannerTitle", main)
        self.assertNotIn("UK VPN", main)


if __name__ == "__main__":
    unittest.main()
