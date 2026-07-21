"""Catalog 0.3.4 packages must embed pin 0.3.4 (not stale 0.3.3/0.3.0)."""

from __future__ import annotations

import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.3.4"
REL = ROOT / "releases" / VERSION


def _plist_short_version(plist: Path) -> str:
    r = subprocess.run(
        ["/usr/libexec/PlistBuddy", "-c", "Print :CFBundleShortVersionString", str(plist)],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        raise unittest.SkipTest(f"PlistBuddy failed on {plist}: {r.stderr}")
    return r.stdout.strip()


@unittest.skipUnless(REL.is_dir(), "releases/0.3.4 not present")
class Test034PackagePins(unittest.TestCase):
    def test_macos_cfbundle_is_0_3_4(self):
        zpath = REL / f"restore-privacy-client-{VERSION}-macos.zip"
        if not zpath.is_file():
            self.skipTest("macos zip missing")
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["unzip", "-q", "-o", str(zpath), "-d", td], check=True)
            app = next(Path(td).rglob("restore_privacy_client.app"))
            ver = _plist_short_version(app / "Contents" / "Info.plist")
            self.assertEqual(ver, VERSION)

    def test_ios_cfbundle_is_0_3_4(self):
        zpath = REL / f"restore-privacy-client-{VERSION}-ios.zip"
        if not zpath.is_file():
            self.skipTest("ios zip missing")
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["unzip", "-q", "-o", str(zpath), "-d", td], check=True)
            app = next(Path(td).rglob("Runner.app"))
            ver = _plist_short_version(app / "Info.plist")
            self.assertEqual(ver, VERSION)

    def test_linux_version_file_and_topdir(self):
        tgz = REL / f"restore-privacy-client-{VERSION}-linux-x64.tar.gz"
        if not tgz.is_file():
            self.skipTest("linux tgz missing")
        with tarfile.open(tgz, "r:gz") as tf:
            names = tf.getnames()
        self.assertTrue(
            any(n.startswith(f"restore-privacy-{VERSION}-linux/") for n in names),
            f"top dir not {VERSION}-linux",
        )
        with tarfile.open(tgz, "r:gz") as tf:
            member = next(m for m in tf.getmembers() if m.name.endswith("client/VERSION"))
            f = tf.extractfile(member)
            assert f is not None
            pin = f.read().decode("utf-8").strip()
        self.assertEqual(pin, VERSION)

    def test_windows_sfx_title_and_version_file(self):
        exe = REL / f"restore-privacy-client-{VERSION}-windows-x64-setup.exe"
        if not exe.is_file():
            self.skipTest("windows setup missing")
        data = exe.read_bytes()
        self.assertIn(f'Title="Restore Privacy {VERSION}"'.encode(), data)
        self.assertNotIn(b'Title="Restore Privacy 0.3.3"', data)
        # Extract VERSION via 7z when available
        if subprocess.run(["which", "7z"], capture_output=True).returncode != 0:
            self.skipTest("7z not available for VERSION extract")
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run(
                ["7z", "e", "-y", f"-o{td}", str(exe), "client/VERSION"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            pin = (Path(td) / "VERSION").read_text(encoding="utf-8").strip()
            self.assertEqual(pin, VERSION)

    def test_android_version_name_is_0_3_4(self):
        apk = REL / f"restore-privacy-client-{VERSION}-android.apk"
        if not apk.is_file():
            self.skipTest("android apk missing")
        with zipfile.ZipFile(apk) as z:
            dex = z.read("classes.dex")
            # residual wire still required
            self.assertIn(b"pfs-x25519", dex)
            self.assertIn(b"RPT-OBFS-LAYER", dex)
            manifest = z.read("AndroidManifest.xml")
        # AXML string pool stores versionName as UTF-16-LE
        self.assertIn(VERSION.encode("utf-16-le"), manifest)
        self.assertNotIn("0.3.3".encode("utf-16-le"), manifest)
        self.assertNotIn("0.3.0".encode("utf-16-le"), manifest)
        # Prefer aapt badging when build-tools present
        aapt = Path.home() / "Library/Android/sdk/build-tools/35.0.0/aapt"
        if aapt.is_file():
            r = subprocess.run(
                [str(aapt), "dump", "badging", str(apk)],
                capture_output=True,
                text=True,
                check=False,
            )
            if r.returncode == 0:
                self.assertIn(f"versionName='{VERSION}'", r.stdout)


if __name__ == "__main__":
    unittest.main()
