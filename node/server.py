#!/usr/bin/env python3
"""RPT VPN node server — custom relay with ElGamal+Pedersen admission."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import select
import struct
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

from node.config import build_node_config, validate_node_config
from node.elgamal import ElGamalPrivateKey, ElGamalPublicKey, generate_keypair
from node.handshake import (
    AdmissionError,
    NodeHandshake,
    ed25519_pub_raw,
    generate_client_admission_keypair,
    node_complete_hello,
)
from node.nolog import apply_no_log_policy
from node.protocol import MsgType, pack_data, parse_data, parse_keepalive, peek_type
from node.routing import (
    build_nat_masquerade_commands,
    build_sysctl_forward_commands,
    detect_wan_iface_command,
)
from node.sessions import Session, SessionRegistry
from node.ui import start_ui_server

TUNSETIFF = 0x400454CA
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000


class NullLogger:
    def info(self, *a, **k):
        return None

    def warning(self, *a, **k):
        return None

    def error(self, *a, **k):
        return None


log = NullLogger()


def open_tun(name: str) -> tuple[int, str]:
    tun = os.open("/dev/net/tun", os.O_RDWR)
    ifr = struct.pack("16sH", name.encode("ascii"), IFF_TUN | IFF_NO_PI)
    ifr = fcntl.ioctl(tun, TUNSETIFF, ifr)
    ifname = ifr[:16].split(b"\x00", 1)[0].decode("ascii")
    return tun, ifname


def ipv4_to_int(ip: str) -> int:
    a, b, c, d = (int(x) for x in ip.split("."))
    return (a << 24) | (b << 16) | (c << 8) | d


def int_to_ipv4(n: int) -> str:
    return f"{(n >> 24) & 0xFF}.{(n >> 16) & 0xFF}.{(n >> 8) & 0xFF}.{n & 0xFF}"


def dest_ip_from_packet(pkt: bytes) -> Optional[str]:
    if len(pkt) < 20 or (pkt[0] >> 4) != 4:
        return None
    return f"{pkt[16]}.{pkt[17]}.{pkt[18]}.{pkt[19]}"


def ensure_secrets(secrets_dir: Path) -> tuple[ElGamalPrivateKey, bytes]:
    secrets_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(secrets_dir, 0o700)
    node_priv_path = secrets_dir / "node_elgamal.priv"
    node_pub_path = secrets_dir / "node_elgamal.pub"
    client_priv_path = secrets_dir / "client_ed25519.priv"
    client_pub_path = secrets_dir / "client_ed25519.pub"
    allow_path = secrets_dir / "authorized_clients.pub"

    if node_priv_path.exists():
        node = ElGamalPrivateKey.import_bytes(node_priv_path.read_bytes())
    else:
        node = generate_keypair()
        node_priv_path.write_bytes(node.export())
        os.chmod(node_priv_path, 0o600)
        node_pub_path.write_bytes(node.public.export())
        os.chmod(node_pub_path, 0o644)

    if client_pub_path.exists():
        client_pub = client_pub_path.read_bytes()
    else:
        cpriv, cpub = generate_client_admission_keypair()
        client_pub = ed25519_pub_raw(cpub)
        from node.handshake import ed25519_priv_raw

        client_priv_path.write_bytes(ed25519_priv_raw(cpriv))
        os.chmod(client_priv_path, 0o600)
        client_pub_path.write_bytes(client_pub)
        os.chmod(client_pub_path, 0o644)

    if not allow_path.exists():
        allow_path.write_bytes(client_pub + b"\n")
        os.chmod(allow_path, 0o644)
    else:
        # ensure client pub is in allow list
        raw = allow_path.read_bytes()
        if client_pub not in raw:
            allow_path.write_bytes(raw.rstrip(b"\n") + b"\n" + client_pub + b"\n")

    return node, client_pub


def load_authorized(secrets_dir: Path) -> list[bytes]:
    allow_path = secrets_dir / "authorized_clients.pub"
    pubs: list[bytes] = []
    data = allow_path.read_bytes()
    # file may be raw 32-byte keys concatenated or newline separated binary
    if b"\n" in data:
        for part in data.split(b"\n"):
            part = part.strip()
            if len(part) == 32:
                pubs.append(part)
            elif len(part) == 64:
                # hex
                try:
                    pubs.append(bytes.fromhex(part.decode("ascii")))
                except Exception:
                    pass
    else:
        for i in range(0, len(data), 32):
            chunk = data[i : i + 32]
            if len(chunk) == 32:
                pubs.append(chunk)
    if not pubs:
        raise SystemExit("no authorized client public keys")
    return pubs


class RPTNode:
    def __init__(self, config: dict, node_key: ElGamalPrivateKey, authorized: list[bytes]):
        v = validate_node_config(config)
        if v:
            raise SystemExit("invalid config: " + "; ".join(v))
        self.config = config
        self.registry = SessionRegistry()
        self.handshake = NodeHandshake(node_key, authorized)
        self._next_ip = ipv4_to_int(config["pool_start"])
        self._pool_end = ipv4_to_int(config["pool_end"])
        self.tun_fd: Optional[int] = None
        self.sock = None

    def allocate_ip(self) -> str:
        if self._next_ip > self._pool_end:
            start = ipv4_to_int(self.config["pool_start"])
            for n in range(start, self._pool_end + 1):
                ip = int_to_ipv4(n)
                if self.registry.get_by_ip(ip) is None:
                    return ip
            raise RuntimeError("IP pool exhausted")
        ip = int_to_ipv4(self._next_ip)
        self._next_ip += 1
        return ip

    def apply_routing(self, iface: str) -> None:
        routing = self.config["routing"]
        for cmd in build_sysctl_forward_commands():
            os.system(cmd)
        addr = routing["tunnel_addr"]
        prefix = routing["tunnel_prefix"]
        os.system(f"ip addr flush dev {iface} 2>/dev/null")
        os.system(f"ip addr add {addr}/{prefix} dev {iface} 2>/dev/null")
        os.system(f"ip link set {iface} up 2>/dev/null")
        wan = os.popen(detect_wan_iface_command()).read().strip() or "eth0"
        for cmd in build_nat_masquerade_commands(iface, wan_iface=wan, client_net=routing["client_net"]):
            os.system(cmd)

    def on_udp(self, data: bytes, addr: Tuple[str, int], sock) -> None:
        t = peek_type(data)
        if t is None:
            return
        try:
            if t == MsgType.CLIENT_HELLO:
                vpn_ip = self.allocate_ip()
                try:
                    reply, result = node_complete_hello(self.handshake, data, vpn_ip)
                except AdmissionError:
                    return  # silent drop — no user-info log
                except Exception:
                    return
                sess = Session(
                    session_id=result.session_id,
                    crypto=result.crypto,
                    client_addr=addr,
                    vpn_ip=vpn_ip,
                )
                self.registry.add(sess)
                sock.sendto(reply, addr)
            elif t == MsgType.DATA:
                session_id, counter, nonce, sealed = parse_data(data)
                sess = self.registry.get(session_id)
                if not sess:
                    return
                # Refresh liveness under registry lock (keeps clients_connected accurate)
                self.registry.touch(session_id, addr)
                aad = session_id + struct.pack("!Q", counter)
                try:
                    plaintext = sess.crypto.open(nonce, sealed, aad=aad)
                except Exception:
                    return
                if self.tun_fd is not None:
                    try:
                        os.write(self.tun_fd, plaintext)
                    except OSError:
                        return
            elif t == MsgType.KEEPALIVE:
                sid = parse_keepalive(data)
                self.registry.touch(sid, addr)
        except Exception:
            return

    def on_tun(self, packet: bytes, sock) -> None:
        dip = dest_ip_from_packet(packet)
        if not dip:
            return
        sess = self.registry.get_by_ip(dip)
        if not sess:
            return
        sess.counter_out += 1
        aad = sess.session_id + struct.pack("!Q", sess.counter_out)
        nonce, sealed = sess.crypto.seal(packet, aad=aad)
        frame = pack_data(sess.session_id, sess.counter_out, nonce, sealed)
        try:
            sock.sendto(frame, sess.client_addr)
        except OSError:
            return

    def serve_forever(self) -> None:
        import socket

        iface = self.config["routing"]["tunnel_iface"]
        os.system(f"ip link del {iface} 2>/dev/null")
        self.tun_fd, _ = open_tun(iface)
        self.apply_routing(iface)

        start_ui_server(self.config["ui_host"], int(self.config["ui_port"]), self.registry.status_payload)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.config["listen_host"], int(self.config["listen_port"])))
        self.sock = sock
        Path("/run/rpt-node.ready").write_text(
            f"listen={self.config['listen_host']}:{self.config['listen_port']}\n"
            f"ui={self.config['ui_host']}:{self.config['ui_port']}\n",
            encoding="utf-8",
        )

        # Periodically drop idle sessions so clients_connected is live, not cumulative
        last_prune = 0.0
        prune_every_sec = 5.0
        while True:
            r, _, _ = select.select([sock, self.tun_fd], [], [], 1.0)
            if sock in r:
                data, addr = sock.recvfrom(65535)
                self.on_udp(data, addr, sock)
            if self.tun_fd in r:
                try:
                    packet = os.read(self.tun_fd, 65535)
                except OSError:
                    continue
                self.on_tun(packet, sock)
            now = time.time()
            if (now - last_prune) >= prune_every_sec:
                self.registry.expire_stale(now=now)
                last_prune = now


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="RPT custom VPN node")
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--listen-port", type=int, default=44044)
    parser.add_argument("--ui-port", type=int, default=8080)
    parser.add_argument("--config-json", default=None)
    parser.add_argument("--secrets-dir", default="/opt/restore-privacy/secrets")
    args = parser.parse_args(argv)

    if args.config_json:
        config = json.loads(Path(args.config_json).read_text(encoding="utf-8"))
        config = apply_no_log_policy(config)
    else:
        config = build_node_config(
            listen_host=args.listen_host,
            listen_port=args.listen_port,
            ui_port=args.ui_port,
            secrets_dir=args.secrets_dir,
        )
    config["listen_host"] = args.listen_host
    config["listen_port"] = args.listen_port
    config["ui_port"] = args.ui_port
    config["collect_user_data"] = False

    secrets = Path(args.secrets_dir)
    node_key, _ = ensure_secrets(secrets)
    authorized = load_authorized(secrets)
    node = RPTNode(config, node_key, authorized)
    node.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
