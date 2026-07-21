"""Product Connect + node must be pre-RUST RPT2 (Python/Flutter/Kotlin/Swift).

Gates that this monorepo is the restore-privacy Python RPT product line — not
RUST-IN-PRIVACY residual (Cargo crates / rpt-ffi / librpt_ffi as Connect path).
"""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestNoRustProductTree(unittest.TestCase):
    def test_no_cargo_or_crates_in_product_root(self):
        self.assertFalse((ROOT / "Cargo.toml").is_file())
        self.assertFalse((ROOT / "crates").is_dir())
        # No product .rs sources outside build caches
        rs = [
            p
            for p in ROOT.rglob("*.rs")
            if ".git" not in p.parts
            and "build" not in p.parts
            and "DerivedData" not in p.parts
            and ".build" not in p.parts
        ]
        self.assertEqual(rs, [], msg=f"unexpected Rust sources: {rs[:10]}")

    def test_catalog_identity_is_restore_privacy_not_rust_in_privacy(self):
        sys_path_insert = str(ROOT / "status_page")
        import sys

        if sys_path_insert not in sys.path:
            sys.path.insert(0, sys_path_insert)
        import app as status_app  # noqa: E402
        from downloads import (  # noqa: E402
            GITHUB_REPO,
            PRODUCT_CATALOG_URL,
            RELEASE_VERSION,
            render_download_section_html,
        )

        self.assertEqual(GITHUB_REPO, "restore-privacy")
        self.assertEqual(RELEASE_VERSION, (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip())
        self.assertIn("restoreprivacy.online", PRODUCT_CATALOG_URL)
        self.assertNotIn("RUST-IN-PRIVACY", PRODUCT_CATALOG_URL)
        self.assertNotIn("RUST-IN-PRIVACY", status_app.GITHUB_BLOB_MAIN)
        self.assertNotIn("RUST-IN-PRIVACY", status_app.PRODUCT_REPO_URL)
        html = render_download_section_html()
        self.assertNotIn("RUST-IN-PRIVACY", html)
        self.assertNotIn("rust-repo-link", html)
        self.assertNotIn("rpt-ffi", html.lower())
        self.assertNotIn("librpt_ffi", html.lower())


class TestConnectPathsPreRust(unittest.TestCase):
    def test_python_rpt_client_is_connect_entry(self):
        connect = (ROOT / "client" / "connect.py").read_text(encoding="utf-8")
        self.assertIn("class RptClient", connect)
        self.assertIn("build_client_hello", connect)
        self.assertNotIn("rpt_ffi", connect)
        self.assertNotIn("librpt", connect)
        self.assertNotIn("cdylib", connect)

    def test_windows_linux_residual_are_python_full_tunnel(self):
        win = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(encoding="utf-8")
        linux = (ROOT / "client" / "linux" / "tunnel_linux.py").read_text(encoding="utf-8")
        self.assertIn("start_full_tunnel", win)
        self.assertIn("Wintun", win)
        self.assertIn("start_full_tunnel", linux)
        self.assertIn("dual /1", linux)
        for text in (win, linux):
            self.assertNotIn("rpt_ffi", text)
            self.assertNotIn("librpt_ffi", text)

    def test_android_engine_is_kotlin_rpt2_not_rust_ffi(self):
        eng = (
            ROOT
            / "client_app"
            / "android"
            / "app"
            / "src"
            / "main"
            / "kotlin"
            / "com"
            / "restoreprivacy"
            / "restore_privacy_client"
            / "RptClientEngine.kt"
        )
        self.assertTrue(eng.is_file())
        text = eng.read_text(encoding="utf-8")
        self.assertIn("RptClientEngine", text)
        self.assertIn("pfs-x25519", text)
        self.assertNotIn("System.loadLibrary", text)
        self.assertNotIn("librpt", text)
        self.assertNotIn("rpt_ffi", text)

    def test_apple_residual_is_swift_rpt2_package(self):
        pkg = ROOT / "client_app" / "apple_shared" / "Rpt2" / "Package.swift"
        self.assertTrue(pkg.is_file())
        text = pkg.read_text(encoding="utf-8")
        self.assertIn('name: "Rpt2"', text)
        self.assertNotIn("rpt_ffi", text)
        self.assertNotIn("librpt", text)


class TestNodeIsPythonRpt2(unittest.TestCase):
    def test_node_main_is_python_server(self):
        main = (ROOT / "node" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("from .server import main", main)
        self.assertFalse((ROOT / "node" / "Cargo.toml").is_file())
        install = (ROOT / "node" / "install.sh").read_text(encoding="utf-8")
        self.assertIn("python -m node.server", install)
        self.assertNotIn("rpt-node --", install)  # not a Rust binary invocation
        # systemd unit name rpt-node is fine; ExecStart must be Python
        self.assertIn("/venv/bin/python -m node.server", install)

    def test_product_node_pin_matches_endpoint(self):
        from client.endpoint import (  # noqa: WPS433
            PRODUCT_NODE_ELGAMAL_PUB_SHA256,
            product_node_elgamal_pub_path,
        )

        pub = product_node_elgamal_pub_path()
        self.assertTrue(pub.is_file())
        h = hashlib.sha256(pub.read_bytes()).hexdigest()
        self.assertEqual(h, PRODUCT_NODE_ELGAMAL_PUB_SHA256)


if __name__ == "__main__":
    unittest.main()
