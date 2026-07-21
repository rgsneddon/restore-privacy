"""Linux installer package: baked-in wheels + offline install entry."""

from __future__ import annotations

import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "package_linux", ROOT / "scripts" / "package_linux.py"
)
assert _spec and _spec.loader
pl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pl)


class TestPackageLinuxHelpers(unittest.TestCase):
    def test_package_has_baked_deps_requires_wheels_and_launcher(self):
        with tempfile.TemporaryDirectory() as td:
            stage = Path(td)
            self.assertFalse(pl.package_has_baked_deps(stage))
            (stage / "wheels").mkdir()
            (stage / "wheels" / "cryptography-1.0-manylinux.whl").write_bytes(b"x")
            (stage / "install.sh").write_text(
                "pip install --no-index --find-links=wheels\n", encoding="utf-8"
            )
            bin_d = stage / "bin"
            bin_d.mkdir()
            (bin_d / "privacy-restored").write_text(
                "#!/bin/sh\n.venv/bin/python -m client.linux\n", encoding="utf-8"
            )
            self.assertTrue(pl.package_has_baked_deps(stage))

    def test_write_install_sh_is_offline(self):
        with tempfile.TemporaryDirectory() as td:
            stage = Path(td)
            pl.write_install_sh(stage)
            text = (stage / "install.sh").read_text(encoding="utf-8")
            self.assertIn("--no-index", text)
            self.assertIn("wheels", text)
            self.assertIn(".venv", text)
            self.assertIn("cryptography", text)
            # Must not require apt install of python3-cryptography as primary path
            self.assertNotIn("apt-get install -y python3-cryptography", text)

    def test_write_launcher_uses_venv(self):
        with tempfile.TemporaryDirectory() as td:
            stage = Path(td)
            pl.write_launcher(stage)
            text = (stage / "bin" / "privacy-restored").read_text(encoding="utf-8")
            self.assertIn(".venv/bin/python", text)
            self.assertIn("client.linux", text)
            self.assertIn("install.sh", text)

    def test_catalog_linux_label_installer(self):
        from status_page.downloads import RELEASE_ASSETS, render_download_section_html

        linux = next(a for a in RELEASE_ASSETS if a.platform == "linux")
        self.assertEqual(linux.label, "Linux (x64) - Installer (.tar.gz)")
        html = render_download_section_html()
        self.assertIn("Linux (x64) - Installer (.tar.gz)", html)
        self.assertIn(f"/pay?platform={linux.platform}", html)
        self.assertIn(linux.filename, html)
        self.assertIn("/releases/download/0.3.0/", linux.url)
        self.assertTrue(linux.filename.endswith(".tar.gz"))

    def test_readme_primary_path_is_install_sh(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("bash install.sh", readme)
        self.assertIn("bin/privacy-restored", readme)
        self.assertIn("wheels", readme.lower() or "baked")
        self.assertIn("baked", readme.lower())


class TestStagedOrRecipePackage(unittest.TestCase):
    def test_release_tarball_has_baked_layout_if_present(self):
        """If package was built, it must contain wheels + install.sh."""
        tgz = ROOT / "releases" / pl.VERSION / pl.NAME
        if not tgz.is_file():
            self.skipTest(f"package not built yet: {tgz}")
        self.assertGreater(tgz.stat().st_size, 500_000)
        with tarfile.open(tgz, "r:gz") as tf:
            names = tf.getnames()
        joined = "\n".join(names)
        self.assertIn("wheels/", joined)
        self.assertTrue(any("cryptography-" in n and n.endswith(".whl") for n in names))
        self.assertTrue(any(n.endswith("install.sh") for n in names))
        self.assertTrue(any("privacy-restored" in n for n in names))

    def test_package_linux_module_exports_helpers(self):
        self.assertTrue(callable(pl.download_linux_wheels))
        self.assertTrue(callable(pl.package_has_baked_deps))
        self.assertTrue(pl.NAME.endswith("linux-x64.tar.gz"))
        src = (ROOT / "scripts" / "package_linux.py").read_text(encoding="utf-8")
        self.assertIn("download_linux_wheels", src)
        self.assertIn("--no-index", src)
        self.assertIn("manylinux", src)


if __name__ == "__main__":
    unittest.main()
