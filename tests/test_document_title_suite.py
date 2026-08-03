"""Browser-tab document <title> is RESTORE PRIVACY (dedicated VPN brand)."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestDocumentTitleSuite(unittest.TestCase):
    def test_public_brand_title_is_all_caps_restore_privacy(self) -> None:
        from public_chrome import PUBLIC_BRAND_TITLE

        self.assertEqual(PUBLIC_BRAND_TITLE, "RESTORE PRIVACY")
        self.assertNotIn("SUITE", PUBLIC_BRAND_TITLE)

    def test_public_display_title_maps_legacy_to_brand(self) -> None:
        from public_chrome import PUBLIC_BRAND_TITLE, public_display_title

        cases = (
            "RESTORE PRIVACY VPN",
            "Restore Privacy VPN",
            "restore privacy vpn",
            "RESTORE PRIVACY",
            "Restore Privacy",
            "Restore Privacy Suite",
            "RESTORE PRIVACY",
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
            self.assertEqual(got, "RESTORE PRIVACY")
            self.assertNotIn("SUITE", got)

    def test_homepage_render_title_tag_is_restore_privacy(self) -> None:
        from app import render_html
        from public_chrome import PUBLIC_BRAND_TITLE

        # Upstream-style legacy brands map to short product brand
        html = render_html({"title": "RESTORE PRIVACY VPN"}).decode("utf-8")
        m = re.search(r"<title>([^<]*)</title>", html)
        self.assertIsNotNone(m)
        assert m is not None
        title = m.group(1).strip()
        self.assertEqual(title, "RESTORE PRIVACY")
        self.assertEqual(title, PUBLIC_BRAND_TITLE)
        self.assertNotEqual(title, "RESTORE PRIVACY SUITE")
        self.assertNotIn("SUITE", title)
        self.assertIn(f"<title>{PUBLIC_BRAND_TITLE}</title>", html)

        # Default / empty status path
        html2 = render_html({}).decode("utf-8")
        m2 = re.search(r"<title>([^<]*)</title>", html2)
        self.assertIsNotNone(m2)
        assert m2 is not None
        self.assertEqual(m2.group(1).strip(), "RESTORE PRIVACY")

    def test_normalize_status_feeds_brand_title(self) -> None:
        from app import normalize_status, public_status_payload
        from public_chrome import PUBLIC_BRAND_TITLE

        out = normalize_status({"title": "RESTORE PRIVACY VPN", "clients_connected": 9})
        self.assertEqual(out["title"], PUBLIC_BRAND_TITLE)
        pub = public_status_payload({"title": "RESTORE PRIVACY VPN"})
        self.assertEqual(pub, {"title": "RESTORE PRIVACY"})


if __name__ == "__main__":
    unittest.main()
