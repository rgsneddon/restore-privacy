"""Settings legal links resolve to shipped repo documents (real helper)."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from client.legal_links import (  # noqa: E402
    AUDIT_LABEL,
    AUDIT_REPO_PATH,
    END_USER_LICENCE_LABEL,
    END_USER_LICENCE_REPO_PATH,
    LEGAL_DOC_LINKS,
    PRIVACY_POLICY_LABEL,
    PRIVACY_POLICY_REPO_PATH,
    audit_url,
    end_user_licence_url,
    legal_doc_urls,
    privacy_policy_url,
)


class TestLegalLinksHelper(unittest.TestCase):
    def test_core_links_with_expected_labels(self):
        labels = [link.label for link in LEGAL_DOC_LINKS]
        self.assertIn(AUDIT_LABEL, labels)
        self.assertIn(PRIVACY_POLICY_LABEL, labels)
        self.assertIn(END_USER_LICENCE_LABEL, labels)
        self.assertEqual(AUDIT_LABEL, "Most recent audit")
        self.assertEqual(PRIVACY_POLICY_LABEL, "Privacy policy")
        self.assertEqual(END_USER_LICENCE_LABEL, "End user licence")
        # How-to-buy is not a Settings legal-doc entry
        self.assertNotIn("How to buy", labels)

    def test_repo_paths_exist_on_disk(self):
        for path_name in (
            AUDIT_REPO_PATH,
            PRIVACY_POLICY_REPO_PATH,
            END_USER_LICENCE_REPO_PATH,
        ):
            p = ROOT / path_name
            self.assertTrue(p.is_file(), f"missing shipped document: {path_name}")
            self.assertGreater(p.stat().st_size, 200)

    def test_urls_point_at_status_origin(self):
        urls = legal_doc_urls()
        self.assertGreaterEqual(len(urls), 3)
        for label, url in urls.items():
            self.assertIn(
                "restoreprivacy.online",
                url,
                msg=f"{label} should use status origin, got {url}",
            )
            self.assertNotIn("github.com", url)
            self.assertNotIn("/blob/", url)
            self.assertNotIn("raw.githubusercontent.com", url)
        self.assertTrue(audit_url().endswith("/AUDIT.md"))
        self.assertEqual(AUDIT_REPO_PATH, "AUDIT.md")
        self.assertTrue(privacy_policy_url().endswith("/PRIVACY_POLICY.md"))
        self.assertTrue(end_user_licence_url().endswith("/LICENSE"))
        # Absolute status-host URLs match what Settings webbrowser.open uses
        self.assertTrue(audit_url().startswith("https://restoreprivacy.online/"))
        self.assertTrue(
            privacy_policy_url().startswith("https://restoreprivacy.online/")
        )

    def test_windows_settings_wires_legal_links(self):
        src = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        self.assertIn("from client.legal_links import LEGAL_DOC_LINKS", src)
        self.assertIn("LEGAL_DOC_LINKS", src)
        self.assertIn("webbrowser.open", src)

    def test_flutter_settings_wires_legal_links(self):
        dart = (ROOT / "client_app" / "lib" / "settings_screen.dart").read_text(
            encoding="utf-8"
        )
        links = (ROOT / "client_app" / "lib" / "legal_links.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("kLegalDocLinks", dart)
        self.assertIn("Most recent audit", links)
        self.assertIn("Privacy policy", links)
        self.assertIn("End user licence", links)
        self.assertIn("AUDIT.md", links)
        self.assertNotIn("repoPath: 'audit.md'", links)
        self.assertIn("PRIVACY_POLICY.md", links)
        self.assertIn("LICENSE", links)
        self.assertIn("restoreprivacy.online", links)
        self.assertNotIn("how-to-buy", links)
        self.assertNotIn("How to buy", links)
        self.assertIn("launchUrl", dart)


class TestDocsTrafficShapeAligned(unittest.TestCase):
    def test_readme_and_policy_lean_off_defaults(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        privacy = (ROOT / "PRIVACY_POLICY.md").read_text(encoding="utf-8")
        public_readme = (ROOT / "status_page" / "public" / "README.md").read_text(
            encoding="utf-8"
        )
        public_privacy = (
            ROOT / "status_page" / "public" / "PRIVACY_POLICY.md"
        ).read_text(encoding="utf-8")
        # Product traffic-shape / outer-obfs defaults are OFF (0.4.6 lean residual)
        for text, name in (
            (readme, "README"),
            (privacy, "PRIVACY_POLICY"),
            (public_readme, "status_page/public/README"),
            (public_privacy, "status_page/public/PRIVACY_POLICY"),
        ):
            lower = text.lower().replace("**", "")
            # Forbid ON-default residual claims (shape/obfs/pad/cover)
            for needle in (
                "on by default on every residual path",
                "enabled by default on the product residual",
                "are on by default on residual paths",
                "default on all product residual",
                "enable outer-layer obfuscation",
                "enable padding / jitter / cover by default",
                "padding / jitter / cover by default",
                "outer-layer obfuscation and padding / jitter / cover by default",
                "apply packet padding, timing jitter, and cover traffic by default",
                "by default (opt out with rpt_traffic_shape=0)",
                "opt out with rpt_traffic_shape=0",
            ):
                self.assertNotIn(
                    needle,
                    lower,
                    f"{name} must not claim shape/obfs on by default (lean residual)",
                )
            # Positive lean-off anchors where residual defaults are discussed
            self.assertTrue(
                "off by default" in lower
                or "default off" in lower
                or "lean residual" in lower,
                f"{name} should state lean-off residual defaults",
            )
        self.assertTrue(
            "off by default" in readme.lower()
            or "default off" in readme.lower(),
            "README should state product traffic-shape / outer obfs are off by default",
        )
        self.assertIn("RPT_TRAFFIC_SHAPE", privacy)
        # Live catalog pin in privacy policy (root + public mirror)
        self.assertIn("Current packages (catalog v0.4.6)", privacy)
        self.assertNotIn("Current packages (catalog v0.4.1)", privacy)
        self.assertNotIn("Current packages (catalog v0.4.0)", privacy)
        public_privacy_pin = (
            ROOT / "status_page" / "public" / "PRIVACY_POLICY.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Current packages (catalog v0.4.6)", public_privacy_pin)
        self.assertNotIn("Current packages (catalog v0.4.1)", public_privacy_pin)
        self.assertTrue(
            "off by default" in privacy.lower()
            or "default off" in privacy.lower()
            or "defaults off" in privacy.lower()
            or "lean residual" in privacy.lower(),
            "PRIVACY_POLICY should state shaping/obfs lean-off defaults",
        )
        # Force-on env (not opt-out) for lean-off policy
        self.assertIn("RPT_TRAFFIC_SHAPE=1", privacy)
        self.assertNotIn("RPT_TRAFFIC_SHAPE=0", privacy)
        # Version surface: current catalog pin and/or historical
        self.assertTrue(
            "0.4.6" in readme
            or "1.0.0" in readme
            or "0.4.0" in readme
            or "0.2.9" in readme,
            "README must cite product version",
        )
        self.assertTrue(
            "1.0.0" in privacy
            or "0.4.0" in privacy
            or "0.2.9" in privacy
            or "0.2" in privacy
            or "0.4" in privacy,
            "PRIVACY_POLICY must cite a product version generation",
        )


if __name__ == "__main__":
    unittest.main()
