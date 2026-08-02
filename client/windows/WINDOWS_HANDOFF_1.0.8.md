# Windows brand breadcrumbs — monopin 1.0.8

**Audience:** Windows build machine operator. This handoff is the architecture
map for Suite **1.0.8** — first-run, residual trial, shell parts, residual peers,
and the PE rebuild path. Fetch via Helsinki breadcrumbs vault when published
(`scripts/breadcrumbs_vault.py check --fetch`).

**Catalog monopin:** `1.0.8` (`client/VERSION` must match).

**Target PE (must match basename):**

```text
releases/1.0.8/restore-privacy-client-1.0.8-windows-x64-setup.exe
```

Honesty: Mac may stage a **carry-forward** PE under that filename until this
machine rebuilds and Authenticode-seals a native **1.0.8** installer. Do not
claim native Windows seal complete until you have built and signed here.

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

## 3. Suite shell architecture (all major parts)

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
| **rpAI · Ned** | rpAI | Ned guide / rpAI co-join surface |

Family rule: **% and Evolve** share one product family — Wallet, Backup, Credit,
Analysis, and Voting promote onto the main bar when the corresponding Suite
parts are installed (`suite_parts` + `suite_nav.dart`). VPN is always on the bar;
rpAI appears when installed.

**Co-joined residual node roles (fleet honesty, not client PE):** residual hosts
may run **VPN + rpAI + Perccent** co-joined roles for operator/Helsinki oracle
collation — clients still contact monopin residual entry.

**Windows observe checklist**

1. After first-run, main bar shows **VPN**.  
2. With wallet/Evolve installed: **Wallet**, **Backup**, **Credit**, and when
   Evolve access is on: **Analysis**, **Voting**.  
3. With rpAI installed: **rpAI** tab.  
4. Settings self-update / CHECK BREADCRUMBS remains opt-in for push updates.  
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

Windows package path should embed entry + DE/exit pubs via the existing Windows
installer secrets inject (same honesty as Apple `inject_apple_secrets`: live
IS+DE+exit only).

Multihop (when enabled): residual-via-exit; not full intermediate onion.

---

## 5. On the Windows build machine (ordered)

1. Sync monorepo to the ship commit; confirm `client/VERSION` reads **`1.0.8`**.  
2. Optional large-drive mirror:  
   `set RPT_WINDOWS_DRIVE=…` then  
   `python scripts/windows_brand_mirror.py apply`  
3. Build native PE with the existing Windows freeze/package path (MSVC / Inno /
   brand assets — see prior multihop handoffs if using `build_windows_multihop`).  
4. Output **must** be named:  
   `restore-privacy-client-1.0.8-windows-x64-setup.exe`  
5. Authenticode-sign the PE.  
6. Stage: copy to `status_page/assets/1.0.8/` and `releases/1.0.8/`.  
7. Helsinki upload: paid_assets monopin path (admin UPLOADS or  
   `scripts/host_paid_assets_vps.py` — selective Windows file is fine).  
8. Refresh breadcrumbs vault:  
   `python3 scripts/breadcrumbs_vault.py stage --version 1.0.8`  
   then `publish` when SSH vault path is available.  
9. Re-check: host PE size/sha matches Helsinki before admin **client-push** of
   Windows package (host vs Helsinki match gate).

### Smoke after PE install (architecture observation)

- First-run order: account → seed → licence → shell (no VPN permission first).  
- Trial: 72h KEYGEN-free residual; then KEYGEN /pay.  
- Suite bar: VPN, %, Evolve surfaces (Analysis/Voting when installed), Backup,
  Credit, rpAI when installed.  
- Residual catalog: IS + DE only; no US peer in Settings as live entry.  
- Stripe: no Checkout trial days.

---

## 6. Operator notes (Stripe + fulfilment)

- Code: `CATALOG_TRIAL_PERIOD_DAYS = 0`; Checkout omits subscription trial days.  
- Residual free trial remains host **device_trial** only (in-app).  
- Paid installers live under Helsinki `paid_assets/1.0.8/` (not public GitHub).  
- Admin UPLOADS (status host): Suite-only monopin inventory; client-push only when
  selected package **sizes match** build host and Helsinki.

---

## 7. Related monorepo truth (read-only pointers)

| Topic | Location |
|-------|----------|
| First-run gate | `client_app/lib/first_run_gate.dart`, `first_run_portal.dart` |
| Suite nav / parts | `client_app/lib/suite_nav.dart`, `suite_parts.dart` |
| Trial / Stripe | `status_page/payments.py` (`RESIDUAL_TRIAL_HOURS`, `CATALOG_TRIAL_PERIOD_DAYS`) |
| Residual peers | `client/multihop.py` (IS+DE live; US/RO retired) |
| Apple inject (parity) | `scripts/inject_apple_secrets.py` — Windows PE should match live-pub set |
| Breadcrumbs vault | `scripts/breadcrumbs_vault.py` stages this file as `WINDOWS_HANDOFF.md` |

---

## Companions (optional same monopin)

- `restore-privacy-rx-browser-1.0.8-windows.zip` if Rx browser ships with this monopin.  
- Brand-wide slots (rpOS, Pens, …) are **not** required for Suite residual observe;
  Suite client PE is the primary residual + shell artifact.

## Honest status

- Catalog can serve monopin **1.0.8** with a re-pinned carry-forward PE until
  this machine seals a native Authenticode build.  
- Architecture (first-run, trial, Suite parts, IS+DE) is product truth regardless
  of PE carry-forward — validate UI/behaviour on a current client build when
  the PE is still carry-forward.
