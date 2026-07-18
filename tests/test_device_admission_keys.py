"""Per-device Ed25519 keys: bootstrap, no shared priv packaging, handshake enrollment."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.secrets_loader import (  # noqa: E402
    CLIENT_PRIV_NAME,
    NODE_PUB_NAME,
    ensure_device_admission_key,
    generate_and_persist_device_key,
    is_package_readonly_secrets_dir,
    packaging_must_not_ship_shared_client_priv,
    provision_secrets_files,
)
from client.windows.installer import (  # noqa: E402
    _copy_tree,
    _provision_secrets,
    strip_all_private_keys,
)
from node.handshake import ed25519_priv_raw  # noqa: E402
from node.elgamal import generate_keypair  # noqa: E402
from node.handshake import (  # noqa: E402
    AdmissionError,
    NodeHandshake,
    build_client_hello,
    ed25519_pub_raw,
    generate_client_admission_keypair,
    node_complete_hello,
    persist_enrolled_client_pub,
)


class TestDeviceKeyBootstrap(unittest.TestCase):
    def test_first_run_generates_key_second_reuses_same_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            node = generate_keypair()
            (d / NODE_PUB_NAME).write_bytes(node.public.export())
            # No client priv yet
            self.assertFalse((d / CLIENT_PRIV_NAME).is_file())
            s1 = ensure_device_admission_key(d)
            self.assertEqual(s1, d)
            priv1 = (d / CLIENT_PRIV_NAME).read_bytes()
            self.assertEqual(len(priv1), 32)
            # Second call must not rotate the key
            s2 = ensure_device_admission_key(d)
            self.assertEqual(s2, d)
            priv2 = (d / CLIENT_PRIV_NAME).read_bytes()
            self.assertEqual(priv1, priv2)

    def test_generate_and_persist_writes_priv_and_pub(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            key = generate_and_persist_device_key(d)
            self.assertTrue((d / CLIENT_PRIV_NAME).is_file())
            self.assertEqual((d / CLIENT_PRIV_NAME).stat().st_size, 32)
            self.assertEqual(len(ed25519_pub_raw(key.public_key())), 32)


class TestNoSharedPrivPackaging(unittest.TestCase):
    def test_policy_flag(self):
        self.assertTrue(packaging_must_not_ship_shared_client_priv())

    def test_provision_default_skips_client_priv(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            dest = Path(td) / "dest"
            src.mkdir()
            dest.mkdir()
            node = generate_keypair()
            cpriv, _ = generate_client_admission_keypair()
            (src / CLIENT_PRIV_NAME).write_bytes(ed25519_priv_raw(cpriv))
            (src / NODE_PUB_NAME).write_bytes(node.public.export())
            written = provision_secrets_files(dest, source_dir=src)
            self.assertIn(NODE_PUB_NAME, written)
            self.assertNotIn(CLIENT_PRIV_NAME, written)
            self.assertTrue((dest / NODE_PUB_NAME).is_file())
            self.assertFalse((dest / CLIENT_PRIV_NAME).is_file())

    def test_windows_copy_tree_and_provision_strip_shared_priv(self):
        """Real installer helpers: shared priv in payload never lands in install tree."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = root / "payload"
            secrets = payload / "secrets"
            internal = payload / "_internal" / "secrets"
            secrets.mkdir(parents=True)
            internal.mkdir(parents=True)
            node = generate_keypair()
            shared = b"\xab" * 32
            (secrets / NODE_PUB_NAME).write_bytes(node.public.export())
            (secrets / CLIENT_PRIV_NAME).write_bytes(shared)
            (internal / NODE_PUB_NAME).write_bytes(node.public.export())
            (internal / CLIENT_PRIV_NAME).write_bytes(shared)
            (payload / "RestorePrivacy.exe").write_bytes(b"MZ")

            install = root / "install"
            _copy_tree(payload, install)
            # _copy_tree must ignore all .priv
            self.assertFalse(any(install.rglob("*.priv")))
            # Plant a leftover under _internal as if an older tree copied it
            leftover = install / "_internal" / "secrets"
            leftover.mkdir(parents=True, exist_ok=True)
            (leftover / CLIENT_PRIV_NAME).write_bytes(shared)
            written = _provision_secrets(payload, install)
            self.assertTrue(any(NODE_PUB_NAME in w for w in written) or (install / "secrets" / NODE_PUB_NAME).is_file())
            # Provision + strip removes every .priv under install (incl. _internal)
            self.assertFalse(
                any(install.rglob("*.priv")),
                f"leftover privs: {list(install.rglob('*.priv'))}",
            )
            self.assertTrue((install / "secrets" / NODE_PUB_NAME).is_file())

    def test_bootstrap_ignores_package_internal_shared_priv(self):
        """Shared priv only under _internal must not be adopted; generate into writable."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            package = root / "pkg" / "_internal" / "secrets"
            package.mkdir(parents=True)
            writable = root / "writable"
            writable.mkdir()
            node = generate_keypair()
            shared = b"\xcd" * 32
            (package / NODE_PUB_NAME).write_bytes(node.public.export())
            (package / CLIENT_PRIV_NAME).write_bytes(shared)
            self.assertTrue(is_package_readonly_secrets_dir(package))

            with mock.patch(
                "client.secrets_loader.candidate_secrets_dirs",
                return_value=[package, writable],
            ), mock.patch(
                "client.secrets_loader.preferred_writable_secrets_dir",
                return_value=writable,
            ):
                # seed node pub into writable via find
                (writable / NODE_PUB_NAME).write_bytes(node.public.export())
                dest = ensure_device_admission_key()
            self.assertEqual(dest, writable)
            device = (writable / CLIENT_PRIV_NAME).read_bytes()
            self.assertEqual(len(device), 32)
            self.assertNotEqual(device, shared)

    def test_android_assets_have_no_client_priv(self):
        assets = (
            ROOT
            / "client_app"
            / "android"
            / "app"
            / "src"
            / "main"
            / "assets"
            / "secrets"
        )
        self.assertFalse(
            (assets / CLIENT_PRIV_NAME).exists(),
            f"shared {CLIENT_PRIV_NAME} must not be in APK assets",
        )
        # After inject recipe, only node pub (or empty) is allowed
        gradle = (
            ROOT / "client_app" / "android" / "app" / "build.gradle.kts"
        ).read_text(encoding="utf-8")
        self.assertIn('listOf("node_elgamal.pub")', gradle)
        self.assertNotIn('listOf("client_ed25519.priv"', gradle)

    def test_android_service_generates_device_key(self):
        svc = (
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
            / "RptVpnService.kt"
        ).read_text(encoding="utf-8")
        self.assertIn("generateDeviceEd25519PrivateKey", svc)
        self.assertNotIn(
            'assets.open("secrets/client_ed25519.priv")',
            svc,
        )

    def test_inject_apple_only_node_pub(self):
        script = (ROOT / "scripts" / "inject_apple_secrets.py").read_text(encoding="utf-8")
        self.assertIn("node_elgamal.pub", script)
        self.assertIn("never a shared", script.lower())
        self.assertIn('dest.glob("*.priv")', script)

    def test_build_inject_strips_internal_priv(self):
        """Shipped inject_product_secrets removes priv under _internal/secrets."""
        import importlib.util

        path = ROOT / "scripts" / "build_release_0.0.8.py"
        spec = importlib.util.spec_from_file_location("br08", path)
        assert spec and spec.loader
        m = importlib.util.module_from_spec(spec)
        # Avoid running main; just load for inject_product_secrets
        # Node pub required from repo secrets
        if not (ROOT / "secrets" / NODE_PUB_NAME).is_file():
            self.skipTest("repo secrets/node_elgamal.pub missing")
        spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as td:
            tree = Path(td)
            top = tree / "secrets"
            internal = tree / "_internal" / "secrets"
            top.mkdir(parents=True)
            internal.mkdir(parents=True)
            shared = b"\xef" * 32
            (top / CLIENT_PRIV_NAME).write_bytes(shared)
            (internal / CLIENT_PRIV_NAME).write_bytes(shared)
            (internal / "node_elgamal.priv").write_bytes(b"\x00" * 64)
            m.inject_product_secrets(tree)
            self.assertFalse(any(tree.rglob("*.priv")), list(tree.rglob("*.priv")))
            self.assertTrue((tree / "secrets" / NODE_PUB_NAME).is_file())


class TestDeviceKeyHandshake(unittest.TestCase):
    def test_fresh_device_key_admitted_when_unknown_allowed(self):
        node_priv = generate_keypair()
        device_priv, device_pub = generate_client_admission_keypair()
        enrolled: list[bytes] = []

        def on_enroll(pub: bytes) -> None:
            enrolled.append(pub)

        # Empty allow-list + admit unknown devices (free product)
        hs = NodeHandshake(
            node_priv,
            [],
            admit_unknown_devices=True,
            on_enroll=on_enroll,
        )
        frame, _nonce, client_pub = build_client_hello(device_priv, node_priv.public)
        self.assertEqual(client_pub, ed25519_pub_raw(device_pub))
        reply, result = node_complete_hello(hs, frame, "10.88.0.9")
        self.assertEqual(len(result.session_id), 8)
        self.assertEqual(result.client_pub, client_pub)
        self.assertIn(client_pub, hs.authorized)
        self.assertEqual(enrolled, [client_pub])
        self.assertTrue(len(reply) > 20)

    def test_unknown_device_rejected_when_enrollment_disabled(self):
        node_priv = generate_keypair()
        good_priv, good_pub = generate_client_admission_keypair()
        bad_priv, _ = generate_client_admission_keypair()
        hs = NodeHandshake(
            node_priv,
            [ed25519_pub_raw(good_pub)],
            admit_unknown_devices=False,
        )
        frame, _, _ = build_client_hello(bad_priv, node_priv.public)
        with self.assertRaises(AdmissionError):
            node_complete_hello(hs, frame, "10.88.0.3")

    def test_persist_enrolled_pub(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            pub = b"\x11" * 32
            persist_enrolled_client_pub(d, pub)
            persist_enrolled_client_pub(d, pub)  # idempotent
            data = (d / "authorized_clients.pub").read_bytes()
            self.assertEqual(data.count(pub), 1)


class TestDocsNoSharedPriv(unittest.TestCase):
    def test_privacy_and_readme_describe_device_keys(self):
        privacy = (ROOT / "PRIVACY_POLICY.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("first run", privacy.lower())
        self.assertIn("device", privacy.lower())
        self.assertNotIn(
            "may include **product client admission keys** (`client_ed25519.priv` + `node_elgamal.pub`)",
            privacy,
        )
        self.assertIn("generates its own Ed25519 device key", readme)
        self.assertIn("do **not** ship a shared", readme)


if __name__ == "__main__":
    unittest.main()
