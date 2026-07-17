"""Load authorized client keys from gitignored secrets/ paths (never commit privkeys)."""

from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from node.elgamal import ElGamalPublicKey
from node.handshake import ed25519_priv_raw

# Search order for secrets (local first, then env override path)
DEFAULT_SECRETS_DIRS = (
    Path(__file__).resolve().parents[1] / "secrets",
    Path.home() / ".restore-privacy" / "secrets",
    Path("/opt/restore-privacy/secrets"),
)


class SecretsError(FileNotFoundError):
    pass


def resolve_secrets_dir(explicit: str | Path | None = None) -> Path:
    if explicit:
        p = Path(explicit)
        if p.is_dir():
            return p
        raise SecretsError(f"secrets dir not found: {p}")
    for d in DEFAULT_SECRETS_DIRS:
        if d.is_dir() and (d / "client_ed25519.priv").exists():
            return d
    raise SecretsError(
        "No client secrets found. Copy from the node: "
        "/opt/restore-privacy/secrets/{client_ed25519.priv,node_elgamal.pub} "
        "into ./secrets/ (gitignored)."
    )


def load_client_private_key(secrets_dir: Path | None = None) -> Ed25519PrivateKey:
    d = secrets_dir or resolve_secrets_dir()
    raw = (d / "client_ed25519.priv").read_bytes()
    if len(raw) != 32:
        raise SecretsError("client_ed25519.priv must be 32 raw bytes")
    return Ed25519PrivateKey.from_private_bytes(raw)


def load_node_elgamal_public(secrets_dir: Path | None = None) -> ElGamalPublicKey:
    d = secrets_dir or resolve_secrets_dir()
    raw = (d / "node_elgamal.pub").read_bytes()
    return ElGamalPublicKey.import_bytes(raw)


def secrets_present(secrets_dir: Path | None = None) -> bool:
    try:
        d = secrets_dir or resolve_secrets_dir()
    except SecretsError:
        return False
    return (d / "client_ed25519.priv").is_file() and (d / "node_elgamal.pub").is_file()
