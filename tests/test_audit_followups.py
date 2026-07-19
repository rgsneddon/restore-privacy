"""Structural checks for post-audit follow-ups (docs M1/M2, gates, Linux ABI)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestDocsM1M2(unittest.TestCase):
    def test_privacy_section_32_includes_linux(self):
        text = (ROOT / "PRIVACY_POLICY.md").read_text(encoding="utf-8")
        self.assertIn(
            "### 3.2 Client applications (Windows, Android, Linux, iOS, and macOS)",
            text,
        )

    def test_readme_has_shared_key_phrase(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("do **not** ship a shared", readme)
        self.assertIn("generates its own Ed25519 device key", readme)


class TestReleaseGates(unittest.TestCase):
    def test_current_build_release_has_assert_no_priv(self):
        script = (ROOT / "scripts" / "build_release_0.1.8.py").read_text(encoding="utf-8")
        self.assertIn("_assert_no_priv", script)
        self.assertIn("def _assert_no_priv", script)

    def test_package_linux_refuses_priv(self):
        src = (ROOT / "scripts" / "package_linux.py").read_text(encoding="utf-8")
        self.assertIn("*.priv", src)
        self.assertIn("refusing private key", src)

    def test_gitignore_excludes_secrets(self):
        gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("secrets/", gi)

    def test_operator_docs_never_force_add_secrets(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        sundries = (ROOT / "sundries.txt").read_text(encoding="utf-8")
        self.assertIn("secrets/", readme.lower() + readme)
        self.assertTrue(
            "force-add" in readme.lower() or "Never commit" in readme,
            "README should warn operators about secrets/",
        )
        self.assertIn("force-add", sundries.lower() or "Never commit" in sundries)


class TestLinuxAbiDocs(unittest.TestCase):
    def test_package_linux_docs_name_abi_range(self):
        src = (ROOT / "scripts" / "package_linux.py").read_text(encoding="utf-8")
        self.assertIn("3.8", src)
        self.assertIn("3.12", src)
        self.assertIn("manylinux", src)
        self.assertIn("package_linux.py", src)
        # Generated LINUX_INSTALL.md content embeds ABI section
        self.assertIn("Supported wheeled Python ABIs", src)
        self.assertTrue(
            "every** release" in src or "every release" in src or "on **every**" in src,
            "package_linux docs must say re-run on every release",
        )

    def test_readme_mentions_re_run_package_linux(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("package_linux.py", readme)
        self.assertIn("3.8", readme)
        self.assertIn("3.12", readme)


class TestAppleAndOps(unittest.TestCase):
    def test_readme_apple_mac_work_required(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Mac work required", readme)
        self.assertIn("Packet Tunnel", readme)
        self.assertIn("diagnostic", readme.lower())

    def test_privacy_section_4_vps_cdn(self):
        privacy = (ROOT / "PRIVACY_POLICY.md").read_text(encoding="utf-8")
        self.assertIn("VPS provider", privacy)
        self.assertIn("CDN", privacy)
        self.assertIn("outside this application's no-log", privacy.lower() or privacy)

    def test_release_md_documents_current_tag(self):
        path = ROOT / "scripts" / "RELEASE.md"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("build_release_0.1.8.py", text)
        self.assertIn("_assert_no_priv", text)
        self.assertIn("package_linux.py", text)


if __name__ == "__main__":
    unittest.main()
