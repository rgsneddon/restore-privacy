"""Browser-tab document <title> is RESTORE PRIVACY SUITE, not VPN."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestDocumentTitleSuite(unittest.TestCase):
    def test_public_brand_title_is_all_caps_suite(self) -> None:
        from public_chrome import PUBLIC_BRAND_TITLE

        self.assertEqual(PUBLIC_BRAND_TITLE, "RESTORE PRIVACY SUITE")
        self.assertNotIn("VPN", PUBLIC_BRAND_TITLE)

    def test_public_display_title_maps_vpn_to_suite(self) -> None:
        from public_chrome import PUBLIC_BRAND_TITLE, public_display_title

        cases = (
            "RESTORE PRIVACY VPN",
            "Restore Privacy VPN",
            "restore privacy vpn",
            "RESTORE PRIVACY",
            "Restore Privacy",
            "Restore Privacy Suite",
            "",
            None,
            "RESTORE PRIVACY VPN v1.0.0",
        )
        for raw in cases:
            got = public_display_title(raw)
            self.assertEqual(
                got,
                PUBLIC_BRAND_TITLE,
                msg=f"raw={raw!r} → {got!r}",
            )
            self.assertNotEqual(got, "RESTORE PRIVACY VPN")
            self.assertNotIn("VPN", got)

    def test_homepage_render_title_tag_is_suite_not_vpn(self) -> None:
        from app import render_html
        from public_chrome import PUBLIC_BRAND_TITLE

        # Upstream-style VPN brand must not appear in the browser tab
        html = render_html({"title": "RESTORE PRIVACY VPN"}).decode("utf-8")
        m = re.search(r"<title>([^<]*)</title>", html)
        self.assertIsNotNone(m)
        assert m is not None
        title = m.group(1).strip()
        self.assertEqual(title, "RESTORE PRIVACY SUITE")
        self.assertEqual(title, PUBLIC_BRAND_TITLE)
        self.assertNotEqual(title, "RESTORE PRIVACY VPN")
        self.assertNotIn("VPN", title)
        self.assertIn(f"<title>{PUBLIC_BRAND_TITLE}</title>", html)

        # Default / empty status path
        html2 = render_html({}).decode("utf-8")
        m2 = re.search(r"<title>([^<]*)</title>", html2)
        self.assertIsNotNone(m2)
        assert m2 is not None
        self.assertEqual(m2.group(1).strip(), "RESTORE PRIVACY SUITE")

    def test_normalize_status_feeds_suite_title(self) -> None:
        from app import normalize_status, public_status_payload
        from public_chrome import PUBLIC_BRAND_TITLE

        out = normalize_status({"title": "RESTORE PRIVACY VPN", "clients_connected": 9})
        self.assertEqual(out["title"], PUBLIC_BRAND_TITLE)
        pub = public_status_payload({"title": "RESTORE PRIVACY VPN"})
        self.assertEqual(pub, {"title": "RESTORE PRIVACY SUITE"})


if __name__ == "__main__":
    unittest.main()
