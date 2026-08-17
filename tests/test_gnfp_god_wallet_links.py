"""GOD page Windows wallet href comes from shipped gnfp-wallet publisher."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT))


def _rel(tag: str, names: list[str]) -> dict:
    pin = tag.lstrip("v")
    return {
        "tag": tag,
        "assets": [
            {
                "platform": "windows" if "windows" in n else "other",
                "filename": n,
                "href": (
                    "https://github.com/rgsneddon/gnfp-wallet/releases/download/"
                    f"{tag}/{n}"
                ),
            }
            for n in names
        ],
    }


CURRENT_PIN = "0.0.6"
WIN_NAME = f"gnfp-wallet-{CURRENT_PIN}-windows.zip"
WIN_HREF = (
    "https://github.com/rgsneddon/gnfp-wallet/releases/download/"
    f"v{CURRENT_PIN}/{WIN_NAME}"
)


class TestGnfpGodWalletLinks(unittest.TestCase):
    def test_publisher_picks_latest_pin_that_has_windows_zip(self) -> None:
        from downloads import (
            gnfp_wallet_asset_href,
            latest_gnfp_wallet_pin_with_windows,
            list_gnfp_wallet_hub_hrefs,
        )

        releases = [
            _rel(
                "v0.0.2",
                ["gnfp-wallet-0.0.2-windows.zip", "gnfp-wallet-0.0.2-macos.zip"],
            ),
            _rel(
                "v0.0.6",
                [
                    "gnfp-wallet-0.0.6-windows.zip",
                    "gnfp-wallet-0.0.6-linux.zip",
                    "gnfp-wallet-0.0.6-macos.zip",
                    "gnfp-wallet-0.0.6-ios.ipa",
                    "gnfp-wallet-0.0.6-archlinux.zip",
                ],
            ),
            _rel("v0.0.5", ["gnfp-wallet-0.0.5-macos.zip"]),
        ]
        pin = latest_gnfp_wallet_pin_with_windows(releases)
        self.assertEqual(pin, CURRENT_PIN)
        hrefs = list_gnfp_wallet_hub_hrefs(releases)
        labels = [label for label, _href in hrefs]
        urls = [href for _label, href in hrefs]
        self.assertEqual(labels[0], "Windows")
        self.assertEqual(urls[0], WIN_HREF)
        self.assertEqual(urls[0], gnfp_wallet_asset_href(pin, WIN_NAME))
        self.assertTrue(
            urls[0].endswith(f"/v{CURRENT_PIN}/{WIN_NAME}"),
            urls[0],
        )
        self.assertIn("Linux", labels)
        self.assertNotIn(
            "https://github.com/rgsneddon/gnfp/releases/download/v1.1.13/"
            "gnfp-wallet-1.1.13-windows.zip",
            urls,
        )
        self.assertFalse(any("0.0.2-windows.zip" in u for u in urls))

    def test_newer_pin_without_windows_is_not_primary(self) -> None:
        from downloads import latest_gnfp_wallet_pin_with_windows

        releases = [
            _rel("v0.0.7", ["gnfp-wallet-0.0.7-macos.zip"]),
            _rel("v0.0.6", ["gnfp-wallet-0.0.6-windows.zip"]),
        ]
        self.assertEqual(latest_gnfp_wallet_pin_with_windows(releases), "0.0.6")

    def test_god_page_embeds_current_windows_zip(self) -> None:
        from god_rpai import gnfp_wallet_hub_product, render_god_wallet_hub_html
        from god_rpai import render_god_rpai_page_html

        releases = [
            _rel(
                "v0.0.6",
                [
                    "gnfp-wallet-0.0.6-windows.zip",
                    "gnfp-wallet-0.0.6-linux.zip",
                    "gnfp-wallet-0.0.6-macos.zip",
                ],
            )
        ]
        card = gnfp_wallet_hub_product(releases=releases)
        self.assertEqual(card["version"], CURRENT_PIN)
        self.assertEqual(card["hrefs"][0][0], "Windows")
        self.assertEqual(card["hrefs"][0][1], WIN_HREF)
        hub = render_god_wallet_hub_html(releases=releases)
        self.assertIn(WIN_HREF, hub)
        self.assertIn("$GNFP privacy wallet", hub)
        self.assertNotIn("GNPF", hub)
        page = render_god_rpai_page_html()
        self.assertIn("god-hub-gnfp", page)
        self.assertIn("gnfp-wallet-", page)
        self.assertIn("-windows.zip", page)
        self.assertNotIn("GNPF", page)


if __name__ == "__main__":
    unittest.main()
