"""Windows TUN via Wintun (open-source virtual NIC driver — not WireGuard protocol).

Creates a real OS network adapter so system routes can deliver traffic into the
sealed RPT DATA plane (seal_packet / open_packet).
"""

from __future__ import annotations

import ctypes
import os
import sys
import threading
from ctypes import wintypes
from pathlib import Path
from collections.abc import Callable
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

        # Open existing adapter first (leftover RPT from crash/zombie), else create.
        # Create-only can hang or fail slowly when the name is already allocated.
        name_w = ctypes.c_wchar_p(name)
        type_w = ctypes.c_wchar_p(tunnel_type)
        adapter = None
        if self._WintunOpenAdapter is not None:
            try:
                adapter = self._WintunOpenAdapter(name_w)
            except Exception:
                adapter = None
        if not adapter:
            adapter = self._WintunCreateAdapter(name_w, type_w, None)
        if not adapter:
            err = ctypes.get_last_error()
            raise WintunError(
                f"WintunCreateAdapter/OpenAdapter failed (winerr={err}). "
                "Run as Administrator and ensure the Wintun driver can load."
            )
        self._adapter = adapter
        # Start the receive ring *after* netsh address/DNS (those cmds bounce
        # the NIC and would leave a pre-config session deaf — HELLO still
        # works on the UDP socket, dual /1 then blackholes).
        self._session = None
        self._read_event = None

    def _bind_api(self) -> None:
        d = self._dll
        self._WintunCreateAdapter = d.WintunCreateAdapter
        self._WintunCreateAdapter.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(GUID)]
        self._WintunCreateAdapter.restype = HADAPTER

        # Optional: reopen existing adapter (present on modern wintun.dll)
        self._WintunOpenAdapter = None
        if hasattr(d, "WintunOpenAdapter"):
            self._WintunOpenAdapter = d.WintunOpenAdapter
            self._WintunOpenAdapter.argtypes = [wintypes.LPCWSTR]
            self._WintunOpenAdapter.restype = HADAPTER

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

        self._WintunGetAdapterLUID = None
        if hasattr(d, "WintunGetAdapterLUID"):
            self._WintunGetAdapterLUID = d.WintunGetAdapterLUID
            self._WintunGetAdapterLUID.argtypes = [HADAPTER, ctypes.POINTER(NET_LUID)]
            self._WintunGetAdapterLUID.restype = None

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

    def start_session(self) -> None:
        """Open the Wintun packet ring (call after configure_address)."""
        if self._closed:
            raise WintunError("adapter closed")
        with self._lock:
            if self._session:
                try:
                    self._WintunEndSession(self._session)
                except Exception:
                    pass
                self._session = None
                self._read_event = None
            if not self._adapter:
                raise WintunError("no Wintun adapter")
            session = self._WintunStartSession(self._adapter, self.RING_CAPACITY)
            if not session:
                raise WintunError("WintunStartSession failed after address config")
            self._session = session
            self._read_event = self._WintunGetReadWaitEvent(session)

    def interface_index(self) -> Optional[int]:
        """Windows IF index for route … IF <n> (anti-blackhole full-tunnel).

        Prefer the adapter **name** (``RPT``) so dual /1 is not applied to a
        stale LUID. Fall back to Wintun LUID → IF index when name resolve fails.
        """
        named = resolve_interface_index(self.name)
        if named:
            return named
        try:
            if self._adapter and self._WintunGetAdapterLUID is not None:
                luid = NET_LUID()
                self._WintunGetAdapterLUID(self._adapter, ctypes.byref(luid))
                idx = if_index_from_luid_value(int(luid.Value))
                if idx:
                    return idx
        except Exception:
            pass
        return None

    def configure_address(self) -> list[str]:
        """Assign IPv4 /32 on Wintun — no fake gateway 10.88.0.1 (cannot ARP).

        Full-tunnel uses IF-bound on-link routes (0.0.0.0 IF <n>), not a next-hop
        that Windows would try to ARP on this virtual NIC.
        """
        required, dns_cmds = wintun_configure_address_commands(
            self.name, self.client_ip, wintun_attach_dns_servers(unbound_ok=False)
        )
        from client.windows.hidden_subprocess import run_hidden

        ran: list[str] = []
        for c in required:
            # netsh is a console app — must use run_hidden or a large blue
            # console flashes on Connect (pythonw has no console to inherit).
            run_hidden(c, shell=True, text=True, timeout=8)
            ran.append(c)
        # DNS add without validate=no contacts 10.88.0.1 before residual is up
        # and hangs (desktop log: add dns timed out after 8s). Never fail attach.
        for c in dns_cmds:
            try:
                run_hidden(c, shell=True, text=True, timeout=5)
            except Exception:
                pass
            ran.append(c)
        return ran

    def read_packet(self, max_size: int = 65535, wait_ms: int = 20) -> Optional[bytes]:
        if self._closed or not self._session:
            return None
        # wait_ms=0 is a non-blocking ring poll (dataplane burst drain).
        try:
            if self._read_event and int(wait_ms) > 0:
                ctypes.windll.kernel32.WaitForSingleObject(
                    self._read_event, int(wait_ms)
                )
        except Exception:
            pass
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
            f"static {self.client_ip} 255.255.255.255",
        ]

    def start_io(self) -> None:
        """Start packet IO after the adapter address is configured."""
        impl = self._impl
        start = getattr(impl, "start_session", None)
        if callable(start):
            start()

    def read_packet(self, max_size: int = 65535, wait_ms: int = 20) -> Optional[bytes]:
        impl = self._impl
        try:
            return impl.read_packet(max_size, wait_ms=wait_ms)
        except TypeError:
            return impl.read_packet(max_size)

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


# Node Unbound (10.88.0.1) has been silent from this Windows client (website
# log: Connected + no internet with IPv6 blocked). Public resolvers still leave
# via dual /1. Do not stamp 10.88.0.1 on the IF unless Unbound actually answers.
WINDOWS_TUNNEL_DNS_PUBLIC: tuple[str, ...] = ("1.1.1.1", "9.9.9.9")


def wintun_attach_dns_servers(*, unbound_ok: bool = False) -> list[str]:
    """Interface DNS for residual Wintun: Unbound only when it has answered."""
    if unbound_ok:
        return ["10.88.0.1"]
    return list(WINDOWS_TUNNEL_DNS_PUBLIC)


def wintun_configure_address_commands(
    name: str,
    client_ip: str,
    dns_servers: list[str],
) -> tuple[list[str], list[str]]:
    """Required address cmds vs optional DNS cmds (always ``validate=no``)."""
    required = [
        f'netsh interface ip set address name="{name}" '
        f"static {client_ip} 255.255.255.255",
        f'netsh interface ipv4 set interface name="{name}" '
        f"metric=1 dadtransmits=0 weakhostsend=enabled weakhostreceive=enabled",
        f'netsh interface set interface name="{name}" admin=ENABLED',
    ]
    dns_cmds = wintun_dns_commands(name, dns_servers)
    return required, dns_cmds


def wintun_dns_commands(name: str, dns_servers: list[str]) -> list[str]:
    """Interface DNS cmds (always ``validate=no`` — never probe 10.88.0.1)."""
    dns_cmds: list[str] = []
    for i, dns in enumerate(dns_servers, start=1):
        addr = str(dns or "").strip()
        if not addr:
            continue
        if i == 1:
            dns_cmds.append(
                f'netsh interface ip set dns name="{name}" static {addr} validate=no'
            )
        else:
            dns_cmds.append(
                f'netsh interface ip add dns name="{name}" addr={addr} '
                f"index={i} validate=no"
            )
    return dns_cmds


def if_index_from_luid_value(
    luid_value: int,
    *,
    convert: Optional[Callable[[int], Optional[int]]] = None,
) -> Optional[int]:
    """Map a NET_LUID integer to an IF index. *convert* is injectable for tests."""
    try:
        val = int(luid_value)
    except (TypeError, ValueError):
        return None
    if val <= 0:
        return None
    if convert is not None:
        try:
            idx = convert(val)
            n = int(idx) if idx is not None else 0
            return n if n > 0 else None
        except Exception:
            return None
    return convert_net_luid_to_if_index(val)


def convert_net_luid_to_if_index(luid_value: int) -> Optional[int]:
    """iphlpapi ConvertInterfaceLuidToIndex (Windows)."""
    if sys.platform != "win32":
        return None
    try:
        val = int(luid_value)
    except (TypeError, ValueError):
        return None
    if val <= 0:
        return None
    try:
        iphlpapi = ctypes.WinDLL("iphlpapi")
        conv = iphlpapi.ConvertInterfaceLuidToIndex
        conv.argtypes = [ctypes.POINTER(NET_LUID), ctypes.POINTER(wintypes.DWORD)]
        conv.restype = wintypes.DWORD
        luid = NET_LUID(val)
        idx = wintypes.DWORD(0)
        status = int(conv(ctypes.byref(luid), ctypes.byref(idx)))
        if status == 0 and int(idx.value) > 0:
            return int(idx.value)
    except Exception:
        return None
    return None


def resolve_interface_index(name: str) -> Optional[int]:
    """Resolve Windows interface index by adapter name (for route IF binding)."""
    if sys.platform != "win32":
        return None
    from client.windows.hidden_subprocess import run_hidden

    # PowerShell Get-NetAdapter is reliable for Wintun names (hidden host)
    try:
        r = run_hidden(
            [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                f"(Get-NetAdapter -Name '{name}' -ErrorAction SilentlyContinue | "
                f"Select-Object -First 1).ifIndex",
            ],
            shell=False,
            text=True,
            timeout=15,
        )
        out = (r.stdout or "").strip()
        if out.isdigit():
            return int(out)
    except Exception:
        pass
    # Fallback: netsh show interfaces (also console — keep hidden)
    try:
        r = run_hidden(
            ["netsh", "interface", "ipv4", "show", "interfaces"],
            shell=False,
            text=True,
            timeout=15,
        )
        out = r.stdout or ""
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
