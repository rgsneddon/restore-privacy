# Restore Privacy — Code & Policy Audit

| Field | Value |
|-------|--------|
| **Product** | Restore Privacy Tunnel (RPT) |
| **Repository** | `restore_privacy` (root of this tree) |
| **Version under review** | **0.1.8** (`client/VERSION`, `status_page/downloads.py` `RELEASE_VERSION` / `RELEASE_TAG`) |
| **Audit date** | 19 July 2026 |
| **Audit type** | Static code + policy consistency review (not a penetration test or live multi-OS residual-IP red-team) |
| **Auditor method** | Tree inspection, targeted greps, unit/structural test suite for security/privacy themes |

---

## 1. Executive summary

Restore Privacy is a custom encrypted tunnel stack (node, multi-platform clients, public status page) with a clear product thesis: **no user-info logs**, **minimal public status surface**, and **honest “Connected”** only when residual public IP can change via full-tunnel routes.

**Overall posture:** Strong alignment between privacy claims and shipped helpers for residual honesty, session-only public metrics, device-key bootstrap (no shared client private key in packages), and packaging gates that strip `*.priv` / forbid `node_elgamal.priv` in public trees. Automated tests largely support these claims.

**Primary residual risks** are operational (operator misconfiguration, host/VPS logging, Apple NE signing gaps) and documentation drift (privacy §3.2 platform list / README phrasing vs tests), not an obvious intentional logging or telemetry pipeline in the product path.

**Supporting automated run (this audit):** security/policy-related unittest modules — **140 passed, 1 failed** (see §6). Failure is a **documentation string** expectation on `README.md`, not a runtime secret-shipping failure.

---

## 2. Scope and method

### 2.1 In scope

| Area | Paths / artifacts |
|------|-------------------|
| Shared client | `client/connect.py`, `dataplane.py`, `full_tunnel.py`, `secrets_loader.py`, `uk_gate.py`, `ui_theme.py` |
| Windows | `client/windows/*` (GUI, tray, Wintun tunnel, installer) |
| Linux | `client/linux/*`, `scripts/package_linux.py`, install scripts |
| Mobile / Apple | `client_app/` (Flutter, Android, iOS/macOS RPT2, honesty helpers) |
| Node | `node/*` (handshake, sessions, nolog, server, UI) |
| Public web | `status_page/*` (status normalize, downloads catalog) |
| Packaging | `scripts/build_release_*.py`, `scripts/package_linux.py`, `releases/` (local stage, gitignored) |
| Policies / legal | `PRIVACY_POLICY.md`, `LICENSE`, `CREDITS.md`, `README.md` |
| Tests | `tests/` (subset listed in §6) |

### 2.2 Out of scope / not deeply audited

- Line-by-line review of every file under `dist/`, `client_app/build/`, or frozen binaries.
- Live residual public-IP change on production node from this host.
- Mac notarization / App Store / Snap / Flathub review.
- Full cryptographic review of ElGamal/Pedersen parameters (implementation present; formal crypto audit not performed).
- Other monorepo apps outside `restore_privacy`.

### 2.3 Method notes

- Read policy and version surfaces against code.
- Grepped for private-key handling, log sinks, status payload fields.
- Ran existing unit/structural tests for residual IP, secrets, legal docs, downloads, Linux package, tunnel teardown, live client count, Apple honesty.
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
- **Linux product Connect:** requires root + TUN + dual `/1` (`client/linux/tunnel_linux.py`); installer package bakes manylinux `cryptography` wheels (`scripts/package_linux.py`).
- **Apple product Connect:** Packet Tunnel NE path required for residual; host-side HELLO alone is diagnostic (tests in `test_apple_full_tunnel_honesty.py`).
- **Public status:** `status_page/app.py` `normalize_status` / `public_status_payload` keep **title + clients_connected** only.

---

## 4. Findings

Severity scale: **High** (likely security/privacy break or secret exposure) · **Medium** (material policy/code gap or user-facing honesty risk) · **Low** (maintainability / minor drift) · **Info** (strength or environmental limit).

### 4.1 High

| ID | Finding | Evidence | Implication / follow-up |
|----|---------|----------|-------------------------|
| — | **No High finding of intentional public private-key shipping or user-info logging pipeline in product defaults.** | Packaging strips `*.priv`; inject/build scripts forbid `node_elgamal.priv`; `node/nolog.py` policy; status API field allow-list. Tests: `test_device_admission_keys`, `test_apple_signing_pipeline`, `test_live_client_count`. | Continue release gates; never commit `secrets/`. |

> **Note:** A local operator checkout may still contain `secrets/*.priv` on disk (gitignored). That is expected for node ops; **High** would apply if those were published in GitHub Releases or public zips (not observed in packaging recipes).

### 4.2 Medium

| ID | Finding | Evidence | Implication / follow-up |
|----|---------|----------|-------------------------|
| M1 | **Privacy policy §3.2 client header omits Linux** while packages and packaging text include Linux. | `PRIVACY_POLICY.md` §3.2 title: “Windows, Android, iOS, and macOS”; §3.2 package bullet includes Linux `.tar.gz` installer. | Update §3.2 heading/list to include **Linux** for consistency. |
| M2 | **README does not use the exact shared-key non-shipping phrase expected by tests** (doc test failed). | `tests/test_device_admission_keys.py::test_privacy_and_readme_describe_device_keys` asserts `do **not** ship a shared` in README; Apple subsection says “Never ship … shared `client_ed25519.priv`” but not that exact markdown phrase. Privacy policy **does** state packages do not ship shared client priv. | Align README wording with privacy policy (or relax test to accept existing Apple/README language). |
| M3 | **Apple residual protection depends on Network Extension signing** not present in prep zips alone. | Policy and `APPLE_*` docs; honesty tests require NE path. Prep zips staged without live notarization on Windows build host. | User-facing downloads already note Mac-side signing; keep residual claims gated on NE `.connected`. |
| M4 | **Linux residual path depends on root + host TUN/`ip`**; app crypto is baked, OS floor is not. | `product_connect_requires_root()`, `LINUX_INSTALL.md` / package docs; honest by design. | Ensure users understand elevation; do not market as zero-privilege residual VPN. |
| M5 | **UK gate / geo check** contacts third-party public IP services (egress metadata). | `client/uk_gate.py` (User-Agent `restore-privacy-client/0.1.8`). | Disclose in privacy “limits” if not already clear; minimize endpoints; no PII beyond egress IP as seen by those services. |

### 4.3 Low

| ID | Finding | Evidence | Implication / follow-up |
|----|---------|----------|-------------------------|
| L1 | **Many historical `scripts/build_release_0.*.py` copies** increase maintenance surface. | `scripts/build_release_0.0.1.py` … `0.1.8.py`. | Prefer single parameterized release script for future tags. |
| L2 | **Workspace `dist/` and Flutter `build/` trees** are large local artifacts (gitignored for dist/releases/build patterns). | `.gitignore` ignores `dist/`, `releases/`, `client_app/build/`. | Ensure CI/clean machines do not accidentally publish full trees. |
| L3 | **Test ResourceWarnings** (unclosed sockets) in connect tests. | `test_windows_secrets` ResourceWarning during suite. | Close sockets in test teardown; non-product issue. |
| L4 | **Linux manylinux wheel matrix** covers multiple CPython tags but not every distro ABI forever. | `scripts/package_linux.py` downloads for 3.8–3.12 manylinux. | Re-run `package_linux.py` when cryptography releases break older wheels. |
| L5 | **Status page subtitle still says “Linux Mint” in one README status-page bullet** while catalog says Ubuntu/Linux installer. | README “Download buttons … Linux Mint (catalog v0.1.8)”. | Minor wording cleanup for catalog alignment. |

### 4.4 Info / strengths

| ID | Observation | Evidence |
|----|-------------|----------|
| I1 | **Residual honesty** is enforced in product Connect paths (Windows/Linux require system capture + routes; Apple NE). | `residual_ip_capture_active`, `require_system_capture=True`, Apple honesty tests. |
| I2 | **Anti-blackhole routing** (dual `/1` on-link, server pin first; no ARP gateway `10.88.0.1` for catch-alls). | `client/full_tunnel.py`, Windows/Linux route builders + tests. |
| I3 | **No shared client private key in packages**; device key generate/rotate on first run. | `secrets_loader.py`, installer strip, inject_apple_secrets, denylist tests. |
| I4 | **Public status data minimization** (live count only; not lifetime total). | `node/sessions.py`, `status_page/app.py`, live client count tests. |
| I5 | **No-log policy** codified for node config/systemd. | `node/nolog.py`. |
| I6 | **Windows product path** does not require system Python for end users (frozen setup). | Installer + `test_no_python_user_path`. |
| I7 | **Linux installer package** bakes cryptography wheels; offline `install.sh` + private venv. | `package_linux.py`, release `0.1.8` linux tar.gz (~14 MB), package tests. |
| I8 | **Version surfaces aligned** for 0.1.8 across VERSION, catalog, privacy, README (at audit time). | Spot-check: `RELEASE_VERSION == client/VERSION == 0.1.8`. |
| I9 | **MIT + third-party credits** present. | `LICENSE`, `CREDITS.md`. |

---

## 5. Policy consistency matrix

| Privacy / product claim | Code / packaging behaviour | Verdict |
|-------------------------|----------------------------|---------|
| No user-info / connection logs by design | `node/nolog.py`; no product telemetry upload path found in client UI code reviewed | **Aligned** (operator can still misconfigure host) |
| Public page: only current connected count | `public_status_payload` / `normalize_status`; tests reject lifetime metrics | **Aligned** |
| No shared `client_ed25519.priv` in packages | Strip/inject/generate device key; packaging ignores `*.priv` | **Aligned** in code; **README phrase test gap** (M2) |
| Never ship `node_elgamal.pub` only for node? Wait: **never ship node private key** | Forbidden in inject/package scripts; gitignore `secrets/` | **Aligned** |
| Residual IP only with full tunnel | Product Connect gates; status strings distinguish ISP vs VPN | **Aligned** |
| Close UI does not disconnect (Windows/Android stay-alive) | `_on_close_ui_only`; Android dispose tests | **Aligned** |
| Disconnect fully tears down | `stop_full_tunnel` Windows/Linux; Android disconnect channel | **Aligned** |
| Catalog v0.1.8 platforms incl. Linux installer | `downloads.py` five platforms; Linux label “Linux - Installer (.tar.gz)” | **Aligned** |
| Linux clients covered in privacy narrative | §3.2 package bullet includes Linux; §3.2 **heading** omits Linux | **Partial** (M1) |
| Windows no separate Python | Frozen setup recipe + README | **Aligned** |
| Linux crypto deps not requiring network pip on install | Baked wheels + `--no-index` in `install.sh` | **Aligned** (system python3-tk/venv still required) |

---

## 6. Automated checks run during this audit

**Command family:** `python -m unittest` on residual, secrets, legal, downloads, Linux, teardown, live count, tray, nonadmin, Apple honesty modules.

| Result | Detail |
|--------|--------|
| **Passed** | 140 |
| **Failed** | 1 — `test_privacy_and_readme_describe_device_keys` (README missing exact `do **not** ship a shared` string) |
| **Log** | `{SCRATCH}/audit_supporting_tests.log` (implementer scratch for this goal run) |

Interpretation: failure is **documentation string match**, not a packaging regression (device-key packaging tests still passed).

---

## 7. Secrets & packaging controls (checklist)

| Control | Status |
|---------|--------|
| `secrets/` gitignored | Yes (`.gitignore`) |
| Installer strips / ignores `*.priv` | Yes (`installer.py`, `package_linux.py`) |
| Apple inject: node pub only | Yes (`inject_apple_secrets.py`) |
| Release recipes assert no node priv | Yes (Windows installer binary scan; package_linux refuses `*.priv`) |
| Shared client key denylist/rotation | Yes (`secrets_loader.py` + tests) |
| This audit embeds no key material | Confirmed |

---

## 8. Recommendations (non-binding)

1. **Docs:** Fix M1 (privacy §3.2 platforms) and M2 (README shared-key sentence) so legal/doc tests stay green and users see consistent claims.
2. **Release process:** Keep `_assert_no_priv` / inject gates on every tag; never force-add `secrets/`.
3. **Linux:** Document supported Python ABIs for wheeled `cffi` when publishing; re-run `package_linux.py` each release.
4. **Apple:** Keep residual UI honest until NE is signed; prep zips remain “Mac work required.”
5. **Ops:** Remind operators that VPS/CDN logs are outside product no-log (already in privacy §4).
6. **Optional:** Consolidate build_release scripts; close sockets in connect tests.

---

## 9. Conclusion

As of **0.1.8**, the codebase and privacy policy are **largely consistent** on the core promises: no-log defaults, minimal public metrics, residual-honest Connect, and no shared client private keys in public packages. The highest-priority cleanups from this audit are **documentation consistency** (Linux in privacy §3.2; README phrase vs tests) and continued discipline around **operator secrets and Apple/Linux privilege floors**.

This document is a **static audit record** for the repository tree reviewed on the date above. It should be re-run after major releases or crypto/packaging changes.

---

## 10. Document control

| Item | |
|------|--|
| Output path | `audit.md` (repository root) |
| Related policy | `PRIVACY_POLICY.md` |
| Related legal | `LICENSE`, `CREDITS.md` |
| Related user docs | `README.md` |
