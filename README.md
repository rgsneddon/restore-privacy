# restore-privacy

Custom-built **VPN node** (Restore Privacy Tunnel / RPT). **Not** WireGuard, OpenVPN, or any pre-existing VPN product.

## Node properties

| Property | Behavior |
|----------|----------|
| Admission | Only the Restore Privacy client tunnel (authorized Ed25519 client key + ElGamal/Pedersen handshake) |
| Crypto | ElGamal (RFC 3526 MODP) + Pedersen commitments + ChaCha20-Poly1305 data plane |
| Relay | UDP tunnel to TUN `rpt0` with IP forward and MASQUERADE |
| Privacy | No user-info logs; no client PII collection; UI shows count only |
| UI | HTTP :8080 — title **RESTORE PRIVACY** + current clients connected |

## Ports

- **UDP 44044** — tunnel
- **TCP 8080** — status UI

## Deploy (password via env — never commit)

```bash
export RPT_SSH_HOST=104.156.224.47
export RPT_SSH_USER=root
export RPT_SSH_PASSWORD='...'
pip install paramiko cryptography
python scripts/deploy_rpt_node.py
```

## Local tests

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## Secrets

Keys live under `secrets/` (gitignored) and `/opt/restore-privacy/secrets/` on the server.
