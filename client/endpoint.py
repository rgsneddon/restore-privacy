"""Default RPT node endpoint configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Endpoint:
    host: str = "104.156.224.47"
    port: int = 44044
    protocol_magic: bytes = b"RPT2"

    @property
    def address(self) -> tuple[str, int]:
        return (self.host, self.port)


DEFAULT_ENDPOINT = Endpoint()
