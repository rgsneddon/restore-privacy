"""Catalog 0.3.6 multi-hop residual package pins (Linux reference + honesty).

When ``releases/0.3.6`` Linux tarball is present, it must embed:
- ``client/VERSION`` = 0.3.6
- ``MULTI_HOP_ROUTING_IMPLEMENTED = True``
- ``product/exit_node_elgamal.pub`` (Romania exit; ElGamal policy A)
and must **not** be bit-identical to the 0.3.5 Linux package.
"""

from __future__ import annotations

import hashlib
import sys
import tarfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VERSION = "0.3.6"
REL = ROOT / "releases" / VERSION
LINUX = REL / f"restore-privacy-client-{VERSION}-linux-x64.tar.gz"
LINUX_035 = (
    ROOT
    / "releases"
    / "0.3.5"
    / "restore-privacy-client-0.3.5-linux-x64.tar.gz"
)
# Tracked product exit pub pin (Romania)
EXIT_PUB_PIN = (
    "a36a3f38066ece7b33abfab6a57942fb998919b4a753ee0d9e9ec9c97c1c7352"
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Test036SourcePins(unittest.TestCase):
    def test_client_version_pin(self):
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(ver, VERSION)

    def test_multihop_routing_implemented(self):
        from client.multihop import MULTI_HOP_ROUTING_IMPLEMENTED, PRODUCT_EXIT_HOST

        self.assertIs(MULTI_HOP_ROUTING_IMPLEMENTED, True)
        self.assertEqual(PRODUCT_EXIT_HOST, "185.146.232.107")

    def test_exit_pub_tracked_and_distinct_from_entry(self):
        exit_p = ROOT / "product" / "exit_node_elgamal.pub"
        entry_p = ROOT / "product" / "node_elgamal.pub"
        self.assertTrue(exit_p.is_file())
        self.assertTrue(entry_p.is_file())
        exit_b = exit_p.read_bytes()
        entry_b = entry_p.read_bytes()
        self.assertGreaterEqual(len(exit_b), 32)
        self.assertNotEqual(exit_b, entry_b)
        self.assertEqual(hashlib.sha256(exit_b).hexdigest(), EXIT_PUB_PIN)

    def test_readme_multihop_honesty(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("RPT_MULTIHOP_ENABLED=1", text)
        self.assertIn("Romania", text)
        # Must not claim multi-hop residual is still missing
        low = text.lower()
        self.assertNotIn("not residual multi-hop until", low)
        self.assertNotIn("no multi-hop residual yet", low)
        self.assertIn("opt-in", low)

    def test_package_linux_ships_exit_pub_candidates(self):
        src = (ROOT / "scripts" / "package_linux.py").read_text(encoding="utf-8")
        self.assertIn("exit_node_elgamal.pub", src)
        self.assertIn("node_elgamal.pub", src)


@unittest.skipUnless(LINUX.is_file(), "releases/0.3.6 Linux package not present")
class Test036LinuxPackageMultihop(unittest.TestCase):
    def test_not_bit_identical_to_0_3_5(self):
        if not LINUX_035.is_file():
            self.skipTest("0.3.5 Linux package absent; cannot compare hashes")
        h36 = _sha256(LINUX)
        h35 = _sha256(LINUX_035)
        self.assertNotEqual(
            h36,
            h35,
            "0.3.6 Linux package must differ from 0.3.5 (rebuild with multihop)",
        )

    def test_embeds_version_multihop_and_exit_pub(self):
        with tarfile.open(LINUX, "r:gz") as tf:
            names = set(tf.getnames())
            # VERSION
            ver_members = [n for n in names if n.endswith("/client/VERSION")]
            self.assertTrue(ver_members, "client/VERSION missing from tarball")
            ver = tf.extractfile(ver_members[0]).read().decode("utf-8").strip()
            self.assertEqual(ver, VERSION)
            # multihop.py
            mh_members = [n for n in names if n.endswith("/client/multihop.py")]
            self.assertTrue(mh_members)
            mh = tf.extractfile(mh_members[0]).read().decode("utf-8")
            self.assertIn("MULTI_HOP_ROUTING_IMPLEMENTED = True", mh)
            self.assertIn("185.146.232.107", mh)
            # exit pub
            exit_members = [
                n for n in names if n.endswith("/product/exit_node_elgamal.pub")
            ]
            self.assertTrue(
                exit_members,
                "product/exit_node_elgamal.pub must ship in Linux 0.3.6 package",
            )
            exit_bytes = tf.extractfile(exit_members[0]).read()
            self.assertEqual(
                hashlib.sha256(exit_bytes).hexdigest(),
                EXIT_PUB_PIN,
            )
            entry_members = [
                n for n in names if n.endswith("/product/node_elgamal.pub")
            ]
            self.assertTrue(entry_members)
            entry_bytes = tf.extractfile(entry_members[0]).read()
            self.assertNotEqual(exit_bytes, entry_bytes)

    def test_release_notes_honest_package_matrix(self):
        notes = (ROOT / "scripts" / "RELEASE_NOTES_0.3.6.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Linux", notes)
        self.assertIn("Android", notes)
        low = notes.lower().replace("**", "")
        self.assertIn("residual-via-exit", low)
        # Windows honesty: native PE rebuild still required for multihop code
        self.assertIn("Windows", notes)
        self.assertTrue(
            "native" in low or "rebuild" in low or "carry" in low,
            "RELEASE_NOTES must be honest about Windows multihop residual limits",
        )



@unittest.skipUnless(
    (REL / f"restore-privacy-client-{VERSION}-android.apk").is_file(),
    "releases/0.3.6 Android APK not present",
)
class Test036AndroidPackageMultihop(unittest.TestCase):
    def test_apk_ships_entry_and_exit_pubs(self):
        import zipfile

        apk = REL / f"restore-privacy-client-{VERSION}-android.apk"
        with zipfile.ZipFile(apk) as z:
            names = set(z.namelist())
            self.assertIn("assets/secrets/node_elgamal.pub", names)
            self.assertIn("assets/secrets/exit_node_elgamal.pub", names)
            exit_b = z.read("assets/secrets/exit_node_elgamal.pub")
            entry_b = z.read("assets/secrets/node_elgamal.pub")
            self.assertEqual(hashlib.sha256(exit_b).hexdigest(), EXIT_PUB_PIN)
            self.assertNotEqual(exit_b, entry_b)
            dex = z.read("classes.dex")
            self.assertIn(b"185.146.232.107", dex)
            self.assertIn(b"pfs-x25519", dex)


@unittest.skipUnless(
    (REL / f"restore-privacy-client-{VERSION}-macos.zip").is_file(),
    "releases/0.3.6 macOS zip not present",
)
class Test036MacosPackagePubs(unittest.TestCase):
    def test_macos_zip_ships_entry_and_exit_pubs(self):
        import zipfile

        zpath = REL / f"restore-privacy-client-{VERSION}-macos.zip"
        with zipfile.ZipFile(zpath) as z:
            exit_names = [n for n in z.namelist() if n.endswith("exit_node_elgamal.pub")]
            entry_names = [n for n in z.namelist() if n.endswith("node_elgamal.pub") and "exit_" not in n]
            self.assertTrue(exit_names, "exit_node_elgamal.pub missing from macOS zip")
            self.assertTrue(entry_names)
            exit_b = z.read(exit_names[0])
            self.assertEqual(hashlib.sha256(exit_b).hexdigest(), EXIT_PUB_PIN)


if __name__ == "__main__":
    unittest.main()
