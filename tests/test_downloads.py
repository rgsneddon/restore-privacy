"""Tests for shipped VPN APP Shop download catalog (restore-privacy 0.3.0) + paid UI."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import app as status_app  # noqa: E402
from downloads import (  # noqa: E402
    ANDROID_APK_FILENAME,
    BMC_TIP_URL,
    GITHUB_REPO,
    IOS_ZIP_FILENAME,
    LINUX_TGZ_FILENAME,
    MACOS_ZIP_FILENAME,
    RELEASE_DOWNLOAD_BASE,
    RELEASE_PAGE_URL,
    RELEASE_TAG,
    RELEASE_VERSION,
    RUST_REPO_URL,
    WINDOWS_ZIP_FILENAME,
    available_downloads,
    download_css,
    download_menu_rows,
    render_download_section_html,
)

EXPECTED_RELEASE_PAGE = (
    "https://github.com/rgsneddon/restore-privacy/releases/tag/0.4.4"
)
EXPECTED_DOWNLOAD_PREFIX = (
    "https://github.com/rgsneddon/restore-privacy/releases/download/0.4.4/"
)
# Public footer points at the paid status host (repo is private).
EXPECTED_PUBLIC_CATALOG_FOOTER = (
    "https://restoreprivacy.online/#downloads"
)


class TestDownloadCatalog(unittest.TestCase):
    def test_version_is_0_2_9(self):
        from downloads import (
            catalog_matches_product_pin,
            current_catalog_version,
            is_current_catalog_filename,
        )

        pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(pin, "0.4.4")
        self.assertEqual(RELEASE_VERSION, pin)
        self.assertEqual(RELEASE_TAG, pin)
        self.assertEqual(current_catalog_version(), RELEASE_VERSION)
        self.assertTrue(catalog_matches_product_pin())
        self.assertEqual(GITHUB_REPO, "restore-privacy")
        self.assertEqual(RELEASE_PAGE_URL, EXPECTED_RELEASE_PAGE)
        self.assertEqual(RELEASE_DOWNLOAD_BASE, EXPECTED_DOWNLOAD_PREFIX.rstrip("/"))
        self.assertEqual(RUST_REPO_URL, EXPECTED_PUBLIC_CATALOG_FOOTER)
        for a in available_downloads():
            self.assertTrue(is_current_catalog_filename(a.filename))
            self.assertIn(RELEASE_VERSION, a.filename)
        self.assertFalse(
            is_current_catalog_filename(
                "restore-privacy-client-0.2.9-windows-x64-setup.exe"
            )
        )

    def test_public_assets_include_device_packages(self):
        assets = available_downloads()
        self.assertEqual(len(assets), 5)
        platforms = {a.platform for a in assets}
        self.assertEqual(platforms, {"windows", "linux", "macos", "ios", "android"})
        by_plat = {a.platform: a for a in assets}
        self.assertEqual(by_plat["windows"].filename, WINDOWS_ZIP_FILENAME)
        self.assertEqual(by_plat["linux"].filename, LINUX_TGZ_FILENAME)
        self.assertEqual(by_plat["macos"].filename, MACOS_ZIP_FILENAME)
        self.assertEqual(by_plat["ios"].filename, IOS_ZIP_FILENAME)
        self.assertEqual(by_plat["android"].filename, ANDROID_APK_FILENAME)
        for a in assets:
            self.assertEqual(a.url, f"{EXPECTED_DOWNLOAD_PREFIX}{a.filename}")
            # Primary path: site-hosted Select your plan page
            self.assertIn("/pay", a.pay_path)
            self.assertIn(f"platform={a.platform}", a.pay_path)

    def test_labels_and_html_paid(self):
        html = render_download_section_html()
        # Catalog filenames remain on option data-filename attrs (not long face labels)
        self.assertIn(LINUX_TGZ_FILENAME, html)
        self.assertIn('value="linux"', html)
        self.assertIn(WINDOWS_ZIP_FILENAME, html)
        self.assertIn(MACOS_ZIP_FILENAME, html)
        self.assertIn(IOS_ZIP_FILENAME, html)
        self.assertIn(ANDROID_APK_FILENAME, html)
        self.assertIn('value="android"', html)
        self.assertIn("£2.45", html)
        # BMC tip URL is on homepage shell bottom, not inside downloads section
        self.assertNotIn(BMC_TIP_URL, html)
        # Live default: embedded platform + plan form + Buy now in downloads box
        self.assertIn("Buy now", html)
        self.assertIn("we accept *", html)
        self.assertIn("£2.45", html)
        self.assertIn("£27.93", html)
        self.assertIn('id="dl-buy-form"', html)
        self.assertIn('id="dl-platform"', html)
        self.assertIn('id="dl-buy-now"', html)
        self.assertIn('action="/pay/checkout"', html)
        self.assertIn('value="windows"', html)
        self.assertIn('value="android"', html)
        self.assertIn('value="macos"', html)
        self.assertIn('value="ios"', html)
        self.assertIn('value="linux"', html)
        self.assertNotIn("buy.stripe.com", html)
        self.assertIn('data-buy-mode="homepage-buy-form"', html)
        self.assertIn('data-billing-intervals="month,year"', html)
        self.assertNotIn("Coming soon", html)
        # Free permanent GitHub installer hrefs must not appear in public HTML.
        self.assertNotIn(f"releases/download/{RELEASE_VERSION}/", html)
        # FULL CATALOGUE / catalog footer link must not be visible on public downloads.
        self.assertNotIn('id="rust-repo-link"', html)
        self.assertNotIn("rust-repo-footer", html)
        self.assertNotIn("installers after £2.45 payment only", html)
        self.assertNotIn("FULL CATALOGUE", html.upper())
        self.assertNotIn("how-to-buy-footer-link", html)
        self.assertNotIn('href="/how-to-buy"', html)
        # BMC tip is page-bottom on homepage shell — not inside downloads section
        self.assertNotIn("bmc-tip-link", html)
        self.assertNotIn('id="bmc-tip"', html)

    def test_download_menu_is_three_then_two_rows(self):
        """Platform menu under the title: row of 3, then row of 2."""
        assets = available_downloads()
        self.assertEqual(len(assets), 5)
        row1, row2 = download_menu_rows(assets)
        self.assertEqual(len(row1), 3)
        self.assertEqual(len(row2), 2)
        self.assertEqual([a.platform for a in row1 + row2], [a.platform for a in assets])

        html = render_download_section_html()
        # Homepage uses a single buy form (not a multi-tile row grid)
        self.assertIn('id="dl-buy-form"', html)
        self.assertIn('id="dl-platform"', html)
        self.assertNotIn('id="dl-row-1"', html)
        self.assertNotIn('id="dl-row-2"', html)
        for a in assets:
            self.assertIn(f'value="{a.platform}"', html)
            self.assertIn(f'data-filename="{a.filename}"', html)
            self.assertNotIn(f'href="{a.url}"', html)
        css = download_css()
        self.assertIn(".dl-buy-form", css)
        self.assertIn(".dl-buy-now", css)
        head_at = html.find("<h2>")
        form_at = html.find('id="dl-buy-form"')
        self.assertGreater(form_at, head_at)

    def test_available_downloads_have_https_github_release_urls(self):
        for a in available_downloads():
            self.assertTrue(a.url.startswith(EXPECTED_DOWNLOAD_PREFIX))
            self.assertEqual(a.url, f"{EXPECTED_DOWNLOAD_PREFIX}{a.filename}")

    def test_render_download_section_uses_paid_paths(self):
        html = render_download_section_html()
        self.assertIn(f"Download client v{RELEASE_VERSION}", html)
        self.assertIn('id="dl-buy-form"', html)
        self.assertNotIn('href="#"', html)
        self.assertIn("Buy now", html)
        self.assertIn("we accept *", html)
        self.assertIn('action="/pay/checkout"', html)
        self.assertIn("homepage-buy-form", html)
        self.assertNotIn("buy.stripe.com", html)
        self.assertNotIn("Coming soon", html)

    def test_download_section_omits_long_pay_flow_copy(self):
        """Public downloads: no long session-id success-page explainer block."""
        html = render_download_section_html()
        self.assertNotIn("Each button opens the payment page", html)
        self.assertNotIn("Direct package files are not linked until paid", html)
        self.assertNotIn('id="dl-pay-flow"', html)
        self.assertNotIn('id="dl-claim-hint"', html)
        self.assertNotIn("/download/success?session_id=", html)
        # Buy form present
        self.assertIn("Buy now", html)
        self.assertIn("we accept *", html)
        self.assertIn('id="dl-buy-form"', html)
        self.assertNotIn('id="dl-windows-year"', html)
        self.assertIn('action="/pay/checkout"', html)
        # No bottom generic “Stripe payment page” footer link
        self.assertNotIn('id="stripe-payment-page-link"', html)
        self.assertNotIn(">Stripe payment page<", html)

    def test_payment_disclaimer_helper_exists_but_not_on_homepage_shop(self):
        """Helper keeps STRONG DISCLAIMER text; public downloads section omits it."""
        from downloads import payment_connect_disclaimer_html, render_download_section_html

        frag = payment_connect_disclaimer_html()
        self.assertIn('id="dl-payment-disclaimer"', frag)
        self.assertIn("STRONG DISCLAIMER", frag)
        self.assertIn("subscription cancellation", frag.lower())
        self.assertIn("subscription period", frag.lower())
        self.assertIn("Connect with the Restore Privacy app is cancelled", frag)

        html = render_download_section_html()
        # Homepage redesign: no strong-disclaimer banner in shop section
        self.assertNotIn('id="dl-payment-disclaimer"', html)
        self.assertNotIn("STRONG DISCLAIMER", html)
        pay_at = html.find('id="dl-buy-now"')
        self.assertGreater(pay_at, 0, "Buy now control marker missing")
        # BMC tip is not mid-page in downloads (page bottom via homepage shell)
        self.assertNotIn('id="bmc-tip"', html)
        # Section has panel-card + homepage buy form
        self.assertIn("panel-card", html)
        self.assertIn('id="dl-buy-form"', html)
        self.assertIn('data-pay-via="homepage-buy-form"', html)
        from downloads import download_css

        css = download_css()
        # Pill buy controls (post-0.4.4 tidy: not fixed square tiles)
        self.assertTrue(
            "aspect-ratio: auto" in css or "aspect-ratio: 1 / 1" in css,
            "buy tile aspect-ratio rule missing",
        )
        self.assertIn(".dl-buy-form", css)
        self.assertIn(".dl-buy-now", css)
        self.assertIn("linear-gradient", css)
        self.assertIn("dl-platform-note", css)
        self.assertIn("dl-interval-row", css)
        self.assertIn("dl-platform-cell", css)

    def test_homepage_copyright_footer_is_last_content_block(self):
        """Homepage: Raskul copyright after downloads / node-wipe / audit."""
        from coffee_link import SITE_COPYRIGHT_TEXT
        from downloads import render_bmc_tip_html

        import app as status_app

        page = status_app.render_html(
            {"title": "RESTORE PRIVACY", "upstream_ok": True}
        ).decode("utf-8")
        self.assertEqual(page.count('id="site-footer"'), 1)
        self.assertIn(SITE_COPYRIGHT_TEXT, page)
        self.assertIn("Raskul", page)
        self.assertIn("all rights reserved", page)
        self.assertNotIn("buymeacoffee.com", page)
        self.assertNotIn("bmc-tip-link", page)
        self.assertNotIn("Tip / support", page)

        brand_at = page.find('id="brand-panel"')
        dl_at = page.find('id="downloads"')
        audit_at = page.find('id="audit-panel"')
        foot_at = page.find('id="site-footer"')
        self.assertGreater(dl_at, brand_at)
        self.assertGreater(audit_at, dl_at)
        self.assertGreater(foot_at, audit_at)
        self.assertGreater(foot_at, dl_at)
        after = page[foot_at:]
        self.assertNotIn('id="downloads"', after[20:])
        self.assertNotIn('id="audit-panel"', after[20:])
        self.assertNotIn('id="brand-panel"', after[20:])
        frag = render_bmc_tip_html()
        self.assertIn('id="site-footer"', frag)
        self.assertIn(SITE_COPYRIGHT_TEXT, frag)

    def test_status_page_html_includes_paid_downloads(self):
        page = status_app.render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn("RESTORE PRIVACY", page)
        self.assertNotIn("clients-connected", page)
        self.assertIn(f"Download client v{RELEASE_VERSION}", page)
        # Live default: homepage buy form (device + plan + Buy now)
        self.assertIn("Buy now", page)
        self.assertIn("we accept *", page)
        self.assertIn('id="dl-buy-form"', page)
        self.assertIn("/pay/checkout", page)
        self.assertIn("homepage-buy-form", page)
        self.assertNotIn("buy.stripe.com", page)
        self.assertNotIn("Coming soon", page)
        self.assertIn("£2.45", page)
        self.assertIn("£27.93", page)
        self.assertIn(WINDOWS_ZIP_FILENAME, page)  # data-filename
        self.assertIn(ANDROID_APK_FILENAME, page)
        self.assertIn("Raskul", page)
        self.assertIn("all rights reserved", page)
        self.assertNotIn("buymeacoffee.com", page)
        self.assertNotIn("releases/download/", page)


if __name__ == "__main__":
    unittest.main()
