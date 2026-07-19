# RPT2 outline for Apple Packet Tunnel (Swift)

Reference implementations (read these on Mac):

- Handshake / session: `client/connect.py`, `node/handshake.py`  
- Frames: `node/protocol.py`  
- Sealed DATA loop: `client/dataplane.py`  
- UK geo gate: removed from product connect (0.1.9); no third-party geo before handshake  

## Constants

- Magic: ASCII `RPT2` (4 bytes)  
- UDP default: host/port from Flutter `connect` args or `82.221.101.241:44044`  
- Msg types: HELLO client/server, **DATA = 0x03**, **KEEPALIVE = 0x04**  

## Connect sequence (extension)

1. **UK public IP check** (fail closed if not GB/UK).  
2. Load `client_ed25519.priv` + `node_elgamal.pub` from App Group / secrets dir.  
3. Build authorized **CLIENT_HELLO** (Ed25519 + ElGamal + Pedersen — match Python).  
4. Send UDP; parse **SERVER_HELLO**; derive session keys (ChaCha20-Poly1305).  
5. Configure tunnel settings: IPv4 address = assigned VPN IP, routes `0.0.0.0/0`, DNS `10.88.0.1` (node tunnel recursive resolver — not public 1.1.1.1/9.9.9.9).  
6. Loop: read IP packets from `packetFlow` → seal DATA → UDP send; UDP DATA → open → `packetFlow.write`.  
7. Periodic KEEPALIVE (~30s) so the node’s live client count stays accurate.  

## Flutter result

On success return to the host app (via channel or IPC):

```json
{ "ok": true, "message": "Connected — tunnel IP 10.88.0.x", "vpnIp": "10.88.0.x" }
```

On failure:

```json
{ "ok": false, "message": "<user-visible reason>" }
```

## Anti-blackhole notes

- Exclude the VPN server host from the tunnel route (or pin host route) so RPT UDP is not recursive.  
- iOS/macOS: use `NEPacketTunnelNetworkSettings` includedRoutes carefully; set `tunnelRemoteAddress` appropriately.  
- Do not claim Connected if `setTunnelNetworkSettings` fails.
