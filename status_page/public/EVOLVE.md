> **On this site:** Evolve documentation mirrored from the public [Evolve README](https://github.com/rgsneddon/evolve/blob/main/README.md). That GitHub file remains the source of truth.

# Evolve — Social Science Chronoflux Framework

**Web** · **Releases** (see this repository’s GitHub Pages site and Releases tab)

BITCOIN TALK [ANN] https://bitcointalk.org/index.php?topic=5587544.msg66906190#msg66906190

Evolve is a cross-platform app for analysing social and political scenarios using the **Chronoflux** hydrodynamic framework.

All core Chronoflux calculations run **locally** on your device. Optional **Grok construal** can fill blank σ / Iτ / Jμ / ω fields before each Calculate — behaviour depends on platform (see [Grok construal](#2-grok-construal-optional)).

The **Chronoflux Principia**, realised by **Roy D Herbert**, is the core mechanical foundation of the Evolve analysis engine (see [License](#license)).

---

## Quick start

**Latest release:** v4.1.8 (build 174) — [Downloads](https://rgsneddon.github.io/evolve/downloads/) · [Web app](https://rgsneddon.github.io/evolve/) · [Releases](https://github.com/rgsneddon/evolve/releases)

### Windows (easiest)

Download **evolve-v4.1.8-windows-x64-setup.exe** from [Downloads](https://rgsneddon.github.io/evolve/downloads/) or the **Releases** tab. Verify the attached `.sha256` checksum, then run the installer. A portable zip is also on each release.

### Web

Live app: [https://rgsneddon.github.io/evolve/](https://rgsneddon.github.io/evolve/) (GitHub Pages, base path `/evolve/`).

### Android

Download **evolve-v4.1.8-android-setup.apk** from [Downloads](https://rgsneddon.github.io/evolve/downloads/) or **Releases** (the APK file itself is on GitHub Releases). Requires **Android 7.0+ (API 24)**. Verify SHA-256 before installing. If install fails after an older debug build, uninstall Evolve first, then reinstall. Enable “Install unknown apps” for the browser or Files app you use to open the APK. The in-app updater checks GitHub Releases first when a newer build is published.

### iOS and macOS (build on a Mac)

Apple binaries require Xcode. The repo includes a full **`ios/`** and **`macos/`** Flutter host (bundle ID `com.evolve.chronoflux`). For the late Mac session — tools, signing, IPA/macOS commands, and handoff into the Windows release pipeline — see **[docs/MAC_BUILDS.md](docs/MAC_BUILDS.md)**. Signing notes: [ios/SIGNING.md](ios/SIGNING.md), [macos/SIGNING.md](macos/SIGNING.md).

---

## How to use Evolve

### 1. Select region and language

At the top of the app:

1. **Region** — choose the country or area you want to analyse. This scopes all observations, base rates, and construct language to that region (not Global unless you pick Global).
2. **Language** — choose the output language (English, Español, Français, Deutsch, and others).

The amber bar reminds you to select the region before you pose your question.

### 2. Grok construal (optional)

Below region and language is a second amber bar: **GROK CONSTRUE**.

| Setting | What happens |
|--------|----------------|
| **Don't use** | Fully offline. Local Chronoflux only. No X account needed. |
| **Use** | Grok construal fills **blank** σ / Iτ / Jμ / ω fields before each Calculate. Fields you already typed are never overwritten. |

Grok construal works differently on each platform:

| Platform | **Use** connects as | How blank fields are filled |
|----------|---------------------|-----------------------------|
| **Windows / Android** | `@your_username` (X OAuth) or `@evolve_mock` (dev) | Built-in Grok proxy; live Grok when **X Premium** and credentials are configured |
| **Web** | `@evolve_web` | **Web heuristic mode** — region-aware suggestions in the browser (no X sign-in, no local proxy) |

**Desktop / Android:** slide to **Use** — the embedded proxy starts automatically; sign in with X when prompted. No manual scripts.

**Web (including GitHub Pages):** slide to **Use** — connects immediately as `@evolve_web` in heuristic mode. No proxy setup, no X sign-in, and no “Grok proxy not found” message. Chronoflux still runs locally. For **live** X Premium Grok on the web, host a remote Grok proxy and rebuild with:

```powershell
flutter build web --release --base-href /evolve/ --dart-define=GROK_PROXY_URL=https://your-proxy.example.com
```

When connected, the bar shows e.g. `Connected @your_username` (desktop) or `Connected @evolve_web` (web heuristic).

### 3. Choose analysis mode

| Mode | Best for |
|------|----------|
| **Percent Chance** | “What is the chance of…?” — probability-style Chronoflux output |
| **Social Cohesion Score** | Narratives, disputes, cohesion trajectories — full SCS report |

### 4. Enter your scenario

**Required:** **POSE YOUR QUESTION HERE** — your base scenario question (ω). Example:

> What is the chance of sporadic civil unrest near-term?

**Optional construct fields** (leave blank for observational inference, or fill to bias the analysis):

| Field | Symbol | Role |
|-------|--------|------|
| Vortex | ω | Circulation / focal tension around the question |
| Shear | σ | Directional bias, polarisation, narrative shear |
| Resistance | Iτ | Institutional or social resistance |
| Flow | Jμ | Trust transport, cohesion flow |

**Social Cohesion mode only:**

- **Narrative link** — paste a URL (news article, X post, YouTube, Bluesky, Reddit, Mastodon, etc.) and fetch text into the scenario via the Grok proxy.
- If the narrative relies on **attributed party responses**, Evolve scores each quote individually and blends them into the overall SCS.

### 5. Calculate

Tap **Calculate percent chance** or **Calculate social cohesion score**.

The pipeline runs:

1. **PART ONE** — core Chronoflux constructs and continuum
2. **PART TWO** — broader political continuum integration (refined SCS where applicable)
3. **PART THREE** — **five** recommended actions for the accountable establishment figurehead (mayor, minister, agency lead, etc.)

With **Grok construal on**, Grok suggestions are applied to empty fields first, then the same local pipeline runs.

### 6. Read and export results

**Percent Chance panel**

- Calibrated ~% headline with REGRESSIVE / PROGRESSIVE lean and continuum conclusion
- **How to read this conclusion** — explains the ~% headline, regressive/progressive momentum, σ and strain scores, registry filter (event class, region, horizon), and lists each historical `OR-xxxx` case used in the base rate

**Social Cohesion panel**

- Full PART ONE / TWO / THREE report
- Party-response refinement when a linked narrative relies on attributed quotes
- Calibrated headline % under `~XX/100` (not the raw THE CONTINUUM regressive/progressive split)
- Same **How to read this conclusion** explainer (refined SCS delta, continuum split, lever projections)

**PART THREE actions** (both modes)

- Five numbered actions with per-action rationales grounded in Chronoflux calculations
- Target SCS or PROGRESSIVE transport shift for the detected agent
- Copy all actions with the panel copy button

**Export complete synopsis** (below results)

| Button | Output |
|--------|--------|
| **PDF** | Download a formatted synopsis document |
| **Text (.md)** | Save a Markdown file (MarkdownBin-compatible) |
| **View in browser** | Open the full report in an in-app browser viewer |
| **Copy to clipboard** | Paste the complete synopsis anywhere |

The synopsis includes your posed question, region, mode, full analysis text, refined scores, and all five PART THREE actions.

### 7. License & attribution

Scroll to the bottom of the app and expand **License & Chronoflux attribution** for the Roy D Herbert / Chronoflux Principia notice and a link to the full [LICENSE](LICENSE) text.

---

## Standalone Perccent Wallet

The full Perccent wallet (without Evolve analysis or FCG voting) is available as a separate open-source project:

**[github.com/rgsneddon/perccent-wallet](https://github.com/rgsneddon/perccent-wallet)**

That repository includes the Flutter wallet app, a self-hosted `perc_chain` seed-node build (`render.yaml`), and deployment docs. It syncs on the same chain (`evolve-chronoflux-principia-chain-1`) as the embedded wallet in this app.

---

## Perccent blockchain — architecture, emission, and scalability

Evolve embeds an optional **Perccent** wallet (`PERC` / **Perccent**) on the **Chronoflux Principia** chain. The ledger lives on your device; an internet **seed node** (`evolve_seed_node`) anchors consensus and serves a public explorer. Currency uses **8 decimal places**: **1 cent = 0.00000001 PERC**.

### Chain layout

| Layer | ID / role |
|-------|-----------|
| **Evolutionary chain** | `evolve-chronoflux-principia-chain-1` — all app versions connect here |
| **Main chain** | `perc-main-evolve-1` — blocks, transfers, treasury, scenario rewards, microblock seals |
| **Side chain** | `perc-chronoflux-side-1` — fair-usage microblock height and pending seal progress |
| **Treasury** | `evolve_treasury` — emits PERC only when users run scenarios; no manual receive address or inbound funding after launch; outbound manual sends disabled |
| **Seed** | `evolve_seed_node` — rendezvous, ledger relay, public explorer |

**One internet seed node — not two.** Deploy a single Render service (`evolve-perc-internet` in `render.yaml`) hosting `evolve_seed_node`. The evolutionary id `evolve-chronoflux-principia-chain-1` is the canonical chain *name* (the `-1` suffix is not a second chain). There is no separate “chain 0” seed host. Every wallet adopts this seed’s chain id, block height, and tip hash at registration (or via background deep sync when the seed was temporarily offline) so cross-wallet Perccent send/receive stays on one ledger.

Each wallet keeps a **local JSON ledger**. When online, wallets gossip blocks and transfers through the rendezvous host (default port **9478**); wallet nodes may serve on port **9477**.

### How blocks are produced

Main-chain blocks advance on **scenario analysis**, **PERC transfers**, **treasury emission/regeneration**, and **microblock seal** events — not on Grok construal or raw field keystrokes alone.

```
Analysis Calculate  →  faucet payout + treasury emission block
PERC send/receive   →  transfer block (+ 1 cent fee burned)
Fair-usage typing   →  side-chain microblock (local log)
100M microblocks    →  main-chain Chronoflux seal block
```

**Confirmation model:** one main-chain confirmation fully settles PERC (Chronoflux Principia TIME). Staking rewards apply to balances confirmed after that same threshold.

**Typical block contents:**

- Treasury emission (accrual or regeneration toward the dynamic per-minute target)
- Scenario reward (faucet payout to the analysing wallet)
- Transfer and fee-burn transactions
- Optional microblock seal marker at 100M fair-usage microblocks

### Side chain, wards, and fair-usage microblocks

Fair-usage events — analysis form keystrokes and field edits — record **one microblock** each after blockchain launch. Each microblock carries a Chronoflux fingerprint and ward position.

| Unit | Size |
|------|------|
| **Microblocks per ward** | 10,000 log entries |
| **Wards per seal cycle** | 10,000 |
| **Microblocks per main seal** | 100,000,000 |

**Ward log pruning:** the fair-usage log holds at most **10,000 entries per ward**. When a ward fills, the log clears and the next ward starts empty — similar to clearing a cache and freeing wallet storage. At the end of a full 100M-microblock seal cycle, the log resets to ward 1 after the main-chain seal.

The in-app **block explorer** visualises ward bundles, seal-cycle progress, and the current ward log.

### Emission structure

Supply follows an **infinite Chronoflux continuum** (`infiniteContinuumSupply = true`). The legacy **283M PERC pool renewal** at 1-cent reserve applies only in finite-pool mode and is **disabled** in the current production setting.

#### Analysis faucet

After sign-in, each **Calculate** (percent chance or social cohesion) may draw from treasury:

- Payout: **xx/100 PERC**, where `xx` is the two-digit outcome (0–100)
- Cooldown: **once per 7 minutes per wallet**
- Maximum draw: **1.00 PERC** at 100/100

#### Treasury emission (dynamic)

Emission accrues between scenario events and funds faucet payouts. The rate is **dynamic** — it scales with **wallet load** and **average block time** on top of a faucet-aligned baseline.

**Baseline (1.0× combined factor):**

- Up to **1 PERC** accrues per **7-minute** cooldown window
- Static equivalent: **~0.14285714 PERC/min**

**Load factor** — scales with active wallets (√n curve):

```
loadFactor = √(wallet count)     (1 wallet → 1.0×, 4 → 2.0×, 25 → 5.0×)
```

Uses the greater of registered non-treasury wallets or currently online peers.

**Block-pace factor** — scales with how fast main-chain blocks arrive:

```
blockFactor = faucetCooldown ÷ averageBlockTime
```

Faster blocks than the 7-minute reference raise emission; slower blocks lower it (clamped 0.5×–5.0×).

**Combined emission:**

```
combinedFactor = loadFactor × blockFactor     (clamped 0.5× – 10×)
emissionPerCooldown = 1 PERC × combinedFactor
emissionPerMinute   = emissionPerCooldown × (60 ÷ 420)
```

**Example rates at 1.0× block pace:**

| Wallets | Load × | Max PERC / 7 min | Approx PERC / min |
|---------|--------|-------------------|-------------------|
| 1 | 1.0× | 1.00 | ~0.143 |
| 4 | 2.0× | 2.00 | ~0.286 |
| 16 | 4.0× | 4.00 | ~0.571 |
| 100+ (capped) | 10.0× | 10.00 | ~1.429 |

**Regeneration:** if treasury balance falls below **66%** of the current dynamic per-minute target, the next block tops it back up to that target.

**Launch mint:** the first scenario emission credits **1 PERC** to `evolve_treasury`.

**Treasury floor:** outbound debits (faucet, staking) never push treasury below **1 cent** (`0.00000001 PERC`). Staking pauses at the floor; emission accrual continues on the next scenario.

#### Staking and fees

- **Staking:** confirmed held PERC earns **0.00000005 PERC** per main-chain block (10% of the 50-cent scenario base reference)
- **Send fee:** **1 cent** burned on every outbound transfer (permanently removed from circulation)

### Scalability

The chain is designed to grow with user activity without unbounded local storage growth or a fixed treasury cap.

| Mechanism | Purpose |
|-----------|---------|
| **√wallet load scaling** | Emission rises with adoption but dampens runaway inflation (doubling users does not double emission) |
| **Block-pace scaling** | Busy chains accrue treasury faster; quiet chains accrue slower |
| **10× emission cap** | Hard ceiling on the combined dynamic multiplier |
| **Per-ward log pruning** | Fair-usage log never exceeds 10,000 entries per ward on device |
| **Seed ledger compaction** | Hosted seed drops `microblockLog` when compacting — anchor blocks and balances persist |
| **Peer mesh gossip** | Wallets sync taller chains and pending transfers without a central custodian |
| **Inbound credits** | Receiver balance updates after **one main-chain confirmation**; pending inbound transfers stay visible until confirmed; undelivered entries remain pending (no auto-revert window) |
| **Scenario block height** | Per-wallet progressive scenario counter (cap 100M) for explorer progress |
| **Seed anchor blocks** | Seed block height advances on cumulative treasury emission thresholds (100M PERC steps) |

**Privacy on public surfaces:** login usernames map to **five-character public aliases** on the explorer; wallet IPv4 endpoints show as **Private node**. Treasury credentials are never published — only emission statistics, block labels, and pseudonymous activity.

**Public explorer:** [evolve-perc-internet.onrender.com](https://evolve-perc-internet.onrender.com/) — block list, dynamic emission rate, load/block multipliers, peer status, and chain identifiers.

**Real-time Chronoflux stats:** [seed `/stats`](https://evolve-perc-internet.onrender.com/stats) (auto-refresh cards + recent blocks from `/health`, `/perc/status`, `/api/network`, `/api/blocks`) · mirror [stats.html](https://rgsneddon.github.io/evolve/stats.html) on GitHub Pages (CORS GETs to the public seed).

### Quick reference

| Topic | Value |
|-------|-------|
| Smallest unit | 1 cent = 0.00000001 PERC |
| Faucet cooldown | 7 minutes per wallet |
| Faucet payout | xx/100 PERC (max 1 PERC) |
| Baseline emission | 1 PERC / 7 min at 1.0× |
| Dynamic range | 0.5× – 10× combined |
| Treasury floor | 1 cent |
| Microblock seal | Every 100M fair-usage microblocks |
| Manual treasury sends | Disabled after launch |
| Manual treasury funding | Blocked — no receive address; PERC emitted on scenario only |

---

## Features

| Feature | What you get |
|---------|----------------|
| **Percent Chance** | Observational probability output for a posed question (ω) |
| **Social Cohesion Score** | Three-part cohesion report (PART ONE / TWO / THREE) with **five** establishment-facing agent actions |
| **Conclusion explainer** | Below each result: momentum, σ/continuum scores, registry filter, and bullet list of exact `OR-xxxx` cases used in calibration |
| **Synopsis export** | After Calculate: **PDF**, **Text (.md)**, **View in browser**, or **Copy to clipboard** — full MarkdownBin-style report including PART THREE actions |
| **Social narrative links** | Paste X, YouTube, Bluesky, Reddit, or Mastodon URLs in Social Cohesion mode — text fetched via Grok proxy for party-response scoring |
| **Web Grok heuristic** | GitHub Pages builds use `@evolve_web` in-browser construal — no local proxy, no X sign-in |
| **Android Grok** | Release APK includes `INTERNET` permission and loopback cleartext for the embedded proxy; Grok construal connects as `@evolve_mock` (or `@evolve_android` heuristic fallback) |
| **Static splash** | Launch uses a static poster (no MP4 splash animation) for faster cold start on all platforms |
| **Android splash banner** | Login splash shows the full EVOLVE wordmark proportionally on phone screens (contain fit, no side crop) |
| **Cross-version PERC** | Wallets on different app builds merge launch flags, pending inbound transfers, and transfer blocks from peers with shorter or divergent chains |
| **Registration seed (one-time)** | After a new account is created on the splash screen, an optional 12-word recovery seed is offered once (generate and write down, or skip) before entering the app |
| **PERC Security tab** | Immediately right of Wallet: export encrypted `.percbackup` files and restore from backup file only (no seed phrase setup) |
| **Switch commitments** | Epoch-tagged quantum-hardening commitments on login, pending transfers, and settlement witnesses |
| **In-app updates** | Windows and Android check published gh-pages `version.json` first, then GitHub Releases / gh-pages APK fallbacks |
| **Android wallet refresh** | Pull down on wallet screens to trigger an immediate inbound sync (`RefreshIndicator`) |
| **Hold-to-reveal password** | Press and hold the eye icon on login/register password fields to view your typed password |
| **Android biometric sign-in** | Optional fingerprint sign-in after you opt in post-login or after new registration seed setup; credentials stay on-device in OS secure storage — manual login always available |
| **Random PERC addresses** | Each independent wallet registration receives a randomly assigned PERC address — not derived from username or password |
| **Multi-device wallet sync** | Wallets restored from the same seed or backup file share the same address, balance, and transaction history across devices |
| **Send re-authentication** | Outbound PERC sends require password confirmation or Android biometric unlock when enrolled; **Percent Chance** and **Social Cohesion** analysis credits do not |

---

## The five constructs

Chronoflux uses five hydrodynamic constructs:

| Symbol | Name | Meaning (short) |
|--------|------|-----------------|
| ρt | Continuum | Baseline social–political continuum |
| Jμ | Flow | Trust and cohesion transport |
| σ | Shear | Bias layers, polarisation |
| Iτ | Resistance | Institutional / cultural resistance |
| ω | Vortex | Question-anchored circulation |

Weights are ascertained from your inputs (and Grok suggestions when enabled), then normalised before the hydrodynamic core runs.

---

## Grok / X configuration (production)

### Windows / Android (embedded proxy)

By default, without credentials, the desktop app uses **mock Premium** for development (connected as `@evolve_mock`). The embedded proxy starts automatically when you slide Grok construal to **Use**.

For live X OAuth and Grok construal, set environment variables before launching:

| Variable | Purpose |
|----------|---------|
| `X_CLIENT_ID` | X API OAuth client ID |
| `X_CLIENT_SECRET` | Optional OAuth secret |
| `XAI_API_KEY` | Live Grok construal via xAI (otherwise heuristic fallback) |

Optional standalone proxy (debug only):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_grok_proxy.ps1
```

### Web

| Mode | When | How |
|------|------|-----|
| **Heuristic** (default) | No `GROK_PROXY_URL` at build time | Slide **Use** → `@evolve_web`; blank fields filled in-browser before Calculate |
| **Live Grok** | `GROK_PROXY_URL` points to a hosted proxy with CORS | Same OAuth flow as desktop, via your remote proxy |

The web app cannot run a localhost proxy (browser security). Heuristic mode is the default on GitHub Pages deployments without `GROK_PROXY_URL`.

---

## Tips

- Expand **How to read this conclusion** under your result to see which registry cases (`OR-xxxx`) drove the calibrated outcome.
- Use **Export complete synopsis** → **PDF** or **Text (.md)** to archive or share a full run; **View in browser** for a quick readable layout.
- PART THREE lists **five** actions — read the grey rationale line under each for the ω/σ/Iτ/Jμ or continuum data behind it.
- Change **region** after entering a question only when you want that region to re-scope the scenario; the example question updates when the posed field is empty or still the old regional example.
- Switching **Percent Chance ↔ Social Cohesion** saves your current tab’s input and restores the other tab if you had posed a question there before.
- Leave bias fields blank to let the engine infer observational values relative to your ω question and selected region.
- **Don't use** Grok for reproducible, fully local analysis with no network dependency.
- On **web**, Grok heuristic mode (`@evolve_web`) needs no X account; use **Windows/Android** for live Premium Grok.
- Use a lowercase GitHub Pages path: `/evolve/` (not `/Evolve/`) when deploying under a user or org site.

---

## Security / Safe use

Release builds of Evolve are **checked regularly for safe use** before they are signed and published:

- **Malware scan** — Windows `.exe` and Android `.apk` installers under `build/downloads/v<version>/` are scanned with Windows Defender (when available) plus structural integrity checks (PE/APK headers, expected Android package id).
- **Dependency audit** — `flutter pub audit` and `npm audit --audit-level=high` in `perc_chain/` run before each release; any remaining critical/high findings must be documented in [SECURITY.md](SECURITY.md).
- **Integrity** — Every published package ships with SHA-256 and SHA-512 checksum sidecars. Verify the `.sha256` file from [GitHub Releases](https://github.com/rgsneddon/evolve/releases) or the [downloads page](https://rgsneddon.github.io/evolve/downloads/) **before installing**.

**Limitation:** Automated scans and checksums reduce risk but **cannot guarantee** that a build is free of malware or other security issues. Use current antivirus tools on your device, verify checksums, and install only from official release URLs.

**Regular command:** **run security audit** — `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_security_audit.ps1` (workspace wrapper: `..\run_security_audit.ps1` audits Evolve + Perccent).

Release pipeline entry points: `scripts/run_security_audit.ps1`, `scripts/scan_release_artifacts.ps1`, `scripts/audit_dependencies.ps1`, and `scripts/sign_download_packages.ps1` (gates signing). Post-work manual QA: [MANUAL_TESTS.md](MANUAL_TESTS.md).

---

## Build requirements

- **Flutter** 3.44+ (stable), **Dart** 3.12+
- **Windows:** Visual Studio 2022 Build Tools with C++ desktop workload
- **Android:** JDK 17+, Android SDK 35

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_all.ps1
powershell -ExecutionPolicy Bypass -File scripts/build_installers.ps1 -SkipCodeSign
powershell -ExecutionPolicy Bypass -File scripts/publish_github_release.ps1 -Version 4.1.3
# Optional: capture release/Pages evidence for CI or audit
powershell -ExecutionPolicy Bypass -File scripts/publish_github_release.ps1 -Version 4.1.3 -SkipBuild -EvidenceDir .\build\release-evidence
```

If the Windows INSTALL step fails with `C:\Program Files\evolve`, delete `build\windows` and rebuild (stale CMake cache).

**Distribution layout:** Full installer packages (`.exe`, `.apk`) are staged under `build/downloads/v<version>/` and published to **GitHub Releases**. GitHub Pages (`gh-pages`) hosts the web app, downloads landing page, and **checksum manifests only** in `downloads/v<version>/` (no full binaries on Pages). Release asset proof uses `gh release view` / GitHub API, not the release web UI.

## Project layout

```
lib/           Application source
assets/data/   Outcome registry (base rates)
scripts/       Tooling
tool/          Optional Grok proxy CLI
test/          Unit and widget tests
```

---

## License

Copyright (c) 2026 Evolve Chronoflux. All rights reserved.

The **Chronoflux Principia**, realised by **Roy D Herbert**, is a **core mechanical part** of the Evolve framework — the hydrodynamic constructs and analysis pipeline at the centre of the engine derive from and operate through that Principia. Evolve is a derivative computational implementation of that work.

Evolve and this Chronoflux implementation are **proprietary software** offered under a **dual licensing** model:

| Use | License |
|-----|---------|
| Personal, private, non-commercial use | [LICENSE](LICENSE) (proprietary grant) |
| Commercial use, redistribution, SaaS, or derivative products for sale | Separate **Commercial License** — contact [russell.gray.sneddon@gmail.com](mailto:russell.gray.sneddon@gmail.com) |

Third-party dependencies (Flutter packages, fonts, etc.) remain under their own licenses; see `NOTICES` in build outputs.
