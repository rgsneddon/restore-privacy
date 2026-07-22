# Credits and third-party attributions

Restore Privacy (RPT) is an **original** custom VPN design. The following
components are **utilised** by the shipped tree or release packages. They are
**not** the RPT protocol itself.

## Crypto libraries

| Component | Role in this project | License (upstream) | More information |
|-----------|----------------------|--------------------|------------------|
| **cryptography** (Python) | AEAD (ChaCha20-Poly1305), Ed25519, HKDF, and related primitives used by the node and Windows client | Apache-2.0 / BSD | https://github.com/pyca/cryptography |
| **Bouncy Castle** (`bcprov-jdk18on`) | Android client handshake / AEAD helpers | MIT (Bouncy Castle) | https://www.bouncycastle.org/ |
| **Apple CryptoKit** | iOS/macOS AEAD (ChaCha20-Poly1305), Ed25519, HKDF-SHA256 for RPT2 Packet Tunnel | Apple SDK | https://developer.apple.com/documentation/cryptokit |
| **BigInt** (attaswift, vendored) | 2048-bit modular arithmetic for ElGamal/Pedersen on Apple platforms | MIT | https://github.com/attaswift/BigInt |

Discrete-log **ElGamal** and **Pedersen** constructions in this repo are
implemented for RPT using standard group parameters (**RFC 3526** MODP group
14). RFC text is a standards document; see https://www.rfc-editor.org/rfc/rfc3526.

## Virtual network / TUN

| Component | Role in this project | License (upstream) | More information |
|-----------|----------------------|--------------------|------------------|
| **Wintun** | Windows virtual NIC used only as a **TUN driver** so sealed RPT DATA can carry IP packets; **not** the WireGuard tunnel protocol | GPL-2.0 (Wintun) with redistribution notes on the project site | https://www.wintun.net/ · https://git.zx2c4.com/wintun/ |

The file `client/windows/native/wintun.dll` (when present in packages) is the
upstream Wintun binary. Full-system VPN on Windows requires Administrator rights
to load the adapter and install routes.

## UI frameworks

| Component | Role in this project | License (upstream) | More information |
|-----------|----------------------|--------------------|------------------|
| **Flutter** / **Dart** | Android (and multi-platform scaffold) client UI shell; method channel to native VPN | BSD-3-Clause (Flutter) | https://flutter.dev/ · https://github.com/flutter/flutter |
| **Tkinter** | Windows retro CLI-style window (stdlib / Python) | Python Software Foundation License | https://docs.python.org/3/library/tkinter.html |

Visual design cues (dark blue title bar, black background, white text) are
inspired by classic **Windows 3.x**-era UI chrome for a retro look; no Microsoft
source code is included. Microsoft, Windows, and related names are trademarks of
their owners.

## Packaging and tooling

| Component | Role | License / notes |
|-----------|------|-----------------|
| **PyInstaller** | Optional Windows standalone bundle in release builds | GPL-2.0 with exception (see PyInstaller docs) — https://pyinstaller.org/ |
| **7-Zip / LZMA SDK** (PE SFX stub) | Windows catalog self-extracting setup packaging (`7zSD.sfx`-style) | LZMA SDK public-domain / 7-Zip license as applicable — https://www.7-zip.org/ · https://www.7-zip.org/sdk.html |
| **paramiko** | Optional deploy script SSH helper | LGPL-2.1 — https://www.paramiko.org/ |
| **GitHub** | Private operator source hosting (not a free public installer CDN) | Service terms of GitHub, Inc. |
| **Stripe** | Paid catalog checkout / Payment Link (£2.45 GBP per package) on the status host | Service terms of Stripe — https://stripe.com/ |
| **Render** | Public VPN APP Shop hosting + paid download fulfilment (`restore-privacy-status`) | Service terms of Render — https://render.com/ |
| **FlokiNET** (Flokinet) | Production RPT node VPS in **Iceland** (product host `82.221.101.241`) | Host public privacy materials — https://flokinet.is/privacy/ · https://flokinet.is/vps/ · https://flokinet.is/ |

## Standards and algorithms (non-code)

- **X25519 / Ed25519 / ChaCha20-Poly1305 / HKDF-SHA256** — standard cryptographic algorithms as implemented by the libraries above.
- **RFC 3526** — MODP Diffie-Hellman groups for IETF use (group parameters for ElGamal/Pedersen).

## Project authorship

Original RPT protocol, node, clients, and VPN APP Shop: **Russell G Sneddon** and
contributors (operator repository **restore-privacy** is **private**; public
docs and paid installers: https://restoreprivacy.online/).

Project licence for original code: **proprietary full copyright** — see [`LICENSE`](LICENSE). Third-party components remain under their own licences (table above).

Privacy practices: [`PRIVACY_POLICY.md`](PRIVACY_POLICY.md).
