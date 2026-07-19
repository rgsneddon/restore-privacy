"""Linux TUN helpers for Restore Privacy (Mint / Ubuntu-family).

Pure helpers are unit-testable without root. Opening ``/dev/net/tun`` requires
``CAP_NET_ADMIN`` (typically ``sudo``).
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Linux TUNSETIFF ioctl
_TUNSETIFF = 0x400454CA
_IFF_TUN = 0x0001
_IFF_NO_PI = 0x1000


@dataclass
class LinuxTun:
    """Opened TUN device (file descriptor + iface name). Implements TunIO."""

    name: str
    fd: int

    def fileno(self) -> int:
        return self.fd

    def read_packet(self, max_size: int = 65535) -> Optional[bytes]:
        if self.fd < 0:
            return None
        try:
            data = os.read(self.fd, max_size)
            return data or None
        except BlockingIOError:
            return None
        except OSError:
            return None

    def write_packet(self, packet: bytes) -> None:
        if self.fd < 0 or not packet:
            return
        try:
            os.write(self.fd, packet)
        except OSError:
            pass

    def close(self) -> None:
        try:
            if self.fd >= 0:
                os.close(self.fd)
        except OSError:
            pass
        self.fd = -1


def tun_device_path() -> Path:
    """Default clone device for TUN/TAP on Linux."""
    return Path("/dev/net/tun")


def system_capture_ready() -> bool:
    """True when this process can open a real OS TUN (Linux + /dev/net/tun)."""
    if sys.platform != "linux":
        return False
    p = tun_device_path()
    return p.exists()


def is_root() -> bool:
    if sys.platform != "linux":
        return False
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def open_linux_tun(name: str = "rpt0") -> LinuxTun:
    """Create/open a TUN interface named ``name`` (requires root / CAP_NET_ADMIN)."""
    if sys.platform != "linux":
        raise OSError("Linux TUN only available on Linux")
    path = tun_device_path()
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing - load the tun module (sudo modprobe tun)"
        )
    import fcntl

    fd = os.open(str(path), os.O_RDWR)
    # struct ifreq: 16-byte name + short flags
    ifr = struct.pack("16sH", name.encode("ascii")[:15], _IFF_TUN | _IFF_NO_PI)
    try:
        fcntl.ioctl(fd, _TUNSETIFF, ifr)
        # Non-blocking: RptDataPlane select() + read_packet() must not stall on idle TUN
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    except OSError:
        os.close(fd)
        raise
    return LinuxTun(name=name, fd=fd)


def ensure_tun_nonblocking(fd: int) -> None:
    """Apply O_NONBLOCK to an open TUN fd (shared helper for tests / callers)."""
    if fd < 0:
        return
    import fcntl

    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)


def create_linux_tun(
    name: str = "rpt0",
    *,
    require_system: bool = True,
) -> tuple[Optional[LinuxTun], str]:
    """Try to open system TUN. Returns ``(tun, message)``.

    When ``require_system`` and open fails, returns ``(None, error)``.
    """
    if not system_capture_ready():
        msg = "system TUN not available (/dev/net/tun)"
        if require_system:
            return None, msg
        return None, msg
    if not is_root():
        msg = "root (or CAP_NET_ADMIN) required to open TUN for residual public IP"
        if require_system:
            return None, msg
        return None, msg
    try:
        tun = open_linux_tun(name)
        return tun, f"TUN {tun.name} open"
    except Exception as exc:  # noqa: BLE001
        return None, f"TUN open failed: {exc}"


def _parse_default_route_line(line: str) -> tuple[Optional[str], Optional[str]]:
    """Parse one ``ip route`` default line into ``(gw, dev)``.

    Handles common Ubuntu iproute2 shapes across 20.04–24.04:
    - ``default via 192.168.1.1 dev eth0 proto dhcp metric 100``
    - ``default dev eth0 scope link`` (on-link, no via)
    - ``default via 10.0.0.1 dev ens3``
    """
    parts = line.split()
    if not parts or parts[0] != "default":
        return None, None
    gw = None
    dev = None
    if "via" in parts:
        i = parts.index("via")
        if i + 1 < len(parts):
            cand = parts[i + 1]
            if cand.count(".") == 3 and not cand.startswith("10.88."):
                gw = cand
    if "dev" in parts:
        i = parts.index("dev")
        if i + 1 < len(parts):
            dev = parts[i + 1]
    return gw, dev


def resolve_default_route() -> tuple[Optional[str], Optional[str]]:
    """Return ``(gateway_ip, physical_dev)`` for the default IPv4 route.

    Tries ``ip -4 route show default`` then ``ip route show default`` so both
    older and newer iproute2 on Ubuntu work. On-link defaults (no via) return
    ``(None, dev)`` so callers can pin the server with ``dev`` only.
    """
    cmds = (
        ["ip", "-4", "route", "show", "default"],
        ["ip", "route", "show", "default"],
        ["ip", "route"],  # last resort: scan for default line
    )
    for cmd in cmds:
        try:
            out = subprocess.check_output(
                cmd,
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except Exception:
            continue
        best_onlink: tuple[Optional[str], Optional[str]] = (None, None)
        for line in out.splitlines():
            gw, dev = _parse_default_route_line(line)
            if gw and dev:
                return gw, dev
            if dev and not gw:
                best_onlink = (None, dev)
        if best_onlink[1]:
            return best_onlink
    return None, None
