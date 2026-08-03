# Windows brand breadcrumbs — monopin 1.1.6

**Audience:** Windows x64 build machine operator (and Linux/Arch rebuild when done here).  
**You must native-rebuild the Windows PE for 1.1.6.** Mac agents only stage carry-forward EXE; that is **not** a seal.

Fetch this doc via Helsinki breadcrumbs vault when published:

```bat
python scripts\breadcrumbs_vault.py check --fetch
```

(requires `RPT_ASSET_FETCH_TOKEN` / vault credentials)

**Catalog monopin:** `1.1.6` — must match `client\VERSION`.

**Target PE basename (exact):**

```text
releases\1.1.6\restore-privacy-client-1.1.6-windows-x64-setup.exe
```

**Do not** rename an ancient PE (e.g. payload `RestorePrivacy-0.5.8.exe`, tray `rpT0`, or monopin 1.1.3/1.1.4 carry) and claim 1.1.6 seal.

---

## 0. Product truth that MUST be in this PE (1.1.6)

| Topic | Required in sealed Windows build |
|-------|----------------------------------|
| Shell | **Residual VPN only** — no Evolve analysis, Perccent wallet (%), rpAI/Ned, or Backup main-bar chrome |
| First-use | **Licence** (full text, scroll-to-bottom accept) → **KEYGEN paste** or **continue 72h trial** → main VPN |
| First-use **not** | Username/password Suite account, 12-word seed gate, multi-product splash |
| Return visit | Trial remaining **or** valid KEYGEN; if trial expired KEYGEN is mandatory |
| Quit | Control at **lower-left** of main connection screen; **disconnect residual then full process exit** (not hide-to-tray with tunnel up) |
| System tray text | Exactly **`Privacy, Restored`** (comma + capital R) — durable for this and future monopin ships |
| Tray **not** | `rpT0`, or `Privacy Restored` without the comma |
| Self-update | **No** admin UPDATE_PUSH / in-app auto PE receive — manual free catalog download only |
| Residual peers | IS + DE only (US retired) |
| Trial | 72-hour KEYGEN-free device trial, then paid KEYGEN |

Source of truth in tree (after `git pull`):

| Fact | File / symbol |
|------|----------------|
| Monopin | `client\VERSION` → `1.1.6` |
| Tray constant | `client\windows\tray_win.py` → `TRAY_DISPLAY_NAME = "Privacy, Restored"` |
| Quit order | `client\windows\app.py` → `_quit_app` / `run_quit_residual_teardown` (disconnect then exit); Quit packed **left** |
| Flutter Quit (if packaging Flutter shell) | `client_app\lib\app_quit.dart` → `kQuitButtonPlacement = 'bottomLeft'` |
| First-run policy | `client_app\lib\first_run_gate.dart` → licence → keygenOrTrial → complete |
| Catalog pin | `status_page\downloads.py` → `RELEASE_VERSION = "1.1.6"` |

---

## 1. Ordered steps — do these in order

### Step 1 — Pull and pin check

```bat
cd /d %RPT_WINDOWS_DRIVE%\restore-privacy
rem or your monorepo clone path

git fetch origin
git checkout main
git pull origin main

type client\VERSION
rem MUST print: 1.1.6

findstr /C:"TRAY_DISPLAY_NAME" client\windows\tray_win.py
rem MUST show: TRAY_DISPLAY_NAME = "Privacy, Restored"
```

If pin is not 1.1.6, **stop** — wrong branch or stale pull.

### Step 2 — Optional large-drive monorepo mirror

```powershell
$env:RPT_WINDOWS_DRIVE = "D:\RestorePrivacyMirror"
python scripts\windows_brand_mirror.py plan
python scripts\windows_brand_mirror.py apply --dest $env:RPT_WINDOWS_DRIVE
```

Then build from the mirrored tree so the large drive holds the seal.

### Step 3 — Source readiness (any OS; run on Windows before freeze)

```bat
python scripts\build_windows_multihop.py --check-only --version 1.1.6
```

Expect readiness OK (pubs, multihop, wintun, pin). Fix failures before Step 4.

### Step 4 — Native PE freeze (Windows x64 only)

```bat
python scripts\build_windows_multihop.py --version 1.1.6
rem or double-click / run:
scripts\build_windows_multihop.bat
```

Output path:

```text
releases\1.1.6\restore-privacy-client-1.1.6-windows-x64-setup.exe
```

### Step 5 — Authenticode sign

Sign the setup EXE with the company code-signing certificate (product standard tool / `signtool`).  
Unsigned PE must not be uploaded as the catalog seal.

### Step 6 — Honesty checks before upload

1. **SHA-256 differs** from any prior carry-forward (old Mac stage was sha `3634e975…` — yours must be different).
2. Strings / frozen assets contain tray **`Privacy, Restored`** (not `rpT0`).
3. Clean install: licence scroll → KEYGEN or trial → VPN; **no** username/password first-run.
4. Main UI: Quit **lower-left**; Quit stops residual then exits the process.
5. Filename is exactly `restore-privacy-client-1.1.6-windows-x64-setup.exe`.

### Step 7 — Stage and upload to Helsinki paid assets

```bat
python scripts\host_paid_assets_vps.py --stage --upload --version 1.1.6 --force
```

Confirm remote:

```text
/opt/restore-privacy/paid_assets/1.1.6/restore-privacy-client-1.1.6-windows-x64-setup.exe
```

Also mirror under `status_page\assets\1.1.6\` if the script does not already.

### Step 8 — Re-publish breadcrumbs (so the next fetch sees seal status)

```bat
python scripts\breadcrumbs_vault.py stage --version 1.1.6
python scripts\breadcrumbs_vault.py publish
```

---

## 2. Linux / Arch on this machine (optional same day)

If this Windows host also rebuilds Linux:

```bat
python scripts\package_linux.py
rem Output: releases\1.1.6\restore-privacy-client-1.1.6-linux-x64.tar.gz
```

Confirm desktop Name in packaged `install.sh` is exactly **`Privacy, Restored`**.  
Then upload with the same host paid-assets command (version 1.1.6).

Arch: `scripts\package_arch_linux.py` or staged tree under `releases\1.1.6\arch`.

---

## 3. What Mac already did (do not re-do as PE)

| Platform | Mac agent status (1.1.6) |
|----------|---------------------------|
| Android | Flutter release build staged |
| macOS | Flutter zip, DevID codesign attempted; notary may need credentials |
| iOS | Flutter zip + residual pub inject |
| Linux | `package_linux.py` rebuild with VERSION 1.1.6 + Name=Privacy, Restored |
| Windows | **Carry-forward only until this machine seals** |

---

## 4. Residual fleet / ops (context, not PE freeze)

- Residual entry peers: **IS + DE** only.
- Connect entitlement: 72h device trial then KEYGEN (status host / Stripe).
- Node ops / admin surfaces live on status host — not multi-product client chrome.
- Client updates: manual free catalog download (no UPDATE_PUSH receive).

---

## 5. Failure modes

| Mistake | Result |
|---------|--------|
| Rename old setup.exe to `…1.1.6…` | Catalog lies; tray/Quit/first-run wrong |
| Build without `git pull` | Missing Privacy, Restored / VPN-only first-run |
| Skip Authenticode | Not a product seal |
| Skip host upload | Free-DL still serves stale PE |
| Expect Mac to produce PE | Impossible — PyInstaller is Windows-host only |

---

## 6. One-page operator checklist

```text
[ ] git pull main; client\VERSION == 1.1.6
[ ] tray_win.py TRAY_DISPLAY_NAME == "Privacy, Restored"
[ ] build_windows_multihop.py --check-only --version 1.1.6  → OK
[ ] build_windows_multihop.py --version 1.1.6  → setup.exe created
[ ] Authenticode-sign setup.exe
[ ] Verify tray string + Quit lower-left + no account/seed first-run
[ ] host_paid_assets_vps.py --stage --upload --version 1.1.6 --force
[ ] breadcrumbs_vault.py stage + publish (optional but preferred)
[ ] Confirm paid_assets/1.1.6 Windows basename on Helsinki
```

**You are the seal.** Until these boxes are done, 1.1.6 Windows free-DL is not product-complete.


## 1.1.6 residual honesty

- Status settles when residual is up (no looping “waiting for full tunnel”).
- Leak test PASS under residual privacy settings; kill-switch WARNING bold red.
- Static VPN main screen + Quit lower-left; no multi-product swipe.
