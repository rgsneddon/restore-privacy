# Windows brand breadcrumbs — monopin 1.2.1

**Audience:** Windows x64 build machine operator (and Linux/Arch rebuild when done here).  
**You must native-rebuild the Windows PE for 1.2.1.** Mac agents only stage carry-forward EXE; that is **not** a seal.

Fetch this doc via Helsinki breadcrumbs vault when published:

```bat
python scripts\breadcrumbs_vault.py check --fetch
```

(requires `RPT_ASSET_FETCH_TOKEN` / vault credentials)

**Catalog monopin:** `1.2.1`

## Mac agent staging status (1.2.1)

Darwin suite build produced **android / macos / ios / linux** under `releases/1.2.1/`.
**No Windows PE was present locally to carry-forward** — catalog Windows for 1.2.1 is **blocked** until this machine runs the freeze below. Do not upload a renamed 1.2.0 EXE as 1.2.1.

Linux tarball was **carry-forward** from monopin 1.2.0 (same bytes; re-pinned filename only). Rebuild on Linux/Arch when convenient.

 — must match `client\VERSION`.

**Target PE basename (exact):**

```text
releases\1.2.1\restore-privacy-client-1.2.1-windows-x64-setup.exe
```

**Do not** rename an ancient PE (e.g. payload `RestorePrivacy-0.5.8.exe`, tray `rpT0`, or monopin 1.1.5/1.1.6 carry) and claim 1.2.1 seal.

---

## 0. Product truth that MUST be in this PE (1.2.1)

| Topic | Required in sealed Windows build |
|-------|----------------------------------|
| Shell | **Residual VPN only** — no Evolve analysis, Perccent wallet (%), rpAI/Ned, or Backup main-bar chrome |
| First-use | **Licence** (full text, scroll-to-bottom accept) → **KEYGEN paste** or **continue 72h trial** → main VPN |
| First-use **not** | Username/password Suite account, 12-word seed gate, multi-product splash |
| Return visit | Trial remaining **or** valid KEYGEN; if trial expired KEYGEN is mandatory |
| Quit | Control at **lower-left** of main connection screen; **disconnect residual then full process exit** (not hide-to-tray with tunnel up) |
| Kill-switch enable | Settings kill-switch **ON** requires confirm dialog **ARE YOU SURE?** + user types exactly **`KILLSWITCH`** before opt-in saves; wrong/cancel leaves OFF |
| Kill-switch disable | Slider/switch to **OFF** alone — **no** typed confirm |
| System tray text | Exactly **`Privacy, Restored`** (comma + capital R) — durable for this and future monopin ships |
| Tray **not** | `rpT0`, or `Privacy Restored` without the comma |
| Self-update | **No** admin UPDATE_PUSH / in-app auto PE receive — manual free catalog download only |
| Residual peers | IS + DE only (US retired) |
| Trial | 72-hour KEYGEN-free device trial, then paid KEYGEN |

Source of truth in tree (after `git pull`):

| Fact | File / symbol |
|------|----------------|
| Monopin | `client\VERSION` → `1.2.1` |
| Tray constant | `client\windows\tray_win.py` → `TRAY_DISPLAY_NAME = "Privacy, Restored"` |
| Quit order | `client\windows\app.py` → `_quit_app` / `run_quit_residual_teardown` (disconnect then exit); Quit packed **left** |
| Flutter Quit | `client_app\lib\app_quit.dart` → disconnect then `exitAppProcess` (Android: `fullExit` + finishAndRemoveTask) |
| Kill-switch confirm | `client_app\lib\kill_switch_confirm.dart` → `evaluateKillSwitchConfirm` / token `KILLSWITCH` |
| Settings wiring | `client_app\lib\settings_screen.dart` → `_setKillSwitch` |
| Catalog pin | `status_page\downloads.py` → `RELEASE_VERSION = "1.2.1"` |



---

## Deltas since monopin 1.2.0 (Windows PE must pick up)

| Area | Change |
|------|--------|
| Catalog pin | `1.2.1` everywhere (`client\VERSION`, setup basename, tray about if it embeds monopin) |
| Flutter/Android Quit | Full process exit: plain `startService(DISCONNECT)` (never `startForegroundService`), deferred kill after task remove |
| iOS catalog | IPA `Payload/Runner.app` + embedded provisions (Mac-side only; Windows PE unaffected) |
| Residual peers | Unchanged: IS + DE; US retired |
| Tray string | Still exactly **`Privacy, Restored`** |
| Kill-switch | Still `KILLSWITCH` confirm on enable |

**You must still native-rebuild the Windows PE for 1.2.1.** Do not rename the 1.2.0 EXE.


## 1. Ordered steps — do these in order

### Step 1 — Pull and pin check

```bat
cd /d %RPT_WINDOWS_DRIVE%\restore-privacy
rem or your monorepo clone path

git fetch origin
git checkout main
git pull origin main

type client\VERSION
rem MUST print: 1.2.1

findstr /C:"TRAY_DISPLAY_NAME" client\windows\tray_win.py
rem MUST show: TRAY_DISPLAY_NAME = "Privacy, Restored"

findstr /C:"KILLSWITCH" client_app\lib\kill_switch_confirm.dart
rem MUST show: kKillSwitchConfirmToken = 'KILLSWITCH'
```

If pin is not 1.2.1, **stop** — wrong branch or stale pull.

### Step 2 — Optional large-drive monorepo mirror

```powershell
$env:RPT_WINDOWS_DRIVE = "D:\RestorePrivacyMirror"
python scripts\windows_brand_mirror.py plan
python scripts\windows_brand_mirror.py apply --dest $env:RPT_WINDOWS_DRIVE
```

Then build from the mirrored tree so the large drive holds the seal.

### Step 3 — Source readiness (any OS; run on Windows before freeze)

```bat
python scripts\build_windows_multihop.py --check-only --version 1.2.1
```

Expect readiness OK (pubs, multihop, wintun, pin). Fix failures before Step 4.

### Step 4 — Native PE freeze (Windows x64 only)

```bat
python scripts\build_windows_multihop.py --version 1.2.1
rem or double-click / run:
scripts\build_windows_multihop.bat
```

Output path:

```text
releases\1.2.1\restore-privacy-client-1.2.1-windows-x64-setup.exe
```

### Step 5 — Authenticode sign

Sign the setup EXE with the company code-signing certificate (product standard tool / `signtool`).  
Unsigned PE must not be uploaded as the catalog seal.

### Step 6 — Honesty checks before upload

1. **SHA-256 differs** from any prior carry-forward (1.1.6 Mac stage was a different hash — yours must be new).
2. Strings / frozen assets contain tray **`Privacy, Restored`** (not `rpT0`).
3. Clean install: licence scroll → KEYGEN or trial → VPN; **no** username/password first-run.
4. Main UI: Quit **lower-left**; Quit stops residual then exits the process.
5. Settings: kill-switch ON → ARE YOU SURE + type `KILLSWITCH`; OFF is one-switch free.
6. Filename is exactly `restore-privacy-client-1.2.1-windows-x64-setup.exe`.

### Step 7 — Stage and upload to Helsinki paid assets

```bat
python scripts\host_paid_assets_vps.py --stage --upload --version 1.2.1 --force
```

Confirm remote:

```text
/opt/restore-privacy/paid_assets/1.2.1/restore-privacy-client-1.2.1-windows-x64-setup.exe
```

Also mirror under `status_page\assets\1.2.1\` if the script does not already.

### Step 8 — Re-publish breadcrumbs (so the next fetch sees seal status)

```bat
python scripts\breadcrumbs_vault.py stage --version 1.2.1
python scripts\breadcrumbs_vault.py publish
```

---

## 2. Linux / Arch on this machine (optional same day)

If this Windows host also rebuilds Linux:

```bat
python scripts\package_linux.py
rem Output: releases\1.2.1\restore-privacy-client-1.2.1-linux-x64.tar.gz
```

Confirm desktop Name in packaged `install.sh` is exactly **`Privacy, Restored`**.  
Then upload with the same host paid-assets command (version 1.2.1).

**Arch Linux:**

```bat
python scripts\package_arch_linux.py
rem or staged tree under releases\1.2.1\arch
```

PKGBUILD / package monopin must read **1.2.1** (not a stale 1.1.6 carry rename).  
Include kill-switch confirm + Quit product truth above when packaging Flutter or Python residual shells.

---

## 3. What Mac already did (do not re-do as PE)

| Platform | Mac agent status (1.2.1) |
|----------|---------------------------|
| Android | Flutter release APK with kill-switch confirm + fullExit Quit |
| macOS | Residual-team monopin zip (host Packet Tunnel NE + launch alive) |
| iOS | Flutter zip + residual pub inject when recipe green |
| Linux | **Carry-forward until this machine seals** (or package_linux.py here) |
| Windows | **Carry-forward only until this machine seals** |

---

## 4. Residual fleet / ops (context, not PE freeze)

- Residual entry peers: **IS + DE** only.
- Connect entitlement: 72h device trial then KEYGEN (status host / Stripe).
- Node ops / admin surfaces live on status host — not multi-product client chrome.
- Client updates: manual free catalog download (no UPDATE_PUSH receive).
- Kill-switch OS arm may still be product-parked at kernel level; Settings confirm UX is required whenever the opt-in control is exposed.

---

## 5. Failure modes

| Symptom | Fix |
|---------|-----|
| Pin not 1.2.1 after pull | Wrong branch; `git checkout main && git pull` |
| PE still named 1.1.6 | Rebuild with `--version 1.2.1`; do not rename |
| Kill-switch enables without typing | Pull tree with `kill_switch_confirm.dart` + Settings wiring |
| Quit leaves process idle | Ensure disconnect-then-exit path; Flutter shells use `app_quit.dart` |
| Helsinki rejects upload | `--force` with matching monopin CFBundle/VERSION |
