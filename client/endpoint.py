"""Default RPT node endpoint configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Product default node (FlokiNET / current production).
PRODUCT_NODE_HOST = "82.221.101.241"
PRODUCT_NODE_PORT = 44044

# SHA-256 of product/node_elgamal.pub (must match the live node private key).
# Wrong pub → node hybrid decrypt fails → silent HELLO drop → client timeout.
PRODUCT_NODE_ELGAMAL_PUB_SHA256 = (
    "1b126abfae737c66ce99670b730e123f2831ce5beb2868d7865324f391280bbe"
)


def product_node_elgamal_pub_path() -> Path:
    """Tracked product public key (preferred over gitignored secrets/)."""
    return Path(__file__).resolve().parents[1] / "product" / "node_elgamal.pub"


def product_exit_node_elgamal_pub_path() -> Path:
    """Tracked exit-hop public key (Germany multi-hop residual; public only)."""
    return Path(__file__).resolve().parents[1] / "product" / "exit_node_elgamal.pub"


def product_us_node_elgamal_pub_path() -> Path:
    """Tracked USA residual peer public key (public only; never priv)."""
    return Path(__file__).resolve().parents[1] / "product" / "us_node_elgamal.pub"


@dataclass(frozen=True)
class Endpoint:
    # Literal default keeps alignment tests and frozen configs unambiguous.
    host: str = "82.221.101.241"
    port: int = 44044
    protocol_magic: bytes = b"RPT2"

    @property
    def address(self) -> tuple[str, int]:
        return (self.host, self.port)


DEFAULT_ENDPOINT = Endpoint()
