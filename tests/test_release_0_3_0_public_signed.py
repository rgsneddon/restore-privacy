"""restore-privacy 0.3.3 is the signed, published current public catalog.

README, PRIVACY_POLICY, and status_page/downloads must present 0.3.3 as current
(not RUST-IN-PRIVACY v1.0.0 as the sole public package story). Optional local
zip codesign when releases/0.3.3 Apple packages are on disk.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.3.3"
RELEASE_DIR = ROOT / "releases" / VERSION
MACOS_ZIP = RELEASE_DIR / f"restore-privacy-client-{VERSION}-macos.zip"
IOS_ZIP = RELEASE_DIR / f"restore-privacy-client-{VERSION}-ios.zip"

sys.path.insert(0, str(ROOT / "status_page"))


class Test029PublicCatalogCurrent(unittest.TestCase):
    def test_readme_current_public_is_0_2_9_signed(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        lower = readme.lower()
        self.assertIn("0.3.3", readme)
        self.assertIn("restoreprivacy.online", readme)
        self.assertIn("restore-privacy-client-0.3.3-macos.zip", readme)
        self.assertIn("restore-privacy-client-0.3.3-ios.zip", readme)
        self.assertIn("Developer ID", readme)
        self.assertIn("notariz", lower)
        self.assertIn("team-signed", lower)
        self.assertIn("private", lower)
        self.assertNotIn("prep packages only", lower)
        # Must not present RUST v1.0.0 as the primary Get the app / package table
        self.assertNotIn("Public v1.0.0 (RUST-IN-PRIVACY)", readme)
        self.assertNotIn("restore-privacy-rust-1.0.0-macos.zip", readme)
        # Primary path is paid VPN APP Shop, not free permanent GH release links
        self.assertIn("paid", lower)
        self.assertNotIn(
            "[Download v0.3.3](https://github.com/rgsneddon/restore-privacy/releases/tag/0.3.3)",
            readme,
        )

    def test_privacy_current_public_is_0_2_9_signed(self):
        privacy = (ROOT / "PRIVACY_POLICY.md").read_text(encoding="utf-8")
        self.assertIn("0.3.3", privacy)
        self.assertIn("restoreprivacy.online", privacy)
        self.assertIn("Developer ID", privacy)
        self.assertIn("Team-signed", privacy)
        self.assertIn("private", privacy.lower())
        self.assertNotIn(
            "Current public packages:** [RUST-IN-PRIVACY v1.0.0]",
            privacy,
        )

    def test_status_catalog_is_0_2_9_restore_privacy(self):
        from downloads import (  # noqa: E402
            GITHUB_REPO,
            MACOS_ZIP_FILENAME,
            RELEASE_TAG,
            RELEASE_VERSION,
            available_downloads,
        )

        self.assertEqual(RELEASE_VERSION, "0.3.3")
        self.assertEqual(RELEASE_TAG, "0.3.3")
        self.assertEqual(GITHUB_REPO, "restore-privacy")
        self.assertEqual(MACOS_ZIP_FILENAME, "restore-privacy-client-0.3.3-macos.zip")
        names = {a.filename for a in available_downloads()}
        self.assertIn("restore-privacy-client-0.3.3-windows-x64-setup.exe", names)
        self.assertIn("restore-privacy-client-0.3.3-macos.zip", names)
        self.assertIn("restore-privacy-client-0.3.3-ios.zip", names)

    def test_handoff_and_release_notes_signed_not_prep_only(self):
        handoff = ROOT / "client_app" / "APPLE_HANDOFF_0.3.3.md"
        notes = ROOT / "scripts" / "RELEASE_NOTES_0.3.3.md"
        self.assertTrue(handoff.is_file())
        self.assertTrue(notes.is_file())
        h = handoff.read_text(encoding="utf-8").lower()
        n = notes.read_text(encoding="utf-8").lower()
        self.assertIn("public package status", h)
        self.assertIn("developer id", h)
        self.assertIn("notariz", h)
        self.assertIn("team-signed", h)
        self.assertNotIn("prep packages only", h)
        self.assertIn("do not treat 0.3.3 public apple assets as prep-only", h)
        self.assertIn("developer id signed + notarized", n)
        # notes text is lowercased above — match product storefront name
        self.assertIn("vpn app shop download catalog (catalog **v0.3.3**", n)


class TestLocal029PackagesIfPresent(unittest.TestCase):
    def test_all_platform_packages_ship_product_node_elgamal_pub(self):
        """Every staged installer must embed product pin pub (not a stale prior key).

        Linux carry-forward historically shipped sha 23136cfe… which breaks HELLO.
        """
        sys.path.insert(0, str(ROOT))
        from client.endpoint import PRODUCT_NODE_ELGAMAL_PUB_SHA256

        product = ROOT / "product" / "node_elgamal.pub"
        self.assertTrue(product.is_file())
        exp = hashlib.sha256(product.read_bytes()).hexdigest()
        self.assertEqual(exp, PRODUCT_NODE_ELGAMAL_PUB_SHA256)
        names = [
            f"restore-privacy-client-{VERSION}-windows-x64-setup.exe",
            f"restore-privacy-client-{VERSION}-android.apk",
            f"restore-privacy-client-{VERSION}-macos.zip",
            f"restore-privacy-client-{VERSION}-ios.zip",
            f"restore-privacy-client-{VERSION}-linux-x64.tar.gz",
        ]
        present = [RELEASE_DIR / n for n in names if (RELEASE_DIR / n).is_file()]
        if len(present) < 5:
            self.skipTest(f"need all five packages under releases/{VERSION}/")

        import tarfile

        for path in present:
            pubs: list[tuple[str, str]] = []
            if path.name.endswith(".exe"):
                # 7z SFX (or PyInstaller): extract and verify coherent frozen-first layout.
                if not shutil.which("7z"):
                    # Fall back: raw product pub blob (legacy onefile)
                    blob = product.read_bytes()
                    if path.read_bytes().count(blob) >= 1:
                        continue
                    self.skipTest("7z required to inspect Windows installer")
                with tempfile.TemporaryDirectory() as td:
                    tdp = Path(td)
                    r = subprocess.run(
                        ["7z", "x", "-y", str(path), f"-o{tdp}"],
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
                    found = list(tdp.rglob("node_elgamal.pub"))
                    self.assertTrue(found, f"{path.name}: no node_elgamal.pub after 7z x")
                    for fp in found:
                        dig = hashlib.sha256(fp.read_bytes()).hexdigest()
                        pubs.append((str(fp.relative_to(tdp)), dig))
                    self.assertFalse(
                        list(tdp.rglob("flyclient_connect.py")),
                        f"{path.name} still embeds flyclient_connect.py",
                    )
                    conn = next(
                        (
                            p
                            for p in tdp.rglob("connect.py")
                            if "client" in str(p)
                        ),
                        None,
                    )
                    if conn is not None:
                        ctext = conn.read_text(encoding="utf-8", errors="replace")
                        self.assertNotIn("flyclient", ctext.lower())
                        self.assertIn("HELLO sent", ctext)
                    # Primary launch: frozen onedir first (not pure-Python embed)
                    run_bat = next(tdp.rglob("run.bat"), None)
                    self.assertIsNotNone(run_bat, f"{path.name}: missing run.bat")
                    bat = run_bat.read_text(encoding="utf-8", errors="replace")
                    self.assertIn("RestorePrivacy.exe", bat)
                    # Frozen path must be primary (first executable launch target)
                    start_idx = bat.lower().find("restoreprivacy.exe")
                    py_idx = bat.lower().find("python\\python.exe")
                    if py_idx >= 0:
                        self.assertLess(
                            start_idx,
                            py_idx,
                            f"{path.name}: run.bat must launch frozen exe before pure-Python",
                        )
                    frozen = list(tdp.rglob("RestorePrivacy.exe"))
                    self.assertTrue(frozen, f"{path.name}: missing RestorePrivacy.exe")
                    # Matched-ABI Tk under _internal (not cross-grafted into python/)
                    tk_files = list(tdp.rglob("_tkinter.pyd"))
                    self.assertTrue(tk_files, f"{path.name}: missing _tkinter.pyd")
                    for tkp in tk_files:
                        # Disallow broken python/_tkinter.pyd next to embed 3.12
                        rel = str(tkp.relative_to(tdp)).replace("\\", "/")
                        if rel.startswith("python/") or "/python/" in rel:
                            self.fail(
                                f"{path.name}: refuse ABI-grafted {rel}; "
                                "use frozen _internal Tk only"
                            )
                        data = tkp.read_bytes()
                        # PE import must match a python3XY.dll ABI string
                        self.assertTrue(
                            b"python314.dll" in data or b"python3" in data,
                            f"{path.name}:{rel} has no python3XY.dll import string",
                        )
                        if b"python314.dll" in data:
                            # Sibling runtime must ship matching dll
                            dlls = list(tdp.rglob("python314.dll"))
                            self.assertTrue(
                                dlls,
                                f"{path.name}: _tkinter imports python314.dll but dll missing",
                            )
                    crypt = list(tdp.rglob("cryptography"))
                    self.assertTrue(crypt, f"{path.name}: missing cryptography")
                    cffi = list(tdp.rglob("_cffi_backend*.pyd")) + list(
                        tdp.rglob("cffi")
                    )
                    self.assertTrue(cffi, f"{path.name}: missing cffi")
            elif path.name.endswith(".tar.gz"):
                with tarfile.open(path, "r:*") as tf:
                    for m in tf.getmembers():
                        if m.name.endswith("node_elgamal.pub") and m.isfile():
                            dig = hashlib.sha256(tf.extractfile(m).read()).hexdigest()
                            pubs.append((m.name, dig))
                        if m.name.endswith("flyclient_connect.py"):
                            self.fail(f"{path.name} embeds {m.name}")
                    # always-HELLO path in connect.py
                    for m in tf.getmembers():
                        if m.name.endswith("client/connect.py"):
                            ctext = tf.extractfile(m).read().decode("utf-8", errors="replace")
                            self.assertNotIn("flyclient", ctext.lower())
                            self.assertIn("HELLO sent", ctext)
                            break
            else:
                with zipfile.ZipFile(path) as zf:
                    for n in zf.namelist():
                        if n.endswith("node_elgamal.pub"):
                            dig = hashlib.sha256(zf.read(n)).hexdigest()
                            pubs.append((n, dig))
                        if "flyclient" in n.lower():
                            self.fail(f"{path.name} embeds {n}")
            self.assertTrue(pubs, f"{path.name}: no node_elgamal.pub")
            for n, dig in pubs:
                self.assertEqual(
                    dig,
                    exp,
                    f"{path.name}:{n} sha {dig} != product pin {exp}",
                )

    def test_local_zips_no_priv_and_macos_developer_id(self):
        if not MACOS_ZIP.is_file() or not IOS_ZIP.is_file():
            self.skipTest("local releases/0.3.3 Apple zips not present")
        for zpath in (MACOS_ZIP, IOS_ZIP):
            with zipfile.ZipFile(zpath) as zf:
                names = zf.namelist()
                self.assertFalse(any(n.endswith(".priv") for n in names), zpath)
                pubs = [n for n in names if n.endswith("node_elgamal.pub")]
                self.assertTrue(pubs, zpath)
                dig = hashlib.sha256(zf.read(pubs[0])).hexdigest()
                self.assertTrue(dig.startswith("1b126abf"), dig)
                sys.path.insert(0, str(ROOT))
                from client.endpoint import PRODUCT_NODE_ELGAMAL_PUB_SHA256

                self.assertEqual(dig, PRODUCT_NODE_ELGAMAL_PUB_SHA256)
        if not shutil.which("codesign"):
            self.skipTest("codesign not available")
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            subprocess.run(
                ["unzip", "-q", "-o", str(MACOS_ZIP), "-d", str(tdp / "mac")],
                check=True,
            )
            app = next((tdp / "mac").rglob("*.app"))
            out = subprocess.check_output(
                ["codesign", "-dv", "--verbose=2", str(app)],
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.assertIn("Developer ID Application: Russell Sneddon (SFCBP95595)", out)
            r = subprocess.run(
                ["codesign", "--verify", "--deep", "--strict", str(app)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            # Host must not carry restricted NE entitlement under Developer ID
            # (that was the 0.3.0 "can't be opened" / SIGKILL 137 root cause).
            ents = subprocess.check_output(
                ["codesign", "-d", "--entitlements", ":-", str(app)],
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.assertNotIn(
                "com.apple.developer.networking.networkextension",
                ents,
                "Developer ID host must not claim networkextension",
            )
            self.assertIn("com.apple.security.cs.allow-jit", ents)
            # Appex still carries NE for Packet Tunnel
            appex = next((tdp / "mac").rglob("*.appex"), None)
            if appex is not None:
                aents = subprocess.check_output(
                    ["codesign", "-d", "--entitlements", ":-", str(appex)],
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                self.assertIn(
                    "com.apple.developer.networking.networkextension", aents
                )
                self.assertIn("packet-tunnel-provider", aents)


if __name__ == "__main__":
    unittest.main()
