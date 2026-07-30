"""Arch / CachyOS family detection and packaging helpers (shipped modules)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


class TestArchFamilyDetection(unittest.TestCase):
    def test_cachyos_and_arch_ids(self):
        from client.linux.ubuntu_compat import (
            is_arch_family,
            is_cachyos,
            is_ubuntu_family,
            linux_family,
            system_packages_for_family,
            package_manager_for_family,
            install_command_for_family,
            ARCH_SYSTEM_PACKAGES,
            UBUNTU_SYSTEM_PACKAGES,
        )

        self.assertTrue(is_arch_family({"ID": "arch", "ID_LIKE": ""}))
        self.assertTrue(is_arch_family({"ID": "cachyos", "ID_LIKE": "arch"}))
        self.assertTrue(is_cachyos({"ID": "cachyos", "NAME": "CachyOS"}))
        self.assertTrue(
            is_arch_family({"ID": "endeavouros", "ID_LIKE": "arch"})
        )
        self.assertTrue(is_arch_family({"ID": "manjaro", "ID_LIKE": "arch"}))
        self.assertTrue(
            is_arch_family({"ID": "something", "ID_LIKE": "archlinux arch"})
        )
        self.assertEqual(linux_family({"ID": "cachyos", "ID_LIKE": "arch"}), "arch")
        # Ubuntu still true
        self.assertTrue(is_ubuntu_family({"ID": "ubuntu", "VERSION_ID": "22.04"}))
        self.assertFalse(is_arch_family({"ID": "ubuntu", "ID_LIKE": "debian"}))
        # Arch is not classified as Ubuntu family
        self.assertFalse(is_ubuntu_family({"ID": "cachyos", "ID_LIKE": "arch"}))

        self.assertEqual(system_packages_for_family("arch"), ARCH_SYSTEM_PACKAGES)
        self.assertEqual(system_packages_for_family("ubuntu"), UBUNTU_SYSTEM_PACKAGES)
        self.assertEqual(package_manager_for_family("arch"), "pacman")
        self.assertEqual(package_manager_for_family("ubuntu"), "apt-get")
        cmd = install_command_for_family("arch")
        self.assertIn("pacman", cmd)
        self.assertIn("python", cmd)
        self.assertIn("tk", cmd)
        self.assertIn("iproute2", cmd)
        self.assertNotIn("python3-tk", cmd)
        u_cmd = install_command_for_family("ubuntu")
        self.assertIn("apt-get", u_cmd)
        self.assertIn("python3-tk", u_cmd)


class TestArchPackagingStage(unittest.TestCase):
    def test_stage_arch_packaging_writes_pkgbuild(self):
        from package_arch_linux import (
            arch_pkg_basename,
            linux_tarball_name,
            package_version,
            stage_arch_packaging,
        )

        ver = package_version()
        self.assertRegex(ver, r"^\d+\.\d+")
        self.assertEqual(
            linux_tarball_name(ver),
            f"restore-privacy-client-{ver}-linux-x64.tar.gz",
        )
        self.assertIn(ver, arch_pkg_basename(ver))
        self.assertTrue(arch_pkg_basename(ver).endswith(".pkg.tar.zst"))

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "arch"
            info = stage_arch_packaging(
                version=ver, out_dir=out, copy_tarball=False
            )
            self.assertEqual(info["version"], ver)
            self.assertFalse(info["deployed"])
            pkg = Path(info["pkgbuild"])
            self.assertTrue(pkg.is_file())
            text = pkg.read_text(encoding="utf-8")
            self.assertIn(f"pkgver={ver}", text)
            self.assertIn(f"restore-privacy-client-{ver}-linux-x64.tar.gz", text)
            self.assertIn("depends=('python' 'tk' 'iproute2')", text)
            self.assertTrue((out / "README_ARCH.md").is_file())
            readme = (out / "README_ARCH.md").read_text(encoding="utf-8")
            self.assertIn("CachyOS", readme)
            self.assertIn("pacman", readme)


class TestInstallScriptsExist(unittest.TestCase):
    def test_arch_and_cachyos_scripts_in_repo(self):
        arch = ROOT / "scripts" / "install_linux_arch.sh"
        cachy = ROOT / "scripts" / "install_linux_cachyos.sh"
        self.assertTrue(arch.is_file())
        self.assertTrue(cachy.is_file())
        a = arch.read_text(encoding="utf-8")
        self.assertIn("pacman", a)
        self.assertIn("CachyOS", a)
        c = cachy.read_text(encoding="utf-8")
        self.assertIn("install_linux_arch.sh", c)

    def test_package_linux_install_sh_mentions_pacman(self):
        src = (ROOT / "scripts" / "package_linux.py").read_text(encoding="utf-8")
        self.assertIn("pacman", src)
        self.assertIn("install_linux_arch.sh", src)
        self.assertIn("install_linux_cachyos.sh", src)
        self.assertIn("CachyOS", src)


if __name__ == "__main__":
    unittest.main()
