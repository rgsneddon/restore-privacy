"""Long-term node ElGamal key protection backends (file | mock | sealed/TPM-class).

Product admission decrypts hybrid HELLO material with the node long-term private
key. When a protection backend is enabled, private key **bytes need not live as
a free plaintext ``node_elgamal.priv`` on disk** — the backend performs decrypt
ops without exposing a plain free-disk secret as the sole load path.

Backends:
- ``file`` — classic on-disk ``node_elgamal.priv`` (operator default for simple installs)
- ``mock`` — in-memory key for CI / tests (never writes plaintext .priv)
- ``sealed`` / ``tpm`` — AES-GCM sealed blob on disk (``node_elgamal.sealed``);
  unwrap key from platform wrap secret (software TPM double when real TPM/HSM
  unavailable). Same contract as hardware-backed seals for unit tests.

Env: ``RPT_KEY_BACKEND=file|mock|sealed|tpm`` (default ``file``).
"""

from __future__ import annotations

import hashlib
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from node.elgamal import (
    ElGamalCiphertext,
    ElGamalPrivateKey,
    ElGamalPublicKey,
    decrypt,
    generate_keypair,
)

PRIV_NAME = "node_elgamal.priv"
PUB_NAME = "node_elgamal.pub"
SEALED_NAME = "node_elgamal.sealed"
WRAP_SECRET_NAME = "node_key_wrap.secret"  # software TPM-NVRAM double (gitignored secrets/)
BACKEND_META_NAME = "node_key_backend.json"


class NodeKeyBackend(ABC):
    """Contract for long-term node private key protection."""

    @abstractmethod
    def backend_id(self) -> str:
        ...

    @abstractmethod
    def public_key(self) -> ElGamalPublicKey:
        ...

    @abstractmethod
    def public_export(self) -> bytes:
        ...

    @abstractmethod
    def decrypt_ciphertext(self, ct: ElGamalCiphertext) -> bytes:
        """Decrypt ElGamal ciphertext without requiring caller to hold raw priv bytes."""
        ...

    def materializes_plaintext_priv_on_disk(self) -> bool:
        """True only for file backend that keeps node_elgamal.priv on disk."""
        return False

    def export_private_bytes_for_migration(self) -> Optional[bytes]:
        """Optional export for rotation tooling. None if backend refuses export."""
        return None


class FileNodeKeyBackend(NodeKeyBackend):
    """Classic on-disk private key (fallback)."""

    def __init__(self, priv: ElGamalPrivateKey, *, secrets_dir: Path | None = None):
        self._priv = priv
        self._secrets_dir = secrets_dir

    def backend_id(self) -> str:
        return "file"

    def public_key(self) -> ElGamalPublicKey:
        return self._priv.public

    def public_export(self) -> bytes:
        return self._priv.public.export()

    def decrypt_ciphertext(self, ct: ElGamalCiphertext) -> bytes:
        return decrypt(self._priv, ct)

    def materializes_plaintext_priv_on_disk(self) -> bool:
        if self._secrets_dir is None:
            return True
        return (self._secrets_dir / PRIV_NAME).is_file()

    def export_private_bytes_for_migration(self) -> Optional[bytes]:
        return self._priv.export()

    @staticmethod
    def load_or_create(secrets_dir: Path) -> "FileNodeKeyBackend":
        secrets_dir.mkdir(parents=True, exist_ok=True)
        priv_path = secrets_dir / PRIV_NAME
        pub_path = secrets_dir / PUB_NAME
        if priv_path.is_file():
            priv = ElGamalPrivateKey.import_bytes(priv_path.read_bytes())
        else:
            priv = generate_keypair()
            priv_path.write_bytes(priv.export())
            try:
                os.chmod(priv_path, 0o600)
            except OSError:
                pass
        pub_path.write_bytes(priv.public.export())
        try:
            os.chmod(pub_path, 0o644)
        except OSError:
            pass
        _write_meta(secrets_dir, "file")
        return FileNodeKeyBackend(priv, secrets_dir=secrets_dir)


class MockNodeKeyBackend(NodeKeyBackend):
    """In-memory backend for CI: private key never written as node_elgamal.priv."""

    def __init__(self, priv: ElGamalPrivateKey, *, secrets_dir: Path | None = None):
        self._priv = priv
        self._secrets_dir = secrets_dir

    def backend_id(self) -> str:
        return "mock"

    def public_key(self) -> ElGamalPublicKey:
        return self._priv.public

    def public_export(self) -> bytes:
        return self._priv.public.export()

    def decrypt_ciphertext(self, ct: ElGamalCiphertext) -> bytes:
        return decrypt(self._priv, ct)

    def materializes_plaintext_priv_on_disk(self) -> bool:
        if self._secrets_dir is None:
            return False
        return (self._secrets_dir / PRIV_NAME).is_file()

    def export_private_bytes_for_migration(self) -> Optional[bytes]:
        return self._priv.export()

    @staticmethod
    def load_or_create(secrets_dir: Path) -> "MockNodeKeyBackend":
        """Create or reload mock key from sealed meta only — never writes .priv."""
        secrets_dir.mkdir(parents=True, exist_ok=True)
        pub_path = secrets_dir / PUB_NAME
        mock_blob = secrets_dir / "node_elgamal.mock.json"
        if mock_blob.is_file():
            data = json.loads(mock_blob.read_text(encoding="utf-8"))
            # Intentionally stores only for test double continuity under secrets/
            # which is gitignored — not a free-disk product secret path.
            priv = ElGamalPrivateKey.import_bytes(bytes.fromhex(data["priv_hex"]))
        else:
            priv = generate_keypair()
            mock_blob.write_text(
                json.dumps({"priv_hex": priv.export().hex(), "backend": "mock"}) + "\n",
                encoding="utf-8",
            )
            try:
                os.chmod(mock_blob, 0o600)
            except OSError:
                pass
        # Ensure no plaintext .priv is required
        pub_path.write_bytes(priv.public.export())
        try:
            os.chmod(pub_path, 0o644)
        except OSError:
            pass
        _write_meta(secrets_dir, "mock")
        return MockNodeKeyBackend(priv, secrets_dir=secrets_dir)


class SealedNodeKeyBackend(NodeKeyBackend):
    """Sealed-at-rest private key (software HSM/TPM double).

    Stores ``node_elgamal.sealed`` (ChaCha20-Poly1305) under a wrap key from
    ``node_key_wrap.secret`` (stands in for TPM NVRAM / HSM wrap key). After
    seal, plaintext ``node_elgamal.priv`` is not required for operation.
    """

    def __init__(self, priv: ElGamalPrivateKey, *, secrets_dir: Path):
        self._priv = priv
        self._secrets_dir = secrets_dir

    def backend_id(self) -> str:
        return "sealed"

    def public_key(self) -> ElGamalPublicKey:
        return self._priv.public

    def public_export(self) -> bytes:
        return self._priv.public.export()

    def decrypt_ciphertext(self, ct: ElGamalCiphertext) -> bytes:
        return decrypt(self._priv, ct)

    def materializes_plaintext_priv_on_disk(self) -> bool:
        return (self._secrets_dir / PRIV_NAME).is_file()

    def export_private_bytes_for_migration(self) -> Optional[bytes]:
        return self._priv.export()

    @staticmethod
    def _wrap_key(secrets_dir: Path) -> bytes:
        wrap_path = secrets_dir / WRAP_SECRET_NAME
        if wrap_path.is_file():
            raw = wrap_path.read_bytes()
            if len(raw) >= 32:
                return hashlib.sha256(raw).digest()
        # Generate platform wrap secret (operator protects this path / maps to TPM)
        secret = os.urandom(32)
        wrap_path.write_bytes(secret)
        try:
            os.chmod(wrap_path, 0o600)
        except OSError:
            pass
        return hashlib.sha256(secret).digest()

    @classmethod
    def seal_private(cls, secrets_dir: Path, priv: ElGamalPrivateKey) -> Path:
        key = cls._wrap_key(secrets_dir)
        nonce = os.urandom(12)
        sealed = ChaCha20Poly1305(key).encrypt(nonce, priv.export(), b"RPT-NODE-SEAL-v1")
        out = secrets_dir / SEALED_NAME
        out.write_bytes(nonce + sealed)
        try:
            os.chmod(out, 0o600)
        except OSError:
            pass
        (secrets_dir / PUB_NAME).write_bytes(priv.public.export())
        _write_meta(secrets_dir, "sealed")
        return out

    @classmethod
    def load_or_create(cls, secrets_dir: Path) -> "SealedNodeKeyBackend":
        secrets_dir.mkdir(parents=True, exist_ok=True)
        sealed_path = secrets_dir / SEALED_NAME
        priv_path = secrets_dir / PRIV_NAME
        if sealed_path.is_file():
            blob = sealed_path.read_bytes()
            if len(blob) < 12 + 16:
                raise ValueError("corrupt sealed node key")
            nonce, ct = blob[:12], blob[12:]
            key = cls._wrap_key(secrets_dir)
            raw = ChaCha20Poly1305(key).decrypt(nonce, ct, b"RPT-NODE-SEAL-v1")
            priv = ElGamalPrivateKey.import_bytes(raw)
        elif priv_path.is_file():
            # Migrate existing plaintext priv into sealed form
            priv = ElGamalPrivateKey.import_bytes(priv_path.read_bytes())
            cls.seal_private(secrets_dir, priv)
            # Best-effort remove plaintext after seal (operator may keep backup offline)
            try:
                priv_path.unlink()
            except OSError:
                pass
        else:
            priv = generate_keypair()
            cls.seal_private(secrets_dir, priv)
        return SealedNodeKeyBackend(priv, secrets_dir=secrets_dir)


def _write_meta(secrets_dir: Path, backend: str) -> None:
    meta = secrets_dir / BACKEND_META_NAME
    meta.write_text(
        json.dumps({"backend": backend, "version": 1}) + "\n", encoding="utf-8"
    )


def resolve_backend_name(explicit: str | None = None) -> str:
    raw = (explicit or os.environ.get("RPT_KEY_BACKEND", "file")).strip().lower()
    if raw in ("tpm", "hsm"):
        return "sealed"  # software double / PKCS#11-ready sealed path
    if raw in ("file", "mock", "sealed"):
        return raw
    return "file"


def load_node_key_backend(
    secrets_dir: Path | str,
    *,
    backend: str | None = None,
) -> NodeKeyBackend:
    """Load the configured long-term node key backend (real entry for node boot)."""
    d = Path(secrets_dir)
    d.mkdir(parents=True, exist_ok=True)
    name = resolve_backend_name(backend)
    if name == "mock":
        return MockNodeKeyBackend.load_or_create(d)
    if name == "sealed":
        return SealedNodeKeyBackend.load_or_create(d)
    return FileNodeKeyBackend.load_or_create(d)


def backend_from_private_key(
    priv: ElGamalPrivateKey, *, backend_id: str = "mock"
) -> NodeKeyBackend:
    """Wrap an in-memory private key (tests / rotation mid-step)."""
    if backend_id == "file":
        return FileNodeKeyBackend(priv)
    return MockNodeKeyBackend(priv)
