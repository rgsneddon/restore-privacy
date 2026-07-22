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
    "https://github.com/rgsneddon/restore-privacy/releases/tag/0.3.7"
)
EXPECTED_DOWNLOAD_PREFIX = (
    "https://github.com/rgsneddon/restore-privacy/releases/download/0.3.7/"
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

        self.assertEqual(RELEASE_VERSION, "0.3.7")
        self.assertEqual(RELEASE_TAG, "0.3.7")
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
            self.assertIn("donate.stripe.com", a.pay_path)
            self.assertIn(f"client_reference_id={a.platform}", a.pay_path)

    def test_labels_and_html_paid(self):
        html = render_download_section_html()
        self.assertIn("Linux (x64) - Installer (.tar.gz)", html)
        self.assertIn('id="dl-linux"', html)
        self.assertIn("Windows (x64) - Installer (.exe)", html)
        self.assertIn("Developer ID + notarized", html)
        self.assertIn("Team-signed sideload", html)
        self.assertIn('id="dl-android"', html)
        self.assertIn("£2.45", html)
        # BMC tip URL is on homepage shell bottom, not inside downloads section
        self.assertNotIn(BMC_TIP_URL, html)
        # Live default: Stripe Payment Link tiles — platform face + version
        self.assertIn("BUY - 0.3.7", html)
        self.assertIn('class="dl-platform"', html)
        self.assertIn(">Windows<", html)
        self.assertIn(">Android<", html)
        self.assertIn(">macOS<", html)
        self.assertIn(">iOS<", html)
        self.assertIn(">Linux<", html)
        self.assertIn("donate.stripe.com", html)
        self.assertIn('data-buy-mode="stripe-live"', html)
        self.assertNotIn("Coming soon", html)
        # Free permanent GitHub installer hrefs must not appear in public HTML.
        self.assertNotIn("releases/download/0.3.7/", html)
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
        self.assertIn('data-dl-layout="3+2"', html)
        self.assertIn('id="dl-row-1"', html)
        self.assertIn('id="dl-row-2"', html)
        self.assertIn('data-dl-count="3"', html)
        self.assertIn('data-dl-count="2"', html)
        # All five platform controls still present with stable ids/attrs
        for a in assets:
            self.assertIn(f'id="dl-{a.platform}"', html)
            self.assertIn(f'data-platform="{a.platform}"', html)
            self.assertIn(f'data-filename="{a.filename}"', html)
        # CSS ships row layout (not a single vertical stack of five)
        css = download_css()
        self.assertIn(".dl-row", css)
        self.assertIn("flex-direction: row", css)
        # Row wrappers appear under the downloads heading
        head_at = html.find("<h2>")
        row1_at = html.find('id="dl-row-1"')
        row2_at = html.find('id="dl-row-2"')
        self.assertGreater(row1_at, head_at)
        self.assertGreater(row2_at, row1_at)
        # Live mode: Stripe Payment Link per platform; never free GitHub
        for a in available_downloads():
            self.assertIn(f'href="{a.pay_path}"', html)
            self.assertNotIn(f'href="{a.url}"', html)

    def test_available_downloads_have_https_github_release_urls(self):
        for a in available_downloads():
            self.assertTrue(a.url.startswith(EXPECTED_DOWNLOAD_PREFIX))
            self.assertEqual(a.url, f"{EXPECTED_DOWNLOAD_PREFIX}{a.filename}")

    def test_render_download_section_uses_paid_paths(self):
        html = render_download_section_html()
        self.assertIn(f"Download client v{RELEASE_VERSION}", html)
        self.assertIn('class="dl"', html)
        self.assertNotIn('href="#"', html)
        self.assertIn("data-price-pence=\"245\"", html)
        self.assertIn("BUY - 0.3.7", html)
        self.assertIn("donate.stripe.com", html)
        self.assertNotIn("Coming soon", html)

    def test_download_section_omits_long_pay_flow_copy(self):
        """Public downloads: no long session-id success-page explainer block."""
        html = render_download_section_html()
        self.assertNotIn("Each button opens the payment page", html)
        self.assertNotIn("Direct package files are not linked until paid", html)
        self.assertNotIn('id="dl-pay-flow"', html)
        self.assertNotIn('id="dl-claim-hint"', html)
        self.assertNotIn("/download/success?session_id=", html)
        # Platform controls present (live Stripe Pay default)
        self.assertIn("BUY - 0.3.7", html)
        self.assertIn('id="dl-windows"', html)
        self.assertIn("donate.stripe.com", html)
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
        pay_at = html.find('id="dl-windows"')
        self.assertGreater(pay_at, 0, "pay control marker missing")
        # BMC tip is not mid-page in downloads (page bottom via homepage shell)
        self.assertNotIn('id="bmc-tip"', html)
        # Section has panel-card + dl pay controls (full button CSS on homepage)
        self.assertIn("panel-card", html)
        self.assertIn('class="dl"', html)
        from downloads import download_css

        css = download_css()
        self.assertIn("aspect-ratio: 1 / 1", css)
        self.assertIn("5.65rem", css)
        self.assertIn("linear-gradient", css)
        self.assertIn("dl-platform", css)

    def test_homepage_bmc_tip_is_last_content_block(self):
        """Homepage: BMC tip after downloads / node-wipe / audit; single tip link."""
        from coffee_link import coffee_tip_url
        from downloads import BMC_TIP_URL, render_bmc_tip_html

        import app as status_app

        page = status_app.render_html(
            {"title": "RESTORE PRIVACY", "upstream_ok": True}
        ).decode("utf-8")
        self.assertEqual(page.count('id="bmc-tip-link"'), 1)
        self.assertEqual(page.count('id="bmc-tip"'), 1)
        tip = coffee_tip_url() or BMC_TIP_URL
        self.assertIn(tip, page)
        self.assertIn("Tip / support", page)
        self.assertIn("not a paid download", page.lower())

        brand_at = page.find('id="brand-panel"')
        dl_at = page.find('id="downloads"')
        # node wipe section markers
        nw_at = max(
            page.find("node-wipe"),
            page.find("nw-countdown"),
            page.find("node_wipe"),
            page.find('id="node-wipe"'),
            page.find("wipe-countdown"),
        )
        audit_at = page.find('id="audit-panel"')
        bmc_at = page.find('id="bmc-tip"')
        self.assertGreater(dl_at, brand_at)
        self.assertGreater(audit_at, dl_at)
        self.assertGreater(bmc_at, audit_at)
        self.assertGreater(bmc_at, dl_at)
        # Nothing after tip except shell close
        after = page[bmc_at:]
        self.assertNotIn('id="downloads"', after[20:])
        self.assertNotIn('id="audit-panel"', after[20:])
        self.assertNotIn('id="brand-panel"', after[20:])
        # Pure tip helper matches homepage fragment
        frag = render_bmc_tip_html()
        self.assertIn('id="bmc-tip-link"', frag)
        self.assertIn("bmc-tip-link", page)

    def test_status_page_html_includes_paid_downloads(self):
        page = status_app.render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn("RESTORE PRIVACY", page)
        self.assertNotIn("clients-connected", page)
        self.assertIn(f"Download client v{RELEASE_VERSION}", page)
        # Live default: Stripe Payment Link Pay buttons
        self.assertIn("BUY - 0.3.7", page)
        self.assertIn("donate.stripe.com", page)
        self.assertNotIn("Coming soon", page)
        self.assertIn("£2.45", page)
        self.assertIn(WINDOWS_ZIP_FILENAME, page)  # data-filename
        self.assertIn(ANDROID_APK_FILENAME, page)
        self.assertIn(BMC_TIP_URL, page)
        self.assertNotIn("releases/download/", page)


if __name__ == "__main__":
    unittest.main()
