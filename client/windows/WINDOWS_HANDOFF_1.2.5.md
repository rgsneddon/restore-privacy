# Windows brand breadcrumbs — monopin 1.2.5

**Audience:** Windows x64 build machine. Native-rebuild the Windows PE for 1.2.5.

**Catalog monopin:** `1.2.5`

**Target PE:** `releases\1.2.5\restore-privacy-client-1.2.5-windows-x64-setup.exe`

## Product truth (unchanged)

Residual VPN. Catalog entries: **Germany (DE)** default and **Singapore (SG)** (`5.223.48.8`, pin `sg_node_elgamal.pub`). Iceland is not offered. Tray exactly `Privacy, Restored`. Quit lower-left disconnect-then-exit. Kill-switch ON requires typing `KILLSWITCH`.

## Singapore catalog (added)

The Windows PE **must** ship `product/sg_node_elgamal.pub` and show Singapore in the entry-country menu. Choosing Singapore dials `5.223.48.8:44044` with the SG pin (never the DE pin). Do **not** rebuild or overwrite the Helsinki Windows 1.2.5 PE from a Mac. After this source lands, rebuild the PE on the Windows machine and upload it:

```bat
python scripts\build_windows_multihop.py --version 1.2.5
python scripts\host_paid_assets_vps.py --stage --upload --version 1.2.5 --force
```

Helsinki breadcrumbs (`WINDOWS_HANDOFF.md` in the vault) is the live instruction set — not a GitHub queue.

## Deltas since 1.2.4 (this PE must pick up)

| Area | Change |
|------|--------|
| Attach | Session-ready → Connected fail-fast; LUID IF index; pin bound to physical IF |
| DATA gate | Valid DNS A probe (`seal_unicast_probe`); fail-closed if `udp_to_tun=0` |
| IPv6 | Fast `route -6 delete ::/0` on Connect; Disable-NetAdapterBinding off-thread (12s) |
| Tray | Per-PID class; no UnregisterClassW; GetClassInfoW before RegisterClassW |
| DNS | IF DNS stamped off-thread (`rpt-dns`); public 1.1.1.1/9.9.9.9 when Unbound silent |

## Build

```bat
cd /d C:\Users\rgsne\restore_privacy
type client\VERSION
rem MUST print: 1.2.5
python scripts\build_windows_multihop.py --version 1.2.5
```

Output: `releases\1.2.5\restore-privacy-client-1.2.5-windows-x64-setup.exe`

Unsigned PE is allowed when Authenticode funds are unavailable (same as 1.2.4).

## Host

```bat
python scripts\host_paid_assets_vps.py --stage --upload --version 1.2.5 --force
```

Helsinki: `/opt/restore-privacy/paid_assets/1.2.5/restore-privacy-client-1.2.5-windows-x64-setup.exe`
