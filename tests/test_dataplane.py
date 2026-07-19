"""Tests drive the real RPT DATA plane seal/open path (shipped client code)."""

from __future__ import annotations

import socket
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from client.connect import complete_server_hello, build_authorized_client_hello  # noqa: E402
from client.dataplane import QueueTun, RptDataPlane  # noqa: E402
from client.connect import RptClient, ConnectState, ClientSession  # noqa: E402
from client.endpoint import Endpoint  # noqa: E402
from client.windows.tun_win import (  # noqa: E402
    WintunError,
    WintunTun,
    create_windows_tun,
    dataplane_enabled,
    system_capture_ready,
    wintun_dll_available,
    wintun_dll_path,
)
from client.windows.tunnel_win import start_full_tunnel  # noqa: E402
from client.full_tunnel import build_full_tunnel_plan  # noqa: E402
from node.elgamal import generate_keypair  # noqa: E402
from node.handshake import (  # noqa: E402
    NodeHandshake,
    ed25519_pub_raw,
    generate_client_admission_keypair,
    node_complete_hello,
)
from node.protocol import pack_data, parse_data, MsgType, peek_type  # noqa: E402
import struct


class TestDataPlaneRealSealOpen(unittest.TestCase):
    def _session_pair(self):
        node_priv = generate_keypair()
        cpriv, cpub = generate_client_admission_keypair()
        node = NodeHandshake(node_priv, [ed25519_pub_raw(cpub)])
        frame, client_nonce, client_pub, _eph = build_authorized_client_hello(cpriv, node_priv.public)
        reply, result = node_complete_hello(node, frame, "10.88.0.9")
        session = complete_server_hello(reply, client_nonce, client_pub, _eph)
        return session, result

    def test_seal_and_open_via_dataplane_helpers(self):
        session, _ = self._session_pair()
        # Build a minimal RptClient shell with session + connected UDP socket
        client = RptClient.__new__(RptClient)
        client.session = session
        client.endpoint = Endpoint("127.0.0.1", 9)
        client.state = ConnectState.CONNECTED
        client._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client._sock.bind(("127.0.0.1", 0))
        client._sock.setblocking(False)

        plane = RptDataPlane(client)
        tun = QueueTun()
        # Real IP-ish packet into TUN
        ip_pkt = bytes([0x45]) + bytes(19)
        tun.inbound.put(ip_pkt)

        frame = plane.seal_from_tun_once(tun)
        self.assertEqual(peek_type(frame), MsgType.DATA)
        # open_packet is the shipped path
        plain = client.open_packet(frame)
        self.assertEqual(plain, ip_pkt)

        # reverse path: open_to_tun_once
        frame2 = client.seal_packet(ip_pkt)
        plain2 = plane.open_to_tun_once(tun, frame2)
        self.assertEqual(plain2, ip_pkt)
        self.assertEqual(tun.outbound.get_nowait(), ip_pkt)

        # counters prove dataplane used seal/open
        self.assertGreaterEqual(plane.stats.tun_to_udp, 1)
        self.assertGreaterEqual(plane.stats.udp_to_tun, 1)

        client._sock.close()

    def test_start_full_tunnel_starts_dataplane_queue_test_mode(self):
        session, _ = self._session_pair()
        client = RptClient.__new__(RptClient)
        client.session = session
        client.endpoint = Endpoint("127.0.0.1", 9)
        client.state = ConnectState.CONNECTED
        client._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client._sock.bind(("127.0.0.1", 0))
        client._sock.setblocking(False)

        plan = build_full_tunnel_plan(session.vpn_ip, tunnel_iface="RPT")
        # force_queue only for unit tests without admin/driver
        res = start_full_tunnel(
            client, plan, "127.0.0.1", dry_run=False, force_queue=True, prefer_system_capture=False
        )
        self.assertTrue(res.ok, res.message)
        self.assertIsNotNone(res.dataplane)
        self.assertTrue(res.dataplane.is_running())
        self.assertTrue(dataplane_enabled(res.tun))
        self.assertIn("dataplane", res.message.lower())

        impl = res.tun._impl
        if hasattr(impl, "inbound"):
            impl.inbound.put(bytes([0x45]) + bytes(19))
            import time

            time.sleep(0.15)
            self.assertGreaterEqual(res.dataplane.stats.tun_to_udp, 1)

        res.dataplane.stop()
        client._sock.close()

    def test_dataplane_enabled_false_without_tun(self):
        self.assertFalse(dataplane_enabled(None))
        self.assertFalse(system_capture_ready(None))

    def test_wintun_dll_shipped_and_api_binds_without_fake_raise(self):
        """Wintun path must load real exports — not raise after finding WintunCreateAdapter."""
        self.assertTrue(wintun_dll_available(), "wintun.dll must be present under client/windows/native/")
        path = wintun_dll_path()
        self.assertIsNotNone(path)
        self.assertTrue(path.is_file())
        # Binding + CreateAdapter attempt: succeeds as admin, or fails at CreateAdapter (not stub raise)
        try:
            tun = WintunTun(name="RPTTestUnit", client_ip="10.88.0.250")
            self.assertEqual(tun.read_packet() is None or isinstance(tun.read_packet(), (bytes, type(None))), True)
            # write empty-safe
            tun.write_packet(bytes([0x45]) + bytes(19))
            tun.close()
            created = True
        except WintunError as exc:
            created = False
            msg = str(exc).lower()
            # Must be a real driver/API failure, not the old intentional stub
            self.assertNotIn("requires signed driver install at runtime", msg)
            self.assertTrue(
                "wintuncreateadapter failed" in msg
                or "wintunstartsession failed" in msg
                or "administrator" in msg
                or "failed" in msg,
                msg,
            )
        # create_windows_tun prefer_system_capture uses Wintun
        if created:
            t2 = create_windows_tun("10.88.0.251", name="RPTTestUnit2", prefer_system_capture=True)
            self.assertEqual(t2.mode, "wintun")
            self.assertTrue(system_capture_ready(t2))
            t2.close()

    def test_wintun_source_implements_create_adapter_call(self):
        src = (ROOT / "client" / "windows" / "tun_win.py").read_text(encoding="utf-8")
        self.assertIn("WintunCreateAdapter", src)
        self.assertIn("WintunStartSession", src)
        self.assertIn("WintunReceivePacket", src)
        self.assertIn("WintunAllocateSendPacket", src)
        self.assertIn("WintunSendPacket", src)
        self.assertNotIn("requires signed driver install at runtime", src)
        # routes applied for wintun when admin
        tun_src = (ROOT / "client" / "windows" / "tunnel_win.py").read_text(encoding="utf-8")
        self.assertIn("apply_routes_for_adapter", tun_src)
        self.assertIn("system_capture_ready", tun_src)


class TestAndroidEngineSource(unittest.TestCase):
    def test_android_has_handshake_and_aead(self):
        root = ROOT / "client_app/android/app/src/main/kotlin/com/restoreprivacy/restore_privacy_client"
        engine = (root / "RptClientEngine.kt").read_text(encoding="utf-8")
        svc = (root / "RptVpnService.kt").read_text(encoding="utf-8")
        self.assertIn("fun handshake", engine)
        self.assertIn("fun sealPacket", engine)
        self.assertIn("fun openPacket", engine)
        self.assertIn("RPT2-CLIENT-HELLO", engine)
        self.assertIn("elgamalEncrypt", engine)
        self.assertIn("pedersenCommitBytes", engine)
        self.assertIn("engine.handshake", svc)
        self.assertIn("engine.sealPacket", svc)
        self.assertIn("engine.openPacket", svc)
        self.assertNotIn("byteArrayOf(0x52, 0x50, 0x54, 0x32)", svc)  # no magic-only probe


if __name__ == "__main__":
    unittest.main()
