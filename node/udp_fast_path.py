"""UDP socket throughput helpers for the residual node (no logging, pure opts).

Larger kernel buffers and non-blocking multi-recv reduce per-packet syscall
overhead under load without changing residual crypto or honesty semantics.
"""

from __future__ import annotations

import os
import socket
from typing import Any

# Defaults sized for multi-megabit residual without huge memory (bytes).
DEFAULT_UDP_RCVBUF = 4 * 1024 * 1024  # 4 MiB
DEFAULT_UDP_SNDBUF = 4 * 1024 * 1024
# Max datagrams drained per select wake (bounded work quantum).
DEFAULT_UDP_DRAIN_MAX = 64


def env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def udp_buffer_sizes() -> tuple[int, int]:
    """Return ``(rcvbuf, sndbuf)`` from env or defaults."""
    rcv = env_int("RPT_UDP_RCVBUF", DEFAULT_UDP_RCVBUF)
    snd = env_int("RPT_UDP_SNDBUF", DEFAULT_UDP_SNDBUF)
    rcv = max(64 * 1024, min(rcv, 64 * 1024 * 1024))
    snd = max(64 * 1024, min(snd, 64 * 1024 * 1024))
    return rcv, snd


def udp_drain_max() -> int:
    n = env_int("RPT_UDP_DRAIN_MAX", DEFAULT_UDP_DRAIN_MAX)
    return max(1, min(n, 512))


def apply_udp_socket_fast_path(sock: socket.socket) -> dict[str, Any]:
    """Apply SO_REUSEADDR + large SO_RCVBUF/SO_SNDBUF for residual throughput.

    Returns applied sizes (best-effort; kernel may clamp). Never raises for
    setsockopt failures — residual must still bind.
    """
    out: dict[str, Any] = {"ok": True, "rcvbuf": None, "sndbuf": None}
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except OSError as exc:
        out["reuseaddr_error"] = str(exc)
    rcv, snd = udp_buffer_sizes()
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcv)
        out["rcvbuf"] = sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
    except OSError as exc:
        out["rcvbuf_error"] = str(exc)
        out["ok"] = False
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, snd)
        out["sndbuf"] = sock.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
    except OSError as exc:
        out["sndbuf_error"] = str(exc)
        out["ok"] = False
    return out


def drain_udp_datagrams(
    sock: socket.socket,
    *,
    max_packets: int | None = None,
    bufsize: int = 65535,
) -> list[tuple[bytes, tuple[Any, ...]]]:
    """Non-blocking drain of up to *max_packets* datagrams (empty if would block).

    Call after select reports the socket readable to clear kernel queue bursts
    in one wake — lowers median latency under multi-flow load.
    """
    limit = udp_drain_max() if max_packets is None else max(1, int(max_packets))
    # Ensure non-blocking for drain; restore previous timeout after.
    prev_timeout = sock.gettimeout()
    out: list[tuple[bytes, tuple[Any, ...]]] = []
    try:
        sock.setblocking(False)
        for _ in range(limit):
            try:
                data, addr = sock.recvfrom(bufsize)
            except BlockingIOError:
                break
            except OSError:
                break
            out.append((data, addr))
    finally:
        try:
            sock.settimeout(prev_timeout)
        except OSError:
            pass
    return out
