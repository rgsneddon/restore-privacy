# Windows brand breadcrumbs — monopin 1.2.0

**Audience:** Windows x64 build machine operator.  
**You must native-rebuild the Windows PE for 1.2.0.** Mac agents only stage carry-forward EXE; that is **not** a seal.

Fetch this doc via Helsinki breadcrumbs vault:

```bat
python scripts\breadcrumbs_vault.py check --fetch
```

(requires `RPT_ASSET_FETCH_TOKEN` / vault credentials)

**Catalog monopin:** `1.2.0` — must match `client\VERSION`.

**Target PE basename (exact):**

```text
releases\1.2.0\restore-privacy-client-1.2.0-windows-x64-setup.exe
```

---

## 0. Product truth that MUST be in this PE (1.2.0)

| Topic | Required in sealed Windows build |
|-------|----------------------------------|
| Shell | **Residual VPN only** — no Evolve / % / rpAI main-bar chrome |
| First-use | **Licence** (scroll-to-bottom) → **KEYGEN** or **72h trial** → main VPN |
| Quit | Lower-left; disconnect residual then process exit |
| Tray text | Exactly **`Privacy, Restored`** |
| Residual peers | IS + DE only |
| Full-tunnel honesty | Product **Connected** only when residual capture (Wintun / full tunnel) is active — not host-only HELLO |

---

## 0b. OBSERVE — dual device identity (parity with macOS 1.2.0 fix)

macOS residual Connect failed when **host HELLO** used one `client_ed25519.priv` (often under `~/.restore-privacy/secrets`, KEYGEN-bound) while **Packet Tunnel** used a **different** key in the App Group. Symptom:

- Connect log: node assigned `10.88.0.x` (HELLO OK)
- Then: tunnel / full residual not active (public IP unchanged)
- **Not** trial-expired when a node IP was assigned

### Windows — check the same class of bug before claiming PE seal

Secrets search order is in `client/secrets_loader.py` (`candidate_secrets_dirs`, `preferred_writable_secrets_dir`).

**Paths to inspect on the Windows machine** (after install + KEYGEN/trial + Connect attempt):

| Store | Typical path |
|-------|----------------|
| User home secrets | `%USERPROFILE%\.restore-privacy\secrets\client_ed25519.priv` |
| LocalAppData / Programs | `%LOCALAPPDATA%\Programs\RestorePrivacy\secrets\client_ed25519.priv` |
| ProgramData / machine | `%ProgramData%\RestorePrivacy\secrets\` (if used) |
| Install tree | install dir `secrets\` (package — **must not** adopt package `.priv` as device identity) |

**Operator checks (PowerShell):**

```powershell
# After Connect attempt with KEYGEN or active trial:
$paths = @(
  "$env:USERPROFILE\.restore-privacy\secrets\client_ed25519.priv",
  "$env:LOCALAPPDATA\Programs\RestorePrivacy\secrets\client_ed25519.priv"
)
foreach ($p in $paths) {
  if (Test-Path $p) {
    $h = Get-FileHash $p -Algorithm SHA256
    Write-Host ("{0}  {1}  bytes={2}" -f $h.Hash.Substring(0,16), $p, (Get-Item $p).Length)
  } else {
    Write-Host "MISSING  $p"
  }
}
```

| Observation | Action |
|-------------|--------|
| **Two different 32-byte priv hashes** under home vs LocalAppData/Programs | **FAIL** — same dual-identity class as macOS. Host residual HELLO may succeed while Wintun/full-tunnel path uses another key. Fix: unify to one device key (prefer the KEYGEN-bound store) before Connect; mirror macOS `unifyDeviceAdmissionKeysAcrossWritables` policy in `secrets_loader` if missing. |
| **One priv only**, Connect still “HELLO OK / no residual capture” | Log residual capture / Wintun status; not identity split — dig tunnel service. |
| **Trial ended + no KEYGEN** | Expect purchase/KEYGEN copy — **not** tunnel residual wall as primary. |

**Report to Helsinki breadcrumbs / support handoff:**

1. Both hashes (first 16 hex of SHA-256 only is enough).  
2. Whether node IP was assigned (connection log line).  
3. Whether Wintun / residual capture showed active.  
4. client_version from log header (must be 1.2.0).

---

## 1. Ordered steps

### Step 1 — Pull and pin

```bat
cd /d %RPT_WINDOWS_DRIVE%\restore-privacy
git fetch origin
git checkout main
git pull origin main
type client\VERSION
rem MUST print: 1.2.0
```

### Step 2 — Large-drive brand mirror

```powershell
$env:RPT_WINDOWS_DRIVE = "D:\RestorePrivacyMirror"
python scripts\windows_brand_mirror.py plan
python scripts\windows_brand_mirror.py apply --dest $env:RPT_WINDOWS_DRIVE
```

### Step 3 — Readiness

```bat
python scripts\build_windows_multihop.py --check-only --version 1.2.0
```

### Step 4 — Native PE freeze

```bat
python scripts\build_windows_multihop.py --version 1.2.0
```

### Step 5 — Dual-identity observe (this ship)

Run the PowerShell hash check above on a clean user profile **and** on a profile that previously had KEYGEN / older monopin. Document results under operator notes / vault response.

### Step 6 — Upload Helsinki

Upload:

```text
releases\1.2.0\restore-privacy-client-1.2.0-windows-x64-setup.exe
```

to `paid_assets/1.2.0/` on Helsinki (native PE only — no 0.5.8 CF).

Then re-publish breadcrumbs from any machine:

```bat
python scripts\breadcrumbs_vault.py publish
```

---

## 2. Helsinki vault files (after publish)

- `breadcrumbs/current/manifest.json` — `windows_actions` includes dual-identity observe  
- `breadcrumbs/current/WINDOWS_HANDOFF.md` — this document  
- `breadcrumbs/current/WINDOWS_BRAND_CHECKLIST.md`  
- `breadcrumbs/current/windows_brand_mirror.json`  

---

> **Breadcrumbs vault (Helsinki)** is the source of truth for “what to update”.  
> Fetch: `https://135.181.152.10.sslip.io/breadcrumbs/current/manifest.json` with `X-RPT-Asset-Token`.

---

## Brand-wide large-drive mirror (all installer slots)

The Windows **larger drive** must hold a working monorepo copy **and** every brand
asset from the inventory — not only the Suite Windows setup.exe.

| | |
|--|--|
| **Env** | `RPT_WINDOWS_DRIVE` (or `--dest`) = large-drive root |
| **Monorepo dest** | `{RPT_WINDOWS_DRIVE}/restore-privacy` |
| **Brand slots** | **35** (browser, node_installer, node_operator, rpmail, rpoffice, rpos, rpos_app, suite_client) |
| **Monopin** | **1.2.0** |

```powershell
$env:RPT_WINDOWS_DRIVE = "D:\RestorePrivacyMirror"   # larger drive
python scripts\windows_brand_mirror.py plan
python scripts\windows_brand_mirror.py apply --dest $env:RPT_WINDOWS_DRIVE
```

Inventory kinds covered: suite_client, browser/Rx, rpos, rpos_app (Pens/Tables/Slides),
node_installer, node_operator, rpmail, rpoffice.

Full checklist: vault `WINDOWS_BRAND_CHECKLIST.md` / `windows_brand_mirror.json`
(after `python scripts\breadcrumbs_vault.py stage`).

Native PE remains required: `scripts\build_windows_multihop.py` →
`releases\1.2.0\restore-privacy-client-1.2.0-windows-x64-setup.exe`.
