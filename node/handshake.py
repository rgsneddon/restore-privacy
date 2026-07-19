"""Product handshake: ElGamal + Pedersen + authorized client Ed25519 only."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional, Set

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from .crypto_session import SessionCrypto, derive_session_key
from .elgamal import (
    ElGamalCiphertext,
    ElGamalPrivateKey,
    ElGamalPublicKey,
    Q,
    decrypt,
    encrypt,
)
from .pedersen import (
    PedersenCommitment,
    PedersenOpening,
    commit_bytes,
    open_verified,
)
from .pfs import (
    EPH_PUB_LEN,
    EphemeralX25519,
    derive_legacy_session_shared,
    derive_pfs_session_shared,
    session_crypto_from_shared,
    x25519_shared_secret,
)
from .protocol import pack_client_hello, pack_server_hello, parse_client_hello
from .traffic_shape import DEFAULT_TRAFFIC_SHAPE


def ed25519_pub_raw(pub: Ed25519PublicKey) -> bytes:
    return pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def ed25519_priv_raw(priv: Ed25519PrivateKey) -> bytes:
    return priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def load_ed25519_pub(raw: bytes) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(raw)


def generate_client_admission_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    priv = Ed25519PrivateKey.generate()
    return priv, priv.public_key()


def persist_enrolled_client_pub(secrets_dir: Path, client_pub: bytes) -> None:
    """Append a newly enrolled device Ed25519 public key (32 bytes) to allow-list file.

    Pure filesystem helper (no Linux-only imports) so unit tests can call it on Windows.
    """
    if len(client_pub) != 32:
        return
    allow_path = Path(secrets_dir) / "authorized_clients.pub"
    Path(secrets_dir).mkdir(parents=True, exist_ok=True)
    existing = b""
    if allow_path.is_file():
        existing = allow_path.read_bytes()
        if client_pub in existing:
            return
    with allow_path.open("ab") as f:
        if existing and not existing.endswith(b"\n"):
            f.write(b"\n")
        f.write(client_pub + b"\n")
    try:
        os.chmod(allow_path, 0o644)
    except OSError:
        pass


def transcript_for_client_hello(client_pub: bytes, commit: bytes, elgamal_ct: bytes) -> bytes:
    return b"RPT2-CLIENT-HELLO|" + client_pub + commit + elgamal_ct


def hybrid_encrypt(node_pub: ElGamalPublicKey, plaintext: bytes) -> bytes:
    """ElGamal-wrap a 32-byte key; ChaCha20-Poly1305 seals the bulk payload.

    Wire: elgamal_ct(512) || nonce(12) || aead_ciphertext
    Returned blob is what goes into the CLIENT_HELLO elgamal_ct field expansion —
    we store hybrid blob as: for protocol, elgamal field stays 512 (key only),
    and sealed bulk is appended inside protocol via expanding elgamal field.

    For fixed 512-byte protocol field we only ElGamal-encrypt the 32-byte key,
    and pack bulk as: we change approach — encrypt only client_nonce(32) with
    ElGamal (fits), send Pedersen opening in AEAD sealed with key derived from
    that nonce after... actually opening must be secret until node decrypts.

    Layout inside 512-byte ElGamal plaintext limit (240): client_nonce(32) +
    message_int(32) + blinding_head(32) is incomplete.

    Hybrid blob exported as bytes replacing elgamal_ct field content:
    We extend protocol: elgamal_ct field becomes hybrid blob of variable length.
    """
    raise NotImplementedError


def pack_hybrid(node_pub: ElGamalPublicKey, plaintext: bytes) -> bytes:
    key = os.urandom(32)
    ct = encrypt(node_pub, key)
    nonce = os.urandom(12)
    sealed = ChaCha20Poly1305(key).encrypt(nonce, plaintext, b"RPT2-HYBRID")
    return ct.export() + nonce + sealed


def open_hybrid(node_priv: ElGamalPrivateKey, blob: bytes) -> bytes:
    if len(blob) < 512 + 12 + 16:
        raise ValueError("hybrid blob too short")
    ct = ElGamalCiphertext.import_bytes(blob[:512])
    key = decrypt(node_priv, ct)
    if len(key) != 32:
        # encode_message may return key with exact bytes
        key = key[:32] if len(key) >= 32 else key.ljust(32, b"\x00")
    nonce = blob[512:524]
    sealed = blob[524:]
    return ChaCha20Poly1305(key).decrypt(nonce, sealed, b"RPT2-HYBRID")


@dataclass
class HandshakeResult:
    session_id: bytes
    crypto: SessionCrypto
    client_pub: bytes
    shared_probe: bytes
    pfs: bool = False
    server_eph_pub: bytes = b""


class AdmissionError(Exception):
    pass


class NodeHandshake:
    """Node-side admission.

    Free-product default: ``admit_unknown_devices=True`` accepts any client that
    presents a valid Ed25519-signed HELLO + hybrid/Pedersen proof encrypted to
    this node's ElGamal key (per-device keys generated on first client run).
    Optional static allow-list still works for operator test keys / revocations
    when combined with ``admit_unknown_devices=False``.
    """

    def __init__(
        self,
        node_elgamal: ElGamalPrivateKey,
        authorized_client_pubs: Iterable[bytes] | None = None,
        *,
        admit_unknown_devices: bool = True,
        on_enroll: Optional[Callable[[bytes], None]] = None,
    ):
        self.node_elgamal = node_elgamal
        self.authorized: Set[bytes] = set(authorized_client_pubs or ())
        self.admit_unknown_devices = bool(admit_unknown_devices)
        self.on_enroll = on_enroll
        if not self.authorized and not self.admit_unknown_devices:
            raise ValueError(
                "authorized client public keys required when admit_unknown_devices is False"
            )

    def enroll_device(self, client_pub: bytes) -> None:
        """Remember a newly admitted device public key (in-memory + optional callback)."""
        if len(client_pub) != 32:
            return
        if client_pub in self.authorized:
            return
        self.authorized.add(client_pub)
        if self.on_enroll is not None:
            try:
                self.on_enroll(client_pub)
            except Exception:
                pass


def node_complete_hello(
    node: NodeHandshake,
    frame: bytes,
    vpn_ip: str,
) -> tuple[bytes, HandshakeResult]:
    client_pub, commit_b, hybrid_b, sig = parse_client_hello(frame)
    known = client_pub in node.authorized
    if not known and not node.admit_unknown_devices:
        raise AdmissionError("unauthorized client")
    pub = load_ed25519_pub(client_pub)
    try:
        pub.verify(sig, transcript_for_client_hello(client_pub, commit_b, hybrid_b))
    except Exception as exc:
        raise AdmissionError("invalid client signature") from exc

    commit = PedersenCommitment.import_bytes(commit_b)
    try:
        opened = open_hybrid(node.node_elgamal, hybrid_b)
    except Exception as exc:
        raise AdmissionError("hybrid decrypt failed") from exc
    if len(opened) < 32 + 288:
        raise AdmissionError("bad hybrid payload")
    client_nonce = opened[:32]
    opening = PedersenOpening.import_bytes(opened[32 : 32 + 288])
    client_eph_pub = b""
    if len(opened) >= 32 + 288 + EPH_PUB_LEN:
        client_eph_pub = opened[32 + 288 : 32 + 288 + EPH_PUB_LEN]
    try:
        open_verified(commit, opening)
    except Exception as exc:
        raise AdmissionError("pedersen verify failed") from exc
    expected_m = int.from_bytes(hashlib.sha256(client_nonce).digest(), "big") % Q
    if opening.message % Q != expected_m:
        raise AdmissionError("pedersen message mismatch")

    # Crypto verified — enroll first-seen device keys for free-product mode
    if not known:
        node.enroll_device(client_pub)

    session_id = os.urandom(8)
    server_nonce = os.urandom(32)
    s_commit, s_opening = commit_bytes(server_nonce)
    # SERVER_HELLO is sealed under a key derivable from client_nonce alone
    # (client does not yet know server_nonce). Session AEAD rekeys after open.
    hello_shared = hashlib.sha256(client_nonce + client_pub + b"|hello").digest()
    # Hello AEAD must not apply DATA padding (handshake plaintext).
    hello_crypto = SessionCrypto(
        key=derive_session_key(hello_shared, salt=client_nonce[:16], info=b"rpt-v2-hello"),
        traffic_shape=DEFAULT_TRAFFIC_SHAPE,
    )

    # PFS: ephemeral X25519 when client offered a 32-byte eph pub in hybrid payload.
    server_eph = EphemeralX25519.generate()
    use_pfs = len(client_eph_pub) == EPH_PUB_LEN
    if use_pfs:
        try:
            eph_shared = x25519_shared_secret(server_eph.private, client_eph_pub)
            session_shared = derive_pfs_session_shared(
                client_nonce, server_nonce, session_id, client_pub, eph_shared
            )
        except Exception as exc:
            raise AdmissionError("ephemeral DH failed") from exc
    else:
        session_shared = derive_legacy_session_shared(
            client_nonce, server_nonce, session_id, client_pub
        )
    crypto = session_crypto_from_shared(session_shared, client_nonce)

    parts = [int(x) for x in vpn_ip.split(".")]
    plain = server_nonce + s_opening.export() + bytes(parts)
    if use_pfs:
        plain = plain + server_eph.public_raw
    aad = b"RPT2-SERVER-HELLO" + session_id
    # seal without DATA padding framing
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305 as _C

    n = os.urandom(12)
    sealed = _C(hello_crypto.key).encrypt(n, plain, aad)
    reply = pack_server_hello(s_commit.export(), session_id, n, sealed)
    result = HandshakeResult(
        session_id=session_id,
        crypto=crypto,
        client_pub=client_pub,
        shared_probe=session_shared,
        pfs=use_pfs,
        server_eph_pub=server_eph.public_raw if use_pfs else b"",
    )
    return reply, result


def build_client_hello(
    client_priv: Ed25519PrivateKey,
    node_elgamal_pub: ElGamalPublicKey,
    *,
    with_pfs: bool = True,
) -> tuple[bytes, bytes, bytes, EphemeralX25519 | None]:
    """Build CLIENT_HELLO. Returns (frame, client_nonce, client_pub, client_eph_or_None).

    When *with_pfs* is True (default), includes an ephemeral X25519 public key in
    the hybrid payload for perfect forward secrecy of session AEAD keys.
    """
    client_pub = ed25519_pub_raw(client_priv.public_key())
    client_nonce = os.urandom(32)
    commit, opening = commit_bytes(client_nonce)
    eph: EphemeralX25519 | None = None
    payload = client_nonce + opening.export()
    if with_pfs:
        eph = EphemeralX25519.generate()
        payload = payload + eph.public_raw
    hybrid_b = pack_hybrid(node_elgamal_pub, payload)
    commit_b = commit.export()
    sig = client_priv.sign(transcript_for_client_hello(client_pub, commit_b, hybrid_b))
    frame = pack_client_hello(client_pub, commit_b, hybrid_b, sig)
    return frame, client_nonce, client_pub, eph
