# Restore Privacy 0.1.9 — release notes (prep)

**Status:** Source / version prep. Multi-platform package rebuild and GitHub
Release assets are **not** required by this change set alone; cut packages when
ready via a `build_release_0.1.9.py` (copy from `build_release_0.1.8.py`).

## Headline

**UK public-IP geo admission removed from all product client connect paths.**

Connect no longer:

- calls third-party geo HTTPS providers (ipapi.co / ipinfo.io / country.is),
- fails closed for non-UK country codes, or
- blocks users solely because a geo lookup failed.

Admission remains **device Ed25519 keys + RPT2 node crypto** only. Node
handshake / `admit_unknown_devices` semantics are **unchanged** (no server-side
regional IP policy added).

## Why

Client-side geo was bypassable, not a real security boundary, and sent the
user’s public IP to third parties before connect — at odds with the product
privacy intent.

## Platforms (source)

| Surface | Change |
|---------|--------|
| Python `client.connect.RptClient` | No UK gate; `client/uk_gate.py` removed |
| Windows / Linux product apps | Inherit shared connect |
| Android `RptVpnService` | No `UkIpGate.checkUkPublicIp` before handshake |
| Apple Packet Tunnel + `RptConnectOrchestrator` | No `RptUkIpGate` before secrets/handshake |

Leftover `UkIpGate.kt` / `RptUkIpGate.swift` helpers (if still in tree) are
**not** on the product connect success path.

## Upgrade note

**Installed 0.1.8 (and older) clients still enforce the UK geo check** until
users upgrade to a 0.1.9 build. Source tree and `client/VERSION` are 0.1.9;
public download catalog may still list 0.1.8 assets until packages are cut.

## Operator

- Do **not** reintroduce live geo on the node for “UK-only” without a separate
  product decision (privacy + no-log tension).
- Release gates (`_assert_no_priv`, never force-add `secrets/`) unchanged.
