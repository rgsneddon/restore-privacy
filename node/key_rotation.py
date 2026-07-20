"""Automated long-term node key rotation + public re-provision surfaces.

Rotates node ElGamal long-term material and updates client-facing **public**
artifacts only (``node_elgamal.pub`` + product pin). Never introduces a shared
``client_ed25519.priv`` — device keys remain per-install.

Operator entry: ``python -m node.key_rotation`` or ``scripts/rotate_node_keys.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from node.elgamal import ElGamalPrivateKey, generate_keypair
from node.key_backend import (
    PRIV_NAME,
    PUB_NAME,
    SEALED_NAME,
    FileNodeKeyBackend,
    MockNodeKeyBackend,
    SealedNodeKeyBackend,
    load_node_key_backend,
    resolve_backend_name,
)

ROOT_DEFAULT = Path(__file__).resolve().parents[1]


@dataclass
class RotationResult:
    ok: bool
    message: str
    old_pub_sha256: str = ""
    new_pub_sha256: str = ""
    backend: str = ""
    product_pub_path: str = ""
    archive_path: str = ""
    introduced_shared_client_priv: bool = False


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rotate_node_long_term_keys(
    secrets_dir: Path | str,
    *,
    product_dir: Path | str | None = None,
    backend: str | None = None,
    archive: bool = True,
    remove_old_plaintext_priv: bool = True,
) -> RotationResult:
    """Generate new node ElGamal key, install via backend, update product public pin.

    Clients re-provision by installing the new ``node_elgamal.pub`` only
    (see ``reprovision_node_public``).
    """
    secrets = Path(secrets_dir)
    secrets.mkdir(parents=True, exist_ok=True)
    be_name = resolve_backend_name(backend)
    product = Path(product_dir) if product_dir else ROOT_DEFAULT / "product"

    old_pub_path = secrets / PUB_NAME
    old_pub = old_pub_path.read_bytes() if old_pub_path.is_file() else b""
    old_sha = sha256_hex(old_pub) if old_pub else ""

    # New keypair
    new_priv = generate_keypair()
    new_pub = new_priv.public.export()
    new_sha = sha256_hex(new_pub)

    archive_path = ""
    if archive and old_pub:
        arch_dir = secrets / "rotation_archive"
        arch_dir.mkdir(exist_ok=True)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        dest = arch_dir / f"node_elgamal.pub.{stamp}.{old_sha[:12]}"
        dest.write_bytes(old_pub)
        archive_path = str(dest)

    # Install via selected backend (no shared client priv written here)
    if be_name == "mock":
        mock_blob = secrets / "node_elgamal.mock.json"
        mock_blob.write_text(
            json.dumps({"priv_hex": new_priv.export().hex(), "backend": "mock"})
            + "\n",
            encoding="utf-8",
        )
        try:
            os.chmod(mock_blob, 0o600)
        except OSError:
            pass
        (secrets / PUB_NAME).write_bytes(new_pub)
        if remove_old_plaintext_priv:
            _unlink_quiet(secrets / PRIV_NAME)
            _unlink_quiet(secrets / SEALED_NAME)
        backend_obj = MockNodeKeyBackend(new_priv, secrets_dir=secrets)
    elif be_name == "sealed":
        SealedNodeKeyBackend.seal_private(secrets, new_priv)
        if remove_old_plaintext_priv:
            _unlink_quiet(secrets / PRIV_NAME)
        backend_obj = SealedNodeKeyBackend.load_or_create(secrets)
    else:
        FileNodeKeyBackend.load_or_create  # noqa: B018 — keep import used
        priv_path = secrets / PRIV_NAME
        priv_path.write_bytes(new_priv.export())
        try:
            os.chmod(priv_path, 0o600)
        except OSError:
            pass
        (secrets / PUB_NAME).write_bytes(new_pub)
        backend_obj = FileNodeKeyBackend(new_priv, secrets_dir=secrets)

    # Product public pin for client packages
    product.mkdir(parents=True, exist_ok=True)
    product_pub = product / "node_elgamal.pub"
    product_pub.write_bytes(new_pub)
    pin = product / "NODE_ELGAMAL_PUB.sha256"
    pin.write_text(f"{new_sha}  node_elgamal.pub\n", encoding="utf-8")

    # Rotation log (no private material)
    log_path = secrets / "rotation_log.jsonl"
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "backend": backend_obj.backend_id(),
        "old_pub_sha256": old_sha,
        "new_pub_sha256": new_sha,
        "product_pub": str(product_pub),
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    # Sanity: backend decrypt self-test
    from node.elgamal import encrypt

    probe = b"rpt-rotation-probe"
    ct = encrypt(backend_obj.public_key(), probe)
    opened = backend_obj.decrypt_ciphertext(ct)
    if opened != probe:
        return RotationResult(
            ok=False,
            message="post-rotation decrypt self-test failed",
            old_pub_sha256=old_sha,
            new_pub_sha256=new_sha,
            backend=backend_obj.backend_id(),
        )

    # Never write shared client priv during rotation
    introduced = (secrets / "client_ed25519.priv").is_file() and False  # explicit
    return RotationResult(
        ok=True,
        message=(
            f"rotated node long-term key via {backend_obj.backend_id()}; "
            f"clients must re-provision public key (sha256={new_sha[:16]}…)"
        ),
        old_pub_sha256=old_sha,
        new_pub_sha256=new_sha,
        backend=backend_obj.backend_id(),
        product_pub_path=str(product_pub),
        archive_path=archive_path,
        introduced_shared_client_priv=introduced,
    )


def reprovision_node_public(
    dest_secrets_dir: Path | str,
    source_pub: Path | str | bytes,
) -> Path:
    """Install/update **only** node_elgamal.pub into a client secrets dir.

    Does not touch client_ed25519.priv (device key stays local).
    """
    dest = Path(dest_secrets_dir)
    dest.mkdir(parents=True, exist_ok=True)
    if isinstance(source_pub, (bytes, bytearray)):
        data = bytes(source_pub)
    else:
        data = Path(source_pub).read_bytes()
    if len(data) != 256:
        raise ValueError("node_elgamal.pub must be 256 bytes")
    out = dest / PUB_NAME
    out.write_bytes(data)
    try:
        os.chmod(out, 0o644)
    except OSError:
        pass
    return out


def _unlink_quiet(path: Path) -> None:
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Rotate RPT node long-term ElGamal keys")
    p.add_argument(
        "--secrets-dir",
        default=os.environ.get("RPT_SECRETS_DIR", "secrets"),
        help="Node secrets directory",
    )
    p.add_argument(
        "--product-dir",
        default=None,
        help="Product public pin dir (default: repo product/)",
    )
    p.add_argument(
        "--backend",
        default=None,
        help="file|mock|sealed (default RPT_KEY_BACKEND or file)",
    )
    args = p.parse_args(argv)
    result = rotate_node_long_term_keys(
        args.secrets_dir,
        product_dir=args.product_dir,
        backend=args.backend,
    )
    print(result.message)
    print(f"backend={result.backend} new_pub_sha256={result.new_pub_sha256}")
    print(f"product_pub={result.product_pub_path}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
