"""Unit tests for node UDP fast-path helpers (shipped residual throughput)."""

from __future__ import annotations

import socket
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestUdpFastPath(unittest.TestCase):
    def test_apply_buffers(self):
        from node.udp_fast_path import (
            DEFAULT_UDP_RCVBUF,
            apply_udp_socket_fast_path,
            udp_buffer_sizes,
        )

        rcv, snd = udp_buffer_sizes()
        self.assertGreaterEqual(rcv, 64 * 1024)
        self.assertEqual(rcv, DEFAULT_UDP_RCVBUF)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            info = apply_udp_socket_fast_path(sock)
            self.assertTrue(info.get("ok") or info.get("rcvbuf") or info.get("sndbuf"))
            # Kernel may double the request on Linux; just require a large buffer
            if info.get("rcvbuf") is not None:
                self.assertGreaterEqual(int(info["rcvbuf"]), 64 * 1024)
        finally:
            sock.close()

    def test_drain_empty_nonblocking(self):
        from node.udp_fast_path import drain_udp_datagrams

        a = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            a.bind(("127.0.0.1", 0))
            port = a.getsockname()[1]
            # Send a burst
            for i in range(5):
                b.sendto(f"pkt{i}".encode(), ("127.0.0.1", port))
            got = drain_udp_datagrams(a, max_packets=10)
            self.assertGreaterEqual(len(got), 1)
            self.assertLessEqual(len(got), 5)
            # Empty drain returns []
            empty = drain_udp_datagrams(a, max_packets=3)
            self.assertEqual(empty, [])
        finally:
            a.close()
            b.close()


if __name__ == "__main__":
    unittest.main()
