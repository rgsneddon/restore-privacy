# Restore Privacy — Code & Policy Audit

| Field | Value |
|-------|--------|
| **Product** | Restore Privacy Tunnel (RPT) |
| **Repository** | `restore_privacy` (root of this tree) |
| **Version under review** | **0.1.8** (`client/VERSION`, `status_page/downloads.py` `RELEASE_VERSION` / `RELEASE_TAG`) |
| **Audit date** | 19 July 2026 (**refresh pass** after follow-up commit `34f138e`) |
| **Prior pass** | Same date, first-pass `audit.md` + follow-ups in §10 |
| **Audit type** | Static code + policy consistency review (not a penetration test or live multi-OS residual-IP red-team) |
| **Auditor method** | Tree inspection, spot-checks of closed follow-ups, unit/structural security/policy test suite |

---

## 1. Executive summary

Restore Privacy is a custom encrypted tunnel stack (node, multi-platform clients, public status page) with a clear product thesis: **no user-info logs**, **minimal public status surface**, and **honest “Connected”** only when residual public IP can change via full-tunnel routes.

**Overall posture (refresh):** Still **strong** alignment between privacy claims and shipped helpers for residual honesty, session-only public metrics, device-key bootstrap (no shared client private key in packages), packaging gates that strip `*.priv` / forbid `node_elgamal.priv`, and Linux bake-in wheels. **Prior Medium doc findings M1 and M2 are re-verified closed** on the current tree (PRIVACY_POLICY §3.2 includes Linux; README contains `do **not** ship a shared`). Prior Low L3 (socket close) and L5 (Linux Mint catalog wording) are also closed.

**Primary residual risks (still open, by design or environment):**

1. **Operational** — operator misconfiguration; VPS/CDN host logging outside product no-log (privacy §4).
2. **Apple** — residual IP requires signed Packet Tunnel / NE; prep zips remain Mac-side work (M3).
3. **Linux privilege floor** — residual needs root + host TUN/`ip` (M4).
4. **UK gate** — egress IP visible to third-party geo endpoints (M5).

**Supporting automated run (this refresh):** representative security/policy modules — **97 passed, 0 failed** (see §6). No documentation-string failure remains for the shared-key / §3.2 checks.

---

## 2. Scope and method

### 2.1 In scope

| Area | Paths / artifacts |
|------|-------------------|
| Shared client | `client/connect.py`, `dataplane.py`, `full_tunnel.py`, `secrets_loader.py`, `uk_gate.py`, `ui_theme.py` |
| Windows | `client/windows/*` (GUI, tray, Wintun tunnel, installer) |
| Linux | `client/linux/*`, `scripts/package_linux.py`, install scripts, `scripts/RELEASE.md` |
| Mobile / Apple | `client_app/` (Flutter, Android, iOS/macOS RPT2, honesty helpers) |
| Node | `node/*` (handshake, sessions, nolog, server, UI) |
| Public web | `status_page/*` (status normalize, downloads catalog) |
| Packaging | `scripts/build_release_0.1.8.py`, `scripts/package_linux.py`, local `releases/` (gitignored) |
| Policies / legal | `PRIVACY_POLICY.md`, `LICENSE`, `CREDITS.md`, `README.md`, `sundries.txt` |
| Tests | Subset in §6; structural `tests/test_audit_md.py`, `tests/test_audit_followups.py` |

### 2.2 Out of scope / not deeply audited

- Line-by-line review of every file under `dist/`, `client_app/build/`, or frozen binaries.
- Live residual public-IP change on production node from this host.
- Mac notarization / App Store / Snap / Flathub review.
- Full cryptographic review of ElGamal/Pedersen parameters (implementation present; formal crypto audit not performed).
- Other monorepo apps outside `restore_privacy`.

### 2.3 Method notes (this pass)

- Re-read version surfaces: `client/VERSION` == catalog `0.1.8`.
- Spot-checked M1/M2 closed language in PRIVACY_POLICY and README.
- Spot-checked release gates (`_assert_no_priv`, package `*.priv` refuse, `.gitignore secrets/`), Linux ABI docs, Apple “Mac work required”, connect socket close path.
- Re-ran unit/structural tests for residual IP, secrets packaging, legal docs, downloads, Linux package, tunnel teardown, live client count, Apple honesty, audit structural tests.
- **Did not** paste any secret key material into this document (local `secrets/` is gitignored; only path patterns cited).

---

## 3. Architecture snapshot (observed)

```
[Clients: Windows | Android | Linux | iOS/macOS]
        |  RPT2 handshake + sealed DATA
        v
[Node: admission + in-memory sessions + NAT/forward]
        |
        v  (optional) status API: title + clients_connected only
[Status page on Render]  <-- public downloads catalog v0.1.8
```

- **Windows product Connect:** requires admin + Wintun + dual `/1` for residual success (`require_system_capture=True` in `client/windows/app.py` / `tunnel_win.py`).
- **Linux product Connect:** requires root + TUN + dual `/1` (`client/linux/tunnel_linux.py`); installer package bakes manylinux `cryptography` wheels (`scripts/package_linux.py`); offline `install.sh` + `bin/privacy-restored`.
- **Apple product Connect:** Packet Tunnel NE path required for residual; host-side HELLO alone is diagnostic (tests in `test_apple_full_tunnel_honesty.py`); README states prep zips need **Mac work**.
- **Public status:** `status_page/app.py` `normalize_status` / `public_status_payload` keep **title + clients_connected** only.
- **Catalog Linux button:** `Linux - Installer (.tar.gz)` → `restore-privacy-client-0.1.8-linux-x64.tar.gz`.

---

## 4. Findings

Severity scale: **High** (likely security/privacy break or secret exposure) · **Medium** (material policy/code gap or user-facing honesty risk) · **Low** (maintainability / minor drift) · **Info** (strength or environmental limit).

### 4.1 High

| ID | Finding | Evidence | Implication / follow-up |
|----|---------|----------|-------------------------|
| — | **No High finding of intentional public private-key shipping or user-info logging pipeline in product defaults.** | Packaging strips `*.priv`; inject/build scripts forbid `node_elgamal.priv`; `node/nolog.py` policy; status API field allow-list. Tests: `test_device_admission_keys`, package gates, live client count. | Continue release gates; never commit `secrets/`. |

> **Note:** A local operator checkout may still contain `secrets/*.priv` on disk (gitignored). That is expected for node ops; **High** would apply if those were published in GitHub Releases or public zips (not observed in packaging recipes).

### 4.2 Medium — open (by design / environment)

| ID | Finding | Evidence | Implication / follow-up |
|----|---------|----------|-------------------------|
| M3 | **Apple residual protection depends on Network Extension signing** not present in prep zips alone. | README Apple section: “Mac work required”; residual only when Packet Tunnel signed/active; honesty tests require NE path. | Keep residual UI honest until NE is signed; prep zips remain Mac-side work. |
| M4 | **Linux residual path depends on root + host TUN/`ip`**; app crypto is baked, OS floor is not. | `product_connect_requires_root()`, package LINUX_INSTALL docs; honest by design. | Do not market as zero-privilege residual VPN. |
| M5 | **UK gate / geo check** contacts third-party public IP services (egress metadata). | `client/uk_gate.py` (User-Agent `restore-privacy-client/0.1.8`). | Disclose in privacy limits if users need more detail; minimize endpoints; no PII beyond egress IP as seen by those services. |

### 4.3 Medium — closed on this refresh (were open on first pass)

| ID | Status | Re-verification evidence |
|----|--------|--------------------------|
| **M1** | **Closed** | `PRIVACY_POLICY.md` §3.2 heading: “Windows, Android, **Linux**, iOS, and macOS”. Tests: `test_audit_followups.TestDocsM1M2`. |
| **M2** | **Closed** | `README.md` contains `do **not** ship a shared` (device-key packaging sentence). Tests: `test_device_admission_keys.TestDocsNoSharedPriv`, `test_audit_followups`. |

### 4.4 Low

| ID | Finding | Status / evidence |
|----|---------|-------------------|
| L1 | **Many historical `scripts/build_release_0.*.py` copies** increase maintenance surface. | **Open (accepted).** Mitigated by `scripts/RELEASE.md` (use current-tag script only). Full consolidation deferred. |
| L2 | **Workspace `dist/` and Flutter `build/` trees** are large local artifacts. | **Open (ops hygiene).** `.gitignore` ignores `dist/`, `releases/`, `client_app/build/`. |
| L3 | **Test ResourceWarnings** (unclosed sockets) in connect tests. | **Closed on refresh.** `RptClient.connect` closes UDP sock on failed handshake; secrets tests call `disconnect()`. |
| L4 | **Linux manylinux wheel matrix** covers CPython 3.8–3.12 but not every distro forever. | **Open (process).** Docs require re-run `package_linux.py` each release; ABI section in package LINUX_INSTALL generator. |
| L5 | **README status-page bullet said “Linux Mint” vs catalog Linux installer.** | **Closed.** README now: “Windows, Android, macOS, iOS, and **Linux** (catalog v0.1.8)”. |

### 4.5 Info / strengths

| ID | Observation | Evidence |
|----|-------------|----------|
| I1 | **Residual honesty** enforced on product Connect (Windows/Linux system capture + routes; Apple NE). | `residual_ip_capture_active`, `require_system_capture=True`, Apple honesty tests. |
| I2 | **Anti-blackhole routing** (dual `/1` on-link, server pin first). | `client/full_tunnel.py`, Windows/Linux builders + tests. |
| I3 | **No shared client private key in packages**; device key generate/rotate. | `secrets_loader.py`, installer strip, inject_apple, denylist tests. |
| I4 | **Public status data minimization** (live count only). | `node/sessions.py`, `status_page/app.py`, live client count tests. |
| I5 | **No-log policy** codified for node config/systemd. | `node/nolog.py`. |
| I6 | **Windows product path** does not require system Python for end users. | Frozen setup + `test_no_python_user_path`. |
| I7 | **Linux installer package** bakes cryptography wheels; offline install. | `package_linux.py`, release linux tar.gz (~14 MB), package tests. |
| I8 | **Version surfaces aligned** at 0.1.8 (VERSION, catalog, privacy, README). | Spot-check this pass. |
| I9 | **MIT + third-party credits** present. | `LICENSE`, `CREDITS.md`. |
| I10 | **Operator secrets discipline** documented (README, sundries, RELEASE.md). | Post-follow-up docs. |

---

## 5. Policy consistency matrix

| Privacy / product claim | Code / packaging behaviour | Verdict (refresh) |
|-------------------------|----------------------------|-------------------|
| No user-info / connection logs by design | `node/nolog.py`; no product telemetry upload path in client UI reviewed | **Aligned** (operator can still misconfigure host) |
| Public page: only current connected count | `public_status_payload` / `normalize_status`; tests reject lifetime metrics | **Aligned** |
| No shared `client_ed25519.priv` in packages | Strip/inject/generate device key; packaging ignores `*.priv`; README exact phrase | **Aligned** |
| Never ship node private key | Forbidden in inject/package scripts; gitignore `secrets/` | **Aligned** |
| Residual IP only with full tunnel | Product Connect gates; status strings distinguish ISP vs VPN | **Aligned** |
| Close UI does not disconnect (Windows/Android stay-alive) | `_on_close_ui_only`; Android dispose tests | **Aligned** |
| Disconnect fully tears down | `stop_full_tunnel` Windows/Linux; Android disconnect channel | **Aligned** |
| Catalog v0.1.8 platforms incl. Linux installer | Five platforms; label `Linux - Installer (.tar.gz)` | **Aligned** |
| Linux clients covered in privacy narrative | §3.2 heading **and** package bullet include Linux | **Aligned** (M1 closed) |
| Windows no separate Python | Frozen setup recipe + README | **Aligned** |
| Linux crypto deps offline on install | Baked wheels + `--no-index` in `install.sh` | **Aligned** (system python3-tk/venv still required) |
| Hosting/CDN logs outside product no-log | Privacy §4; README/sundries operator reminder | **Aligned** |

---

## 6. Automated checks run during this refresh

**Command family:** `python -m unittest` on audit structural, audit follow-ups, residual, secrets packaging, legal, downloads, Linux package, teardown, live count, Apple honesty modules.

| Result | Detail |
|--------|--------|
| **Passed** | **97** |
| **Failed** | **0** |
| **Log** | `{SCRATCH}/audit_refresh_supporting_tests.log` |

Interpretation: prior doc-string failure on README shared-key phrase is **gone**. Packaging and residual honesty tests remain green.

---

## 7. Secrets & packaging controls (checklist)

| Control | Status (refresh) |
|---------|------------------|
| `secrets/` gitignored | Yes (`.gitignore`) |
| Installer strips / ignores `*.priv` | Yes (`installer.py`, `package_linux.py`) |
| Apple inject: node pub only | Yes (`inject_apple_secrets.py`) |
| Release recipes assert no node priv | Yes (`_assert_no_priv` in `build_release_0.1.8.py`; package_linux refuses `*.priv`) |
| Shared client key denylist/rotation | Yes (`secrets_loader.py` + tests) |
| Operator “never force-add secrets/” | Yes (README, `sundries.txt`, `scripts/RELEASE.md`) |
| This audit embeds no key material | Confirmed |

---

## 8. Recommendations (non-binding; residual after this pass)

1. **Keep** residual UI honest on Apple until NE is signed; do not market prep zips as residual-ready.
2. **Re-run** `package_linux.py` on every tag so manylinux **CPython 3.8–3.12** wheels stay current.
3. **Optional:** Parameterize a single release script over time (historical `build_release_0.*.py` remain archive; `RELEASE.md` is the process note).
4. **Optional:** Further minimize or document UK-gate third-party endpoints (M5).
5. **Ops:** Continue reminding operators that VPS/CDN logs are outside product no-log (privacy §4).

---

## 9. Conclusion

As of **0.1.8 refresh**, the codebase and privacy policy remain **consistent** on core promises: no-log defaults, minimal public metrics, residual-honest Connect, and no shared client private keys in public packages. **Documentation inconsistencies M1/M2 from the first pass are closed and re-verified.** Remaining Medium items (Apple NE, Linux root floor, UK gate, host logging) are primarily **privilege / environment / operational** limits, not silent product dishonesty.

This document is a **static audit record**. Re-run after major releases or crypto/packaging changes.

---

## 10. Follow-ups from first pass (status)

| Rec | Status |
|-----|--------|
| M1 privacy §3.2 includes Linux | **Closed** (re-verified this pass) |
| M2 README `do **not** ship a shared` | **Closed** (re-verified this pass) |
| Release `_assert_no_priv` / never force-add `secrets/` | **In place** + documented (RELEASE.md, sundries, README) |
| Linux wheeled ABIs + re-run `package_linux.py` | **Documented** in package LINUX_INSTALL generator + README |
| Apple residual honesty + Mac work required | **In place** (README + honesty tests green) |
| Ops VPS/CDN outside no-log | **In place** (privacy §4; operator docs) |
| Optional release-script consolidation | **Partial** (`scripts/RELEASE.md`; historical scripts retained) |
| Optional connect socket close | **Closed** (`RptClient.connect` + secrets tests) |

---

## 11. Document control

| Item | |
|------|--|
| Output path | `audit.md` (repository root) |
| Related policy | `PRIVACY_POLICY.md` |
| Related legal | `LICENSE`, `CREDITS.md` |
| Related user docs | `README.md`, `scripts/RELEASE.md`, `sundries.txt` |
| Refresh commit target | Current `main` after follow-ups (`34f138e`+) |
