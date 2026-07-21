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
    def test_readme_and_policy_not_defaults_off(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        privacy = (ROOT / "PRIVACY_POLICY.md").read_text(encoding="utf-8")
        # Product traffic-shape default is ON — no claim that shaping defaults off
        for text, name in ((readme, "README"), (privacy, "PRIVACY_POLICY")):
            lower = text.lower()
            # Forbid traffic-shape "defaults off" phrasing near pad/jitter/cover
            for needle in (
                "traffic-shape features (padding / jitter / cover) — **defaults off**",
                "optional traffic-shape features (padding / jitter / cover) — **defaults off**",
                "defaults are off** for bandwidth",
                "defaults are off for bandwidth",
            ):
                self.assertNotIn(
                    needle.lower().replace("**", ""),
                    lower.replace("**", ""),
                    f"{name} must not claim traffic-shape defaults off",
                )
        self.assertTrue(
            "on by default" in readme.lower()
            or "enabled by default" in readme.lower(),
            "README should state product traffic-shape is on by default",
        )
        self.assertIn("RPT_TRAFFIC_SHAPE", privacy)
        self.assertTrue(
            "enabled by default" in privacy.lower(),
            "PRIVACY_POLICY should state shaping enabled by default",
        )
        # Version surface: public v1.0.0 and/or historical 0.2.9
        self.assertTrue(
            "1.0.0" in readme or "0.3.3" in readme or "0.2.9" in readme,
            "README must cite product version",
        )
        self.assertTrue(
            "1.0.0" in privacy or "0.3.3" in privacy or "0.2.9" in privacy or "0.2" in privacy,
            "PRIVACY_POLICY must cite a product version generation",
        )


if __name__ == "__main__":
    unittest.main()
