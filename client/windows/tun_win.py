"""Windows TUN via Wintun (open-source virtual NIC driver — not WireGuard protocol).

Creates a real OS network adapter so system routes can deliver traffic into the
sealed RPT DATA plane (seal_packet / open_packet).
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

# --- Wintun ctypes API (https://git.zx2c4.com/wintun/about/) ---

HADAPTER = ctypes.c_void_p
HSESSION = ctypes.c_void_p


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]


class NET_LUID(ctypes.Structure):
    _fields_ = [("Value", ctypes.c_uint64)]


def _wintun_dll_candidates() -> list[Path]:
    here = Path(__file__).resolve().parent
    env = os.environ.get("WINTUN_DLL", "").strip()
    out: list[Path] = []
    if env:
        out.append(Path(env))
    out.extend(
        [
            here / "native" / "wintun.dll",
            here / "native" / "wintun-amd64.dll",
            here / "wintun.dll",
        ]
    )
    return out


def wintun_dll_path() -> Optional[Path]:
    for p in _wintun_dll_candidates():
        if p.is_file():
            return p
    return None


def wintun_dll_available() -> bool:
    return wintun_dll_path() is not None


class WintunError(RuntimeError):
    pass


class WintunTun:
    """Real Wintun session: OS-visible adapter with packet IO."""

    RING_CAPACITY = 0x400000  # 4 MiB

    def __init__(self, name: str = "RPT", client_ip: str = "10.88.0.2", tunnel_type: str = "RestorePrivacy"):
        if sys.platform != "win32":
            raise WintunError("Wintun is Windows-only")
        path = wintun_dll_path()
        if not path:
            raise WintunError("wintun.dll not found under client/windows/native/")

        self.name = name
        self.client_ip = client_ip
        self._dll = ctypes.WinDLL(str(path), use_last_error=True)
        self._bind_api()
        self._adapter = None
        self._session = None
        self._lock = threading.Lock()
        self._closed = False

        # Create adapter (requires Administrator)
        name_w = ctypes.c_wchar_p(name)
        type_w = ctypes.c_wchar_p(tunnel_type)
        adapter = self._WintunCreateAdapter(name_w, type_w, None)
        if not adapter:
            err = ctypes.get_last_error()
            raise WintunError(
                f"WintunCreateAdapter failed (winerr={err}). "
                "Run as Administrator and ensure the Wintun driver can load."
            )
        self._adapter = adapter

        session = self._WintunStartSession(adapter, self.RING_CAPACITY)
        if not session:
            self._WintunCloseAdapter(adapter)
            self._adapter = None
            raise WintunError("WintunStartSession failed")
        self._session = session
        self._read_event = self._WintunGetReadWaitEvent(session)

    def _bind_api(self) -> None:
        d = self._dll
        self._WintunCreateAdapter = d.WintunCreateAdapter
        self._WintunCreateAdapter.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(GUID)]
        self._WintunCreateAdapter.restype = HADAPTER

        self._WintunCloseAdapter = d.WintunCloseAdapter
        self._WintunCloseAdapter.argtypes = [HADAPTER]
        self._WintunCloseAdapter.restype = None

        self._WintunStartSession = d.WintunStartSession
        self._WintunStartSession.argtypes = [HADAPTER, wintypes.DWORD]
        self._WintunStartSession.restype = HSESSION

        self._WintunEndSession = d.WintunEndSession
        self._WintunEndSession.argtypes = [HSESSION]
        self._WintunEndSession.restype = None

        self._WintunGetReadWaitEvent = d.WintunGetReadWaitEvent
        self._WintunGetReadWaitEvent.argtypes = [HSESSION]
        self._WintunGetReadWaitEvent.restype = wintypes.HANDLE

        self._WintunReceivePacket = d.WintunReceivePacket
        self._WintunReceivePacket.argtypes = [HSESSION, ctypes.POINTER(wintypes.DWORD)]
        self._WintunReceivePacket.restype = ctypes.POINTER(ctypes.c_ubyte)

        self._WintunReleaseReceivePacket = d.WintunReleaseReceivePacket
        self._WintunReleaseReceivePacket.argtypes = [HSESSION, ctypes.POINTER(ctypes.c_ubyte)]
        self._WintunReleaseReceivePacket.restype = None

        self._WintunAllocateSendPacket = d.WintunAllocateSendPacket
        self._WintunAllocateSendPacket.argtypes = [HSESSION, wintypes.DWORD]
        self._WintunAllocateSendPacket.restype = ctypes.POINTER(ctypes.c_ubyte)

        self._WintunSendPacket = d.WintunSendPacket
        self._WintunSendPacket.argtypes = [HSESSION, ctypes.POINTER(ctypes.c_ubyte)]
        self._WintunSendPacket.restype = None

        # Required symbols must exist
        for attr in (
            "WintunCreateAdapter",
            "WintunStartSession",
            "WintunReceivePacket",
            "WintunSendPacket",
            "WintunAllocateSendPacket",
        ):
            if not hasattr(d, attr):
                raise WintunError(f"missing Wintun export: {attr}")

    def interface_index(self) -> Optional[int]:
        """Windows IF index for route … IF <n> (anti-blackhole full-tunnel)."""
        return resolve_interface_index(self.name)

    def configure_address(self) -> list[str]:
        """Assign IPv4 on the Wintun adapter with on-link gateway 10.88.0.1.

        Using /24 + gateway (not bare /32 alone) so dual /1 routes via the
        tunnel gateway are reachable and do not blackhole internet traffic.
        """
        gateway = "10.88.0.1"
        cmds = [
            f'netsh interface ip set address name="{self.name}" '
            f"static {self.client_ip} 255.255.255.0 {gateway}",
            f'netsh interface ip delete dns name="{self.name}" all',
            f'netsh interface ip add dns name="{self.name}" addr=1.1.1.1 index=1',
            f'netsh interface ip add dns name="{self.name}" addr=9.9.9.9 index=2',
            # Ensure adapter is up for routing
            f'netsh interface set interface name="{self.name}" admin=ENABLED',
        ]
        for c in cmds:
            subprocess.run(c, shell=True, capture_output=True, text=True)
        return cmds

    def read_packet(self, max_size: int = 65535) -> Optional[bytes]:
        if self._closed or not self._session:
            return None
        with self._lock:
            size = wintypes.DWORD(0)
            ptr = self._WintunReceivePacket(self._session, ctypes.byref(size))
            if not ptr:
                return None
            n = int(size.value)
            if n <= 0:
                self._WintunReleaseReceivePacket(self._session, ptr)
                return None
            data = ctypes.string_at(ptr, min(n, max_size))
            self._WintunReleaseReceivePacket(self._session, ptr)
            return data

    def write_packet(self, packet: bytes) -> None:
        if self._closed or not self._session or not packet:
            return
        with self._lock:
            ptr = self._WintunAllocateSendPacket(self._session, len(packet))
            if not ptr:
                return
            ctypes.memmove(ptr, packet, len(packet))
            self._WintunSendPacket(self._session, ptr)

    def fileno(self) -> int:
        # Wintun uses wait events, not a selectable fd
        return -1

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        with self._lock:
            if self._session:
                try:
                    self._WintunEndSession(self._session)
                except Exception:
                    pass
                self._session = None
            if self._adapter:
                try:
                    self._WintunCloseAdapter(self._adapter)
                except Exception:
                    pass
                self._adapter = None


class WindowsTun:
    """TUN for RPT: prefers real Wintun adapter; fails closed if required.

    When prefer_system_capture=True (default for full VPN), only Wintun is used.
    QueueTun is available for unit tests via force_queue=True only.
    """

    def __init__(
        self,
        name: str = "RPT",
        client_ip: str = "10.88.0.2",
        force_queue: bool = False,
        prefer_system_capture: bool = True,
    ):
        self.name = name
        self.client_ip = client_ip
        self._closed = False
        self._impl: TunIO
        self._mode: str

        if force_queue:
            self._impl = QueueTun()
            self._mode = "queue_fallback"
            return

        if prefer_system_capture:
            # Full VPN path: must be a real OS adapter
            self._impl = WintunTun(name=name, client_ip=client_ip)
            self._mode = "wintun"
            return

        # Optional soft path (tests / degraded)
        try:
            self._impl = WintunTun(name=name, client_ip=client_ip)
            self._mode = "wintun"
        except Exception:
            self._impl = QueueTun()
            self._mode = "queue_fallback"

    @property
    def mode(self) -> str:
        return self._mode

    def interface_index(self) -> Optional[int]:
        if hasattr(self._impl, "interface_index"):
            return self._impl.interface_index()  # type: ignore[no-any-return]
        return resolve_interface_index(self.name)

    def configure_address(self) -> list[str]:
        if hasattr(self._impl, "configure_address"):
            return self._impl.configure_address()  # type: ignore[no-any-return]
        return [
            f'netsh interface ip set address name="{self.name}" '
            f"static {self.client_ip} 255.255.255.0 10.88.0.1",
        ]

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


def create_windows_tun(
    client_ip: str,
    name: str = "RPT",
    force_queue: bool = False,
    prefer_system_capture: bool = True,
) -> WindowsTun:
    return WindowsTun(
        name=name,
        client_ip=client_ip,
        force_queue=force_queue,
        prefer_system_capture=prefer_system_capture,
    )


def resolve_interface_index(name: str) -> Optional[int]:
    """Resolve Windows interface index by adapter name (for route IF binding)."""
    if sys.platform != "win32":
        return None
    # PowerShell Get-NetAdapter is reliable for Wintun names
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                f"(Get-NetAdapter -Name '{name}' -ErrorAction SilentlyContinue | "
                f"Select-Object -First 1).ifIndex",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=15,
        ).strip()
        if out.isdigit():
            return int(out)
    except Exception:
        pass
    # Fallback: netsh show interfaces
    try:
        out = subprocess.check_output(
            ["netsh", "interface", "ipv4", "show", "interfaces"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        for line in out.splitlines():
            # Idx  Met  MTU   State        Name
            parts = line.split()
            if len(parts) >= 5 and name.lower() in line.lower():
                if parts[0].isdigit():
                    return int(parts[0])
    except Exception:
        pass
    return None


def dataplane_enabled(tun: Optional[WindowsTun] = None) -> bool:
    """True when a live TUN is open for IO (Wintun or explicit test queue)."""
    if tun is None or getattr(tun, "_closed", False):
        return False
    return tun.mode in ("wintun", "queue_fallback")


def system_capture_ready(tun: Optional[WindowsTun] = None) -> bool:
    """True only when OS can deliver routed packets into the TUN (real Wintun)."""
    return tun is not None and not getattr(tun, "_closed", False) and tun.mode == "wintun"
