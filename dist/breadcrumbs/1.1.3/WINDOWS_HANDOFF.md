# Windows brand breadcrumbs — monopin 1.1.3

**Audience:** Windows build machine operator. This is the **full product map**
for Suite **1.1.3**: client architecture, residual fleet, **Ned / rpAI / oracle**,
**every status-host admin surface**, fulfilment, brand companions, and PE rebuild.
Fetch via Helsinki breadcrumbs vault when published
(`scripts/breadcrumbs_vault.py check --fetch`).

**Catalog monopin:** `1.1.3` (`client/VERSION` must match).

**Target Suite PE (must match basename):**

```text
releases/1.1.3/restore-privacy-client-1.1.3-windows-x64-setup.exe
```

Honesty: Mac may stage a **carry-forward** PE under that filename until this
machine rebuilds and Authenticode-seals a native **1.1.3** installer. Do not
claim native Windows seal complete until you have built and signed here.
Architecture below is product truth regardless of PE carry-forward.


**1.1.3 ship notes (this monopin):**

| Topic | 1.1.3 product truth |
|-------|---------------------|
| Fresh main bar | **VPN + rpAI only**; % wallet and EVOLVE **not** installed until Settings → Suite parts → Install |
| Optional install | Installing wallet/Evolve expands destinations; **no second KEYGEN** solely to add a part; VPN always installed |
| Splash identity | First-run account create/login is the only Suite identity gate — no secondary Evolve/% login walls after setup |
| First-run seed | Timed seed attach/publish after “I’ve written them down” (no unbounded hang); local envelope required; network backup best-effort |
| Licence step | Full end-user LICENSE scroll pane; accept only after scroll-to-bottom; public link `https://restoreprivacy.online/LICENSE` |
| Family rehydrate | Suite step-1 session rehydrates on family host (`suiteSplashIdentityActive`); Analysis/Voting when Evolve installed + access |
| macOS VPN prep | Sequenced prepare → await → open System Settings if needed → Connect (no simultaneous popup burst) |
| Residual peers | IS+DE only (US retired) — unchanged |
| Free Suite download | Five catalog basenames under Helsinki `paid_assets/1.1.3/` |
| Residual leak posture | Settings **Residual leak posture**: Minimal only when residual capture + tunnel DNS + IPv6 residual + leak-test PASS; honesty footnote forbids absolute zero-leak claims |
| Residual watchdog | TunnelHome timer calls `evaluateResidualWatchdog` while Connected; surfaces capture/IPv6/DNS drop on Home + status |
| Live leak probes | Settings `collectProductLeakTestInputs` — live DNS plan + public IP vs residual peers; **no invented PASS** |
| Home residual leak posture | Panel while residual-connected (same pure evaluator as Settings) |
| Private DNS / DoH | Settings guidance: OS Private DNS / public DoH may bypass tunnel DNS |
| WebRTC/STUN | Settings guidance: browser WebRTC not claimed residual-proof |
| Kill-switch | Opt-in Settings toggle; **product default OFF** (fail-closed when armed) |
| residual_core C++ | X25519 (RFC7748) + ChaCha20-Poly1305 + PFS IKM/HKDF; `residual_core/` CMake; host-side link later — not Flutter dataplane |
| Linux rebuild | On this Windows machine: rebuild `linux-x64.tar.gz` under monopin 1.1.3; Mac may stage carry-forward only |
| Windows PE | Carry-forward under 1.1.3 basename until **native Authenticode seal on this machine** |
| Linux tarball | Carry-forward under 1.1.3 until native rebuild here |


---

## 0. End-to-end product map (one page)

```text
Public shop (restoreprivacy.online)
  ├── Free Suite installer download (all 5 platforms) — no residual until KEYGEN/trial
  ├── /pay Stripe Checkout KEYGEN (monthly/yearly GBP) — trial_period_days = 0
  └── Public status title-only (no client counts)

Client Suite (this PE / Flutter / native)
  ├── First-run: account → 12-word seed → licence  BEFORE  residual VPN permissions
  ├── Residual Connect: 72h KEYGEN-free trial (device_pub + install_id) then paid KEYGEN
  ├── Fresh shell main bar: **VPN · rpAI** only (wallet/Evolve install later in Settings)
  ├── After install optionals: Wallet (%) · Backup · Evolve Analysis/Voting · Credit · rpAI·Ned
  └── Settings: Suite parts install/uninstall; updates are manual (catalog free download)

Residual fleet (IS + DE only; US/RO retired)
  ├── Default entry DE; catalog peer IS; multihop residual-via-exit (optional)
  ├── Co-joined node roles: VPN + rpAI + Perccent
  └── Weekly sequential wipe IS → DE (never both at once)

Helsinki paid store
  └── paid_assets/{monopin}/ — authenticated downloads; not public GitHub

Status-host admin (/admin) — full map in §8
  Link Generation · Licences · Fleet · Node Operator · rpOS · rpS (Ned)
  Perc · Support · Accounting · UPLOADS · Processors · 2FA login
```

---

## 1. First-run account creation (observe on clean install)

**Order (product law):** account → 12-word recovery seed → licence acceptance
**before residual VPN permissions** / tunnel prep / Connect.

Clean install **must not** open residual VPN / tunnel permissions first.

| Order | Gate | Operator notes |
|------:|------|----------------|
| 1 | **Suite account** | Username + password (Evolve-style portal). One Suite identity for % wallet and Evolve. Credentials stay **on device** — not uploaded to residual nodes. |
| 2 | **12-word recovery seed** | BIP39 recovery phrase; strong offline write-down advice. Restores Suite account / % / Evolve identity on reinstall. |
| 3 | **End-user licence** | Licence acceptance before full shell. |
| 4 | **Suite shell** | Only after account + seed + licence: main bar (VPN · % family · Evolve · rpAI). |
| 5 | **Residual permissions** | VPN / Packet Tunnel (or Windows tunnel prep) only **after** first-run complete. |

Product truth (Flutter): `client_app/lib/first_run_gate.dart` —
`account → seed → licence → complete`; `mayRequestResidualPermissions` is false
until first-run is done. Connect still requires trial or KEYGEN after entry.

**Windows observe checklist**

1. Fresh profile / wipe app data → portal shows **Create your Restore Privacy Suite account** first.  
2. After account: **Backup: 12-word recovery phrase** (not stub words).  
3. After seed: licence step.  
4. Only then: Suite chrome + residual Connect path.  
5. Confirm Settings does not offer residual Connect entitlement before first-run complete.

---

## 2. Free residual trial (KEYGEN-free) then pay

| Topic | Product truth |
|-------|----------------|
| Duration | **72 hours (3 days)** residual Connect trial |
| Card | **No card** for the free trial |
| Binding | Host binds trial to **`device_pub`** and durable **`install_id`** (best-effort reinstall mitigation) |
| After trial | Residual **Connect blocked** until **paid KEYGEN** / active subscription |
| Stripe Checkout | **`trial_period_days = 0`** — subscription bills immediately; trial is **in-app only**, not on the payment plan |
| Code pins | `status_page/payments.py`: `RESIDUAL_TRIAL_HOURS = 72`, `CATALOG_TRIAL_PERIOD_DAYS = 0` |
| Configure script | `scripts/configure_stripe_payment_link_trial.py` must keep trial=0; if Dashboard still shows a Stripe trial, clear it |

Operator-only (not public privacy copy): same `device_pub` or `install_id` should
not receive a second full trial window after expiry. Do **not** publish
reinstall-for-trial attack-surface wording on public pages.

**Windows observe checklist**

1. After first-run, Connect offers **trial-then-KEYGEN** path (no card-first).  
2. Unlock / boot UI always exposes **Get keygen → shop `/pay`**.  
3. Post-trial: Connect denied without KEYGEN; pay path remains visible.  
4. Do not expect Stripe Checkout free days.

---

## 3. Suite shell architecture (all major client parts)

Restore Privacy Suite is **one shell** with residual VPN plus free product
surfaces. Main destinations (`SuiteNavDest` / product map):

| Surface | User-facing | Role |
|---------|-------------|------|
| **VPN** | Residual VPN | Residual tunnel / Connect (after first-run + trial or KEYGEN) |
| **Wallet (%)** | Wallet / **%** (Perccent) | Shared % / Evolve wallet surface |
| **Backup** | Backup | Security / recovery (enum `security` → label Backup) |
| **Analysis** | Analysis | **Evolve** analyser (when Evolve installed + app access) |
| **Voting** | Voting | **Evolve** FCG voting (when Evolve installed + app access) |
| **Credit** | Credit | Credit surface in % / Evolve family |
| **rpAI · Ned** | rpAI | **Ned** guide / rpAI surface (when rpAI installed) |

Family rule: **% and Evolve** share one product family — Wallet, Backup, Credit,
Analysis, and Voting promote onto the main bar when the corresponding Suite
parts are installed (`suite_parts` + `suite_nav.dart`). VPN is always on the bar;
rpAI/Ned appears when installed.

**Windows observe checklist**

1. After first-run, main bar shows **VPN**.  
2. With wallet/Evolve installed: **Wallet**, **Backup**, **Credit**, and when
   Evolve access is on: **Analysis**, **Voting**.  
3. With rpAI installed: **rpAI** tab (Ned guide content).  
4. Suite updates are **manual** (free Suite download). Discrete “new version available” notice only.  
5. Residual **IS + DE** peers only in product catalog (see §4).

---

## 4. Residual peers + public pins (Windows PE)

Live residual catalog peers:

| Code | Role | Public pin (product/) |
|------|------|------------------------|
| **DE** | Default entry + multihop exit material | `de_node_elgamal.pub` / `exit_node_elgamal.pub` |
| **IS** | Catalog peer (Iceland) | `node_elgamal.pub` |

**United States residual is retired** — do **not** inject `us_node_elgamal.pub`
as a live dial peer. Dials normalize retired US → DE. Never ship `*.priv`.

Windows package path must embed entry + DE/exit pubs (same honesty as Apple
`inject_apple_secrets`: live IS+DE+exit only). Multihop when enabled:
residual-via-exit; not full intermediate onion.

**Fleet wipe cadence:** sequential peers under exclusive lock — **IS then DE**
(never concurrent). Clients hop to a healthy peer while one rebuilds.

---

## 5. Ned · rpAI · oracle · co-join (fleet + client)

### 5.1 Client: rpAI · Ned

- Suite tab **rpAI** hosts the **Ned** product guide / rpAI surface.  
- Install optional via Suite parts (`rpaiInstalled`).  
- Ned does **not** receive user secrets (seed, password, connection logs, KEYGEN
  strings, cards). Privacy strip is absolute on oracle/Ned durable paths.

### 5.2 Residual node co-join

On residual hosts, **three co-joined roles** share one contact surface:

| Role | Purpose |
|------|---------|
| **VPN** | Residual HELLO / session / tunnel |
| **rpAI** | Local Ned-related learning epochs / oracle sync hooks |
| **Perccent** | % chain health / seed ticks (co-located heartbeat) |

Code: `node/cojoined_roles.py`. Clients dial monopin residual host:port once.

### 5.3 Helsinki oracle + Ned absorb (admin rpS)

| Piece | Path / role |
|-------|-------------|
| Oracle collate | `node/oracle_master.py` — pure collate of satellite heartbeats |
| Live residual peers in collate | **IS + DE only** (US/RO retired if reported) |
| Suite surfaces in collate | vpn, wallet, backup, analysis, voting, credit, rpai |
| Ned absorb | `ned_learn_oracle` — growth counters, learned surfaces, housework tags |
| Ops counters only | trial_claims / keygen_entitled **ints** — never KEYGEN strings or cards |
| Admin rpS UI | status host **`/admin/rps`** — readiness + Ned growth public snapshot |
| Persistence | `admin_rps` stats path — stripped of forbidden user keys |

**Windows machine must understand:** rebuilding the PE does not train Ned. Ned
growth comes from **Helsinki oracle collate + admin rpS absorb** of fleet
heartbeats. Client rpAI tab is the user-facing Ned guide, not the training loop.

---

## 6. Status-host admin — complete map

**Base:** public shop / status process (e.g. Render / restoreprivacy.online).
Login: `/admin` with `RPT_ADMIN_USER` / `RPT_ADMIN_PASSWORD` (+ optional 2FA).
Session: `RPT_ADMIN_SESSION_SECRET`. Durable licences/grants on **payment disk**,
not residual scratch.

### 6.1 Sidebar (every surface)

| Nav | Path | What it is |
|-----|------|------------|
| **Home** | `/admin` | Architecture blurb + payment readiness summary |
| **Link Generation** | `/admin/link-generation` | Failsafe links & KEYGENs (see §6.2) |
| **Active Licences** | `/admin/licences` | Licence DB + paid download grants |
| **Fleet** | `/admin/fleet` | Fleet bandwidth / node usage probes |
| **Node Operator** | `/admin/node-operator` | Residual node control (IS/DE tabs): co-join, capacity, package deploy to Helsinki |
| **rpOS** | `/admin/rpos` | Desktop RESTORE OS brand admin surface |
| **rpS** | `/admin/rps` | **Ned / admin rpS** readiness + growth (oracle absorb) |
| **Perc** | `/admin/perc` | Perccent chain / % admin surface |
| **Support tickets** | `/admin/support-tickets` | Operator support inbox |
| **Accounting** | `/admin/accounting` | RASKUL LTD accounting |
| **UPLOADS** | `/admin/uploads` | Suite monopin packages → Helsinki paid_assets only (no client push) |
| **Processors** | `/admin/processors` | Processor plugins / connection variables |
| **Logout** | `/admin/logout` | End admin session |

### 6.2 Link Generation (detail)

| Tool | Purpose |
|------|---------|
| Re-issue by purchase ID | Fresh paid download URL for an existing Stripe purchase |
| Generate download (failsafe) | On-demand catalog package mint (platform dropdown) |
| Generate KEYGEN (failsafe) | Mint KEYGEN without full Checkout path (operator) |
| One-month tester | Tester entitlement window |
| Seed test purchase | Only if `RPT_ADMIN_SEED_PURCHASE=1` (lab) |

Also: clear-licences / clear-grants forms where exposed — durable disk ops.

### 6.3 UPLOADS (Suite push — critical for this machine)

Path: **`/admin/uploads`**. Inventory = **Suite client only** at current monopin
(windows / android / macos / ios / linux) — not full brand by default.

| Action | Behaviour |
|--------|-----------|
| **Push selected packages to Helsinki** | Stage + upload checked files to `paid_assets/{monopin}/` (async progress). Dry-run available. |
| **Client updates** | Residual client update push **disabled** — users update manually from free Suite download; older clients see discrete upgrade notice |
| **Browse / path upload** | Single local installer path → stage/upload Helsinki |

After you seal a native Windows PE: upload Windows file, confirm host sha/size
equals Helsinki (for honest catalog hosting).

### 6.4 Node Operator (residual control)

Path: **`/admin/node-operator`**.

- Node selector tabs (IS / DE / lab).  
- Co-join readiness (vpn / rpai / perccent).  
- Capacity live/capacity.  
- Package inventory + Helsinki deploy (can still be brand-aware on that page).  
- SSH key missing for package host → forced browser redirect to app-testers (product rule).

### 6.5 Fleet · Perc · rpOS · Support · Accounting · Processors

| Surface | Operator purpose |
|---------|------------------|
| **Fleet** | Package-host / residual bandwidth used vs capability (token probes) |
| **Perc** | Perccent / % chain ops on Helsinki explorer path |
| **rpOS** | Desktop RESTORE OS brand (not mobile residual) |
| **Support** | Tickets inbox, close/clear |
| **Accounting** | RASKUL LTD books surface |
| **Processors** | Plugin connection variables (apply form) |

### 6.6 Security / privacy admin rules

- Public status: **title-only** (no live client counts).  
- No `.priv` in installers or paid assets.  
- Oracle/Ned never durable-store seed, password, connection_log, KEYGEN string,
  card numbers, reinstall-trial attack prose.  
- 2FA setup/verify paths under `/admin/2fa/*` when enabled.

---

## 7. Public shop + payments (customer path)

| Item | Truth |
|------|--------|
| Free Suite download | Shop catalog five platforms; download ≠ residual unlock |
| KEYGEN unlock | After Stripe; monthly / yearly GBP prices in `payments.py` |
| Webhook | Stripe → status host fulfilment email + grant + KEYGEN |
| Custom domain | pay.restoreprivacy.online (Checkout branding limits apply) |
| Trial | **In-app only**; Stripe `CATALOG_TRIAL_PERIOD_DAYS = 0` |

---

## 8. Brand companions (beyond Suite PE)

Not all required for residual smoke, but Windows brand mirror may stage them:

| Brand | Notes |
|-------|--------|
| **Suite client** | This monopin PE + other OS packages |
| **Rx browser** | `restore-privacy-rx-browser-1.1.3-windows.zip` (optional) |
| **rpOS** | Desktop Windows/macOS/Linux; free Pens · Tables · Slides after install |
| **rpMail / rpOffice** | Brand desktop package slots |
| **Node installer / node-operator** | Operator-facing residual host packages |
| **Browser extension** | Separate browser slot in brand inventory |

Large-drive mirror: `RPT_WINDOWS_DRIVE` + `python scripts/windows_brand_mirror.py apply`.

---

## 9. On the Windows build machine (ordered)

1. Sync monorepo; confirm `client/VERSION` = **`1.1.3`**.  
2. Read **this entire handoff** (client + admin + Ned + fleet).  
3. Optional: `set RPT_WINDOWS_DRIVE=…` → `python scripts/windows_brand_mirror.py apply`.  
4. Build native PE (MSVC / Inno / multihop recipe as used on this host).  
5. Output name: `restore-privacy-client-1.1.3-windows-x64-setup.exe`.  
6. Authenticode-sign.  
7. Stage → `status_page/assets/1.1.3/` and `releases/1.1.3/`.  
8. Helsinki: admin **UPLOADS** or `host_paid_assets_vps` (Windows file).  
9. Confirm host size == Helsinki size for Windows package honesty.  
10. Breadcrumbs: `python3 scripts/breadcrumbs_vault.py stage --version 1.1.3` (+ publish).  
11. Smoke client: first-run → trial → Suite bar (VPN · % · Evolve · Backup · Credit · rpAI/Ned).  
12. Smoke residual: IS/DE only; no US live peer.  
13. Optionally open status **admin** (credentials from ops vault) and verify UPLOADS /
    Node Operator / **rpS (Ned)** pages load — do not treat admin as part of the PE.

### Smoke after PE install (architecture observation)

- First-run: account → seed → licence → shell (no VPN permission first).  
- Trial: 72h KEYGEN-free residual; then KEYGEN /pay.  
- Suite bar: VPN, %, Evolve (Analysis/Voting), Backup, Credit, rpAI/Ned when installed.  
- Residual catalog: IS + DE only.  
- Stripe: no Checkout trial days.  
- Suite updates are manual (no admin client push).

---

## 10. Operator notes (Stripe + fulfilment)

- Code: `CATALOG_TRIAL_PERIOD_DAYS = 0`; Checkout omits subscription trial days.  
- Residual free trial remains host **device_trial** only (in-app).  
- Paid installers: Helsinki `paid_assets/1.1.3/` (token-gated).  
- Admin UPLOADS: Suite-only inventory to Helsinki (no residual client push).  
- Licence/grant DB: durable payment disk — survives residual wipe / redeploy.

---

## 11. Monorepo truth table (read-only pointers)

| Topic | Location |
|-------|----------|
| First-run gate | `client_app/lib/first_run_gate.dart`, `first_run_portal.dart` |
| Suite nav / parts | `client_app/lib/suite_nav.dart`, `suite_parts.dart` |
| Trial / Stripe | `status_page/payments.py` |
| Residual peers | `client/multihop.py` |
| Co-join roles | `node/cojoined_roles.py` |
| Oracle + Ned absorb | `node/oracle_master.py`, `status_page/admin_rps.py` |
| Updates | Manual free Suite download; upgrade banner for old monopin |
| Helsinki package host | `scripts/host_paid_assets_vps.py` |
| Admin shell | `status_page/admin_panel.py` (sidebar + all pages) |
| Node Operator UI | `status_page/admin_node_operator.py` |
| Apple inject (parity) | `scripts/inject_apple_secrets.py` |
| Breadcrumbs vault | `scripts/breadcrumbs_vault.py` (stages this file as `WINDOWS_HANDOFF.md`) |
| Brand mirror | `scripts/windows_brand_mirror.py` |
| Paid assets host | `scripts/host_paid_assets_vps.py` |

---

## Companions (optional same monopin)

- `restore-privacy-rx-browser-1.1.3-windows.zip` if Rx browser ships with this monopin.  
- Brand-wide slots (rpOS, Pens, node-installer, …) via brand mirror — see §8.

## Honest status

- Catalog can serve monopin **1.1.3** with a re-pinned carry-forward PE until
  this machine seals a native Authenticode build.  
- **Everything above** (first-run, trial, Suite shell, Ned/oracle, full admin map,
  fleet, fulfilment) is required operator knowledge even while the PE is still
  carry-forward — validate client UI on a current build and admin on the live
  status host.

---

## Windows + Linux operator continue (1.1.3 leak-posture ship)

### What Mac already did
- Flutter residual leak posture Settings UI + pure policy tests
- residual_core P1 crypto (X25519, ChaCha20-Poly1305) unit-tested
- Catalog monopin **1.1.3** packages staged; macOS DevID notarized when sealed here
- Helsinki `paid_assets/1.1.3/` + breadcrumbs vault current
- Windows PE / Linux tar may be **carry-forward** basenames until native rebuild here

### Windows PE seal (required for honest native Windows ship)
1. `python scripts/breadcrumbs_vault.py check --fetch`
2. Open this file + monorepo at monopin 1.1.3
3. Rebuild suite PE → `releases/1.1.3/restore-privacy-client-1.1.3-windows-x64-setup.exe`
4. Authenticode-sign; upload Helsinki paid_assets/1.1.3
5. Re-publish breadcrumbs; re-run free-DL probe for windows basename

### Linux rebuild (on Windows build host or Linux agent)
1. Rebuild `restore-privacy-client-1.1.3-linux-x64.tar.gz` from monorepo
2. Stage + Helsinki upload same monopin
3. Note: Mac cannot produce native Linux seal authenticity claims

### Observe leak posture on Windows clean install
1. First residual Connect → Settings → Residual leak posture
2. Run Leak test while Connected → expect path to **Minimal** only if capture + IPv6 + tunnel DNS + PASS
3. Confirm kill-switch default OFF; Private DNS + WebRTC guidance visible
4. Forbidden: any UI string promising absolute zero leakage

### residual_core note for Windows
```
cmake -S residual_core -B residual_core/build -DOPENSSL_ROOT_DIR=...
cmake --build residual_core/build
residual_core\build\residual_core_tests.exe
```
Link into residual host process later (not Flutter isolate).

---

> **Breadcrumbs vault (Helsinki)** is the source of truth for “what to update” on this monopin. Do **not** treat a private GitHub pull of this file as the primary task queue.
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
| **Monopin** | **1.1.3** |

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
`releases\1.1.3\restore-privacy-client-1.1.3-windows-x64-setup.exe`.
