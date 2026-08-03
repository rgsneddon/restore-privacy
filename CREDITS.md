# Credits and third-party attributions

**Restore Privacy residual VPN** (RPT) is an original product. The public storefront is the
**VPN APP Shop**. The components below are used by the shipped tree or installers.
They are **not** the RPT protocol itself.

## Crypto libraries

| Component | Role | Upstream licence | More information |
|-----------|------|------------------|------------------|
| **cryptography** (Python) | AEAD (ChaCha20-Poly1305), Ed25519, HKDF on node and Windows/Linux clients | Apache-2.0 / BSD | https://github.com/pyca/cryptography |
| **Bouncy Castle** (`bcprov-jdk18on`) | Android handshake / AEAD helpers | MIT | https://www.bouncycastle.org/ |
| **Apple CryptoKit** | iOS/macOS AEAD, Ed25519, HKDF-SHA256 for Packet Tunnel | Apple SDK | https://developer.apple.com/documentation/cryptokit |
| **BigInt** (attaswift, vendored) | 2048-bit modular arithmetic for ElGamal/Pedersen on Apple | MIT | https://github.com/attaswift/BigInt |

ElGamal and Pedersen in this project use **RFC 3526** MODP group 14 parameters: https://www.rfc-editor.org/rfc/rfc3526

## Virtual network / TUN

| Component | Role | Upstream licence | More information |
|-----------|------|------------------|------------------|
| **Wintun** | Windows virtual NIC so sealed RPT DATA can carry IP packets on a virtual adapter | GPL-2.0 (see Wintun site) | https://www.wintun.net/ |

`client/windows/native/wintun.dll` (when packaged) is the upstream binary. Full-system VPN on Windows needs Administrator rights for the adapter and routes.

## UI frameworks

| Component | Role | Upstream licence | More information |
|-----------|------|------------------|------------------|
| **Flutter** / **Dart** | Android (and multi-platform) client UI; method channel to native VPN | BSD-3-Clause | https://flutter.dev/ |
| **Tkinter** | Windows desktop shell | Python Software Foundation | https://docs.python.org/3/library/tkinter.html |

The dark retro chrome is a visual nod to classic Windows 3.x UI — no Microsoft source is included. Microsoft and Windows are trademarks of their owners.

## Packaging and services

| Component | Role | Notes |
|-----------|------|--------|
| **PyInstaller** | Optional Windows frozen bundles | See PyInstaller docs |
| **7-Zip / LZMA SDK** | Windows self-extracting setup packaging | https://www.7-zip.org/ |
| **paramiko** | Optional deploy SSH helper | LGPL-2.1 — https://www.paramiko.org/ |
| **GitHub** | Private operator source hosting (not a free public installer CDN) | GitHub terms |
| **Stripe** | Catalog checkout (monthly £3.00 / yearly £30.00 GBP) | https://stripe.com/ |
| **Render** | Public status host + paid download fulfilment | https://render.com/ |
| **FlokiNET** | Residual peer IS (`82.221.101.241`); former RO host retired | https://flokinet.is/privacy/ · https://flokinet.is/vps/ |
| **Hetzner** | Residual peer DE (`178.105.187.178`, default entry); US monopin retired | https://www.hetzner.com/ |

## Standards (non-code)

- **X25519 / Ed25519 / ChaCha20-Poly1305 / HKDF-SHA256** — as implemented by the libraries above.
- **RFC 3526** — MODP groups used for ElGamal/Pedersen parameters.

## Project authorship

Original RPT protocol, node, clients, and status host: **Raskul** and contributors. Source repository **restore-privacy** is **private**. Public docs and paid installers: https://restoreprivacy.online/

Project licence for original code: **proprietary full copyright** — see [LICENSE](LICENSE). Third-party components keep their own licences (tables above).

Privacy: [PRIVACY_POLICY.md](PRIVACY_POLICY.md).
