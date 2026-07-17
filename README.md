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
- **TCP 8080** — status UI (on the Vultr node)

## Public status page (Render)

The same **RESTORE PRIVACY** + client-count UI can run on [Render](https://render.com) as a free web service. It **proxies** live counts from the Vultr node (`RPT_STATUS_UPSTREAM`) and does not store user data.

| Item | Value |
|------|--------|
| App | `status_page/app.py` |
| Blueprint | `render.yaml` |
| One-click deploy | https://render.com/deploy?repo=https://github.com/rgsneddon/restore-privacy |
| Health | `/health` |
| Expected URL pattern | `https://restore-privacy-status.onrender.com` (name may vary) |

After deploy, open the Render URL — you should see the same title and live count as `http://104.156.224.47:8080/`.

**Note (free tier):** the service may sleep after ~15 minutes idle; the first hit can take 30–90s to wake.

## Deploy node (password via env — never commit)

```bash
export RPT_SSH_HOST=104.156.224.47
export RPT_SSH_USER=root
export RPT_SSH_PASSWORD='...'
pip install paramiko cryptography
python scripts/deploy_rpt_node.py
```

## Client apps

| Platform | How to run |
|----------|------------|
| **Windows** | `python -m client.windows` (retro Win 3.1 UI, auto-connect; admin for full routes) |
| **Android** | `cd client_app && flutter run` / `flutter build apk` |
| **iOS / macOS** | Build on a Mac — see `client_app/ios/BUILD_ON_MAC.md` and `client_app/macos/BUILD_ON_MAC.md` |

Copy node secrets into `./secrets/` (gitignored): `client_ed25519.priv`, `node_elgamal.pub`.

Scrolling UI copy (exact):  
`lightweight vpn to restore your privacy - no user data is retained - your privacy is restored`

## Local tests

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## Secrets

Keys live under `secrets/` (gitignored) and `/opt/restore-privacy/secrets/` on the server.
