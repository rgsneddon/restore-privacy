# Node residual path — speed analysis (0.4.1)

## Goal
Improve **median residual throughput / latency** for Restore Privacy VPN clients
without geo-admission, third-party telemetry, or residual-honesty regressions.

## Findings (read of `node/server.py`, `routing.py`, `traffic_shape.py`, `sessions.py`)

| Area | Observation | Action (0.4.1) |
|------|-------------|----------------|
| UDP recv path | One `recvfrom` per `select` wake — bursts leave packets in the kernel queue | **Shipped:** `node/udp_fast_path.drain_udp_datagrams` after readable wake |
| Socket buffers | Only `SO_REUSEADDR`; default kernel rcv/snd buffers are small under multi-flow | **Shipped:** `apply_udp_socket_fast_path` → 4 MiB rcv/snd (env override) |
| Traffic shape | Product clients may enable pad/jitter/cover; node defaults off | No change — privacy opt-in must not force latency on node |
| Multihop | Residual-via-exit is opt-in; default single-hop Iceland | Prefer single-hop for speed; multihop remains privacy trade-off |
| DNS | Tunnel DNS via Unbound DoT | Keep; DoT latency is DNS-path only |
| HELLO | Cryptographic admission is mandatory | No shortcut; residual speed is post-session DATA path |

## Env knobs (node process)
- `RPT_UDP_RCVBUF` / `RPT_UDP_SNDBUF` — bytes (default 4 MiB, clamp 64 KiB–64 MiB)
- `RPT_UDP_DRAIN_MAX` — datagrams per select wake (default 64, max 512)

## Deferred (not in 0.4.1)
- Kernel XDP / AF_XDP
- QUIC transport (would change residual wire)
- Per-client QoS classes
- Global RTT SLA claims

## Tests
`tests/test_udp_fast_path.py` drives the shipped helpers on real UDP sockets.
