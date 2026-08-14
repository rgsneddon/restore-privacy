# Windows brand breadcrumbs — monopin 1.2.6

**Audience:** Windows x64 build machine only.

**Do not build or Authenticode-sign this PE on a Mac.** Helsinki
`paid_assets/1.2.5/restore-privacy-client-1.2.5-windows-x64-setup.exe` stays
until **this** machine uploads `paid_assets/1.2.6/`.

Helsinki breadcrumbs (`WINDOWS_HANDOFF.md` in the vault) is the live
instruction set — not a GitHub queue.

| | |
|--|--|
| **Catalog monopin** | `1.2.6` |
| **Target PE** | `releases\1.2.6\restore-privacy-client-1.2.6-windows-x64-setup.exe` |
| **Live residual menu** | Germany (DE) default + Singapore (SG) |
| **Singapore host** | `5.223.48.8:44044` UDP |
| **Singapore pin** | `product/sg_node_elgamal.pub` |
| **Germany host** | `178.105.187.178:44044` UDP |
| **Germany pin** | `product/de_node_elgamal.pub` |
| **Not offered** | Iceland, United States, Romania |

## 0. Fetch this brief from Helsinki

On the Windows machine:

```bat
git pull
type client\VERSION
rem MUST print: 1.2.6
type client\windows\WINDOWS_HANDOFF_1.2.6.md
```

Or pull the live vault (source of truth):

`/opt/restore-privacy/breadcrumbs/current/WINDOWS_HANDOFF.md`

## 1. Product truth (this PE)

- Residual VPN only. Tray text exactly `Privacy, Restored`.
- Quit (lower-left) disconnects then exits.
- Kill-switch ON requires typing `KILLSWITCH`.
- Settings country menu: **Germany** and **Singapore** only.
- Choosing Singapore dials `5.223.48.8:44044` with `sg_node_elgamal.pub`.
  Never the DE pin. Never Iceland `node_elgamal.pub`.
- Flag decoration is emoji (`🇸🇬` / `🇩🇪`); no extra `flags\sg.png` is required.

## 2. What the Mac already did (do not repeat)

- Catalog pin 1.2.6 committed (`c1b0da5` and follow-ups).
- Android / macOS / iOS 1.2.6 uploaded to Helsinki `paid_assets/1.2.6/`.
- Downloads Map: Windows still **1.2.5**; Android/macOS/iOS **1.2.6**.
- Audit schedule is DE+SG (Iceland is not a live connectivity peer).
- **No** Windows PE was built or restamped on the Mac.

## 3. Source gates before freeze

```bat
cd /d C:\Users\rgsne\restore_privacy
python scripts\build_windows_multihop.py --check-only --version 1.2.6
```

Must be OK. Must see `product\sg_node_elgamal.pub` present (256 bytes).

Recipe `scripts\build_release_0.0.8.py` `inject_product_secrets` now **requires**
`sg_node_elgamal.pub` (same as `de_node_elgamal.pub`). A PE without that file
must not be uploaded.

## 4. Native PE freeze (Windows x64 only)

```bat
cd /d C:\Users\rgsne\restore_privacy
git pull
type client\VERSION
rem MUST print: 1.2.6
python scripts\build_windows_multihop.py --version 1.2.6
```

Output: `releases\1.2.6\restore-privacy-client-1.2.6-windows-x64-setup.exe`

Unsigned PE is allowed when Authenticode funds are unavailable (same as 1.2.5).

After freeze, confirm the setup (or onedir `product\` / `secrets\`) contains:

- `sg_node_elgamal.pub`
- `de_node_elgamal.pub`
- no `*.priv`

## 5. Upload to Helsinki (1.2.6 folder only)

```bat
python scripts\host_paid_assets_vps.py --stage --upload --version 1.2.6 --force
```

Remote: `/opt/restore-privacy/paid_assets/1.2.6/restore-privacy-client-1.2.6-windows-x64-setup.exe`

That upload should move the Downloads Map **Windows** row from 1.2.5 to 1.2.6.

**Do not** overwrite or delete
`paid_assets/1.2.5/restore-privacy-client-1.2.5-windows-x64-setup.exe`.

## 6. Observe after first Connect

1. Menu shows Germany + Singapore; default Germany.
2. Germany Connect → HELLO to `178.105.187.178` with `de_node_elgamal.pub`.
3. Singapore Connect → HELLO to `5.223.48.8` with `sg_node_elgamal.pub`.
4. Hash `client_ed25519.priv` under
   `%USERPROFILE%\.restore-privacy\secrets` and
   `%LOCALAPPDATA%\Programs\RestorePrivacy\secrets` — they must match.
5. Tray: `Privacy, Restored`. Quit lower-left disconnects then exits.

## 7. Deltas this PE must pick up (1.2.5 attach + 1.2.6 catalog)

| Area | Change |
|------|--------|
| Pin | `client/VERSION` **1.2.6** |
| Catalog | DE default + SG; Iceland forgotten as live |
| HELLO | `5.223.48.8` → `sg_node_elgamal.pub` |
| Secrets seed | `CATALOG_PUBLIC_PUBS` + `CATALOG_NODE_PUB_NAMES` include SG |
| Attach | Session-ready → Connected fail-fast; LUID IF index |
| DATA gate | `seal_unicast_probe`; fail-closed if `udp_to_tun=0` |
| IPv6 | Fast `route -6 delete ::/0` on Connect |
| Tray | Per-PID class; `GetClassInfoW` before `RegisterClassW` |
| DNS | IF DNS stamped off-thread (`rpt-dns`) |
