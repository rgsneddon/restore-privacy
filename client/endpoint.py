"""Default RPT node endpoint configuration."""

from __future__ import annotations

from dataclasses import dataclass

# Product default node (FlokiNET / current production).
PRODUCT_NODE_HOST = "82.221.101.241"
PRODUCT_NODE_PORT = 44044


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
