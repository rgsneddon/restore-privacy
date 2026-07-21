"""Windows secrets resolution + provision â€” no 'copy from the node' dead-end when keys present."""

from __future__ import annotations

import os
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
    SecretsError,
    candidate_secrets_dirs,
    dir_has_client_secrets,
    load_client_private_key,
    load_node_elgamal_public,
    provision_secrets_files,
    resolve_secrets_dir,
    secrets_present,
)
from client.connect import ConnectState, RptClient  # noqa: E402
from node.elgamal import generate_keypair  # noqa: E402
from node.handshake import generate_client_admission_keypair, ed25519_priv_raw  # noqa: E402


def _write_valid_secrets(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    cpriv, _ = generate_client_admission_keypair()
    (d / CLIENT_PRIV_NAME).write_bytes(ed25519_priv_raw(cpriv))
    node = generate_keypair()
    (d / NODE_PUB_NAME).write_bytes(node.public.export())


class TestSecretsResolveAndLoad(unittest.TestCase):
    def test_load_succeeds_from_temp_dir(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_valid_secrets(d)
            self.assertTrue(dir_has_client_secrets(d))
            resolved = resolve_secrets_dir(d)
            self.assertEqual(resolved, d)
            key = load_client_private_key(d)
            pub = load_node_elgamal_public(d)
            self.assertIsNotNone(key)
            self.assertIsNotNone(pub)
            self.assertTrue(secrets_present(d))

    def test_missing_dir_fails_with_filenames(self):
        with tempfile.TemporaryDirectory() as td:
            empty = Path(td) / "empty"
            empty.mkdir()
            # Explicit empty dir with no node pub cannot bootstrap
            with self.assertRaises(SecretsError) as ctx:
                resolve_secrets_dir(empty)
            msg = str(ctx.exception)
            self.assertIn(NODE_PUB_NAME, msg)

    def test_missing_global_message_is_windows_oriented(self):
        # Point candidates at empty locations only; no node pub available
        # (including no product/ pin — product exists in-repo for real installs).
        with tempfile.TemporaryDirectory() as td:
            empty = Path(td)
            with mock.patch(
                "client.secrets_loader.candidate_secrets_dirs",
                return_value=[empty / "nope"],
            ), mock.patch(
                "client.secrets_loader.preferred_writable_secrets_dir",
                return_value=empty / "writable",
            ), mock.patch(
                "client.secrets_loader._find_node_pub",
                return_value=None,
            ), mock.patch(
                "client.secrets_loader.sync_product_node_pub_into",
                return_value=False,
            ):
                with self.assertRaises(SecretsError) as ctx:
                    resolve_secrets_dir()
                msg = str(ctx.exception)
                self.assertIn(NODE_PUB_NAME, msg)

    def test_candidate_dirs_include_windows_install_and_user(self):
        dirs = [str(p).replace("\\", "/").lower() for p in candidate_secrets_dirs()]
        joined = " ".join(dirs)
        self.assertTrue(
            any("restoreprivacy" in d and "secrets" in d for d in dirs)
            or "programs" in joined
            or ".restore-privacy" in joined
        )
        self.assertTrue(any(".restore-privacy" in d for d in dirs))

    def test_provision_copies_only_product_keys(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            dest = Path(td) / "dest"
            _write_valid_secrets(src)
            # decoy node private key must not be provisioned
            (src / "node_elgamal.priv").write_bytes(b"\x00" * 256)
            written = provision_secrets_files(dest, source_dir=src)
            # Default: only public node key (device Ed25519 generated on first run)
            self.assertIn(NODE_PUB_NAME, written)
            self.assertNotIn(CLIENT_PRIV_NAME, written)
            self.assertFalse((dest / CLIENT_PRIV_NAME).is_file())
            self.assertTrue((dest / NODE_PUB_NAME).is_file())
            self.assertFalse((dest / "node_elgamal.priv").is_file())


class TestConnectUsesSecrets(unittest.TestCase):
    def test_connect_with_secrets_present_not_missing_secrets_error(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_valid_secrets(d)
            client = RptClient(
                secrets_dir=d,
            )
            # May fail later on network/handshake, but must not be the missing-secrets message
            try:
                result = client.connect(timeout=0.5)
                self.assertNotIn("No client secrets found", result.message)
                self.assertNotIn("Copy from the node", result.message)
            finally:
                try:
                    client.disconnect()
                except Exception:
                    pass

    def test_connect_without_secrets_reports_secrets_failure(self):
        with tempfile.TemporaryDirectory() as td:
            empty = Path(td) / "nosec"
            empty.mkdir()
            # Explicit empty dir: no node_elgamal.pub → bootstrap fails closed
            client = RptClient(
                secrets_dir=empty,
            )
            try:
                result = client.connect(timeout=0.5)
                self.assertFalse(result.ok)
                self.assertEqual(result.state, ConnectState.ERROR)
                self.assertTrue(
                    "secrets" in result.message.lower()
                    or NODE_PUB_NAME in result.message
                    or CLIENT_PRIV_NAME in result.message
                    or "node" in result.message.lower()
                )
            finally:
                try:
                    client.disconnect()
                except Exception:
                    pass


class TestInstallerAndBuildRecipe(unittest.TestCase):
    def test_installer_provisions_secrets(self):
        inst = (ROOT / "client" / "windows" / "installer.py").read_text(encoding="utf-8")
        self.assertIn("_provision_secrets", inst)
        self.assertIn("node_elgamal.pub", inst)
        self.assertIn("node_elgamal.priv", inst)  # must mention to exclude
        self.assertIn("device Ed25519", inst)
        self.assertIn('VERSION = "0.2.9"', inst)

    def test_build_script_injects_secrets(self):
        script = (ROOT / "scripts" / "build_release_0.2.9.py").read_text(encoding="utf-8")
        self.assertIn("inject_product_secrets", script)
        self.assertIn("node_elgamal.pub", script)
        self.assertIn('VERSION = "0.2.9"', script)
        # Public packages must not embed shared client priv
        lower = script.lower()
        self.assertTrue(
            "never a shared" in lower or "device ed25519" in lower,
            "build recipe must describe per-device keys / no shared client priv",
        )


if __name__ == "__main__":
    unittest.main()
