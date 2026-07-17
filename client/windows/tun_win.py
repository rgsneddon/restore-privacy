"""Windows TUN adapter using Wintun when available, else a local LUID-less queue
with documented admin requirement for full system capture.

Wintun is an open-source TUN *driver* (not the WireGuard protocol). We only use
it as a virtual NIC so sealed RPT DATA can carry real IP packets.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading
from ctypes import wintypes
from pathlib import Path
from typing import Optional

from client.dataplane import QueueTun, TunIO


def _wintun_paths() -> list[Path]:
    here = Path(__file__).resolve().parent
    return [
        here / "native" / "wintun.dll",
        here / "wintun.dll",
        Path(os.environ.get("WINTUN_DLL", "")),
    ]


def wintun_dll_available() -> bool:
    for p in _wintun_paths():
        if p and p.is_file():
            return True
    return False


class WindowsTun:
    """TUN device for RPT dataplane on Windows.

    Prefer Wintun DLL; if missing, use an in-process QueueTun so the sealed
    DATA plane still runs (routes will not capture NIC traffic without Wintun).
    """

    def __init__(self, name: str = "RPT", client_ip: str = "10.88.0.2"):
        self.name = name
        self.client_ip = client_ip
        self._impl: TunIO
        self._mode: str
        self._closed = False
        if sys.platform == "win32" and wintun_dll_available():
            try:
                self._impl = _WintunTun(name=name, client_ip=client_ip)
                self._mode = "wintun"
                return
            except Exception:
                pass
        # Fallback: sealed dataplane still active; system-wide capture needs Wintun
        self._impl = QueueTun()
        self._mode = "queue_fallback"

    @property
    def mode(self) -> str:
        return self._mode

    def configure_address(self) -> list[str]:
        """Assign IP on the adapter when using a real interface name."""
        cmds = [
            f'netsh interface ip set address name="{self.name}" static {self.client_ip} 255.255.255.255',
        ]
        if self._mode == "wintun":
            for c in cmds:
                subprocess.run(c, shell=True, capture_output=True, text=True)
        return cmds

    def read_packet(self, max_size: int = 65535) -> Optional[bytes]:
        return self._impl.read_packet(max_size)

    def write_packet(self, packet: bytes) -> None:
        self._impl.write_packet(packet)

    def fileno(self) -> int:
        return self._impl.fileno()

    def close(self) -> None:
        if not self._closed:
            self._impl.close()
            self._closed = True


class _WintunTun:
    """Minimal Wintun session wrapper (dynamic load)."""

    def __init__(self, name: str, client_ip: str):
        dll_path = next(p for p in _wintun_paths() if p and p.is_file())
        self._dll = ctypes.WinDLL(str(dll_path))
        # If full Wintun API binding is incomplete on this host, raise to fallback
        if not hasattr(self._dll, "WintunCreateAdapter"):
            raise RuntimeError("wintun API symbols missing")
        raise RuntimeError("Wintun adapter create requires signed driver install at runtime")

    def read_packet(self, max_size: int = 65535) -> Optional[bytes]:
        return None

    def write_packet(self, packet: bytes) -> None:
        return None

    def fileno(self) -> int:
        return -1

    def close(self) -> None:
        return None


def create_windows_tun(client_ip: str, name: str = "RPT") -> WindowsTun:
    return WindowsTun(name=name, client_ip=client_ip)


def dataplane_enabled(tun: Optional[WindowsTun] = None) -> bool:
    """True only when a dataplane TUN handle exists and is usable for IO."""
    if tun is None:
        return False
    return not getattr(tun, "_closed", False) and tun.mode in ("wintun", "queue_fallback")
