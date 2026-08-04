# Apple breadcrumbs checklist — monopin 1.2.0

Generated: 2026-08-04T22:28:17Z
Source of truth: **helsinki_breadcrumbs_vault** (GitHub breadcrumb pull: **deprecated**)

## Operator mandate (monopin 1.2.0)

- **Built this:** Windows / Linux / Android packages for **1.2.0** (restore-privacy-client-1.2.0-windows-x64-setup.exe, …-linux-x64.tar.gz, …-android.apk).
- **Update these docs:** APPLE_HANDOFF_1.2.0.md, RELEASE_NOTES_1.2.0.md, PRIVACY_POLICY, AUDIT, settings explainer, downloads monopin — all to **1.2.0**.
- **Publish all to the version number of this build (1.2.0):** every platform installer under paid_assets/1.2.0/ and status assets — macOS + iOS after Mac seal. Do not invent a different version or wait for a separate commit command.

## Actions
- `none_apple_up_to_date`

## Platform honesty
- **macos**: status=`native_monopin` needs_work=`False` bundle=`1.2.0` — CFBundle/marketing version 1.2.0 matches monopin 1.2.0.
- **ios**: status=`native_monopin` needs_work=`False` bundle=`1.2.0` — CFBundle/marketing version 1.2.0 matches monopin 1.2.0.

## Steps
- BUILT (this build monopin 1.2.0): Windows setup.exe, Linux tar.gz, Android APK as restore-privacy-client-1.2.0-* (this host). Apple packages not sealed here — Mac rebuild/sign required.
- UPDATE THESE DOCS to monopin 1.2.0: client_app/APPLE_HANDOFF_1.2.0.md, scripts/RELEASE_NOTES_1.2.0.md, PRIVACY_POLICY.md, AUDIT.md, status_page/settings_explainer.py (Settings guide), status_page/downloads.py RELEASE_VERSION, client/VERSION.
- PUBLISH ALL to the version number of this build (1.2.0): stage/upload every platform package under paid_assets/1.2.0/ and status_page/assets/1.2.0/ (Windows + Linux + Android already built; macOS + iOS after native seal). No separate commit/version guess — use monopin 1.2.0 everywhere.
- 1. Fetch vault: breadcrumbs_vault.py check --fetch
- 2. If macos needs_work: flutter build macos + notarize per APPLE_HANDOFF
- 3. If ios needs_work: flutter build ios + Team-sign per APPLE_HANDOFF
- 4. Stage/upload paid assets for 1.2.0 (Helsinki), then re-publish breadcrumbs
- 5. Re-run check until needs_any_apple_work is false
- 6. Windows machine: set RPT_WINDOWS_DRIVE to the large drive; python scripts/windows_brand_mirror.py apply — monorepo + all brand installer slots (35 packages); then native PE seal + upload
- 7. Windows machine: open client/windows/WINDOWS_HANDOFF_1.2.0.md — full product map: first-run licence (scroll-to-bottom) → KEYGEN or continue 72h trial (no username/password/seed); residual VPN-only shell (no Evolve/%/rpAI/Backup chrome); Quit lower-left disconnect-then-exit; tray text exactly Privacy, Restored; residual IS+DE; manual free-DL updates only (no UPDATE_PUSH); then native PE seal + upload paid_assets/1.2.0/
- 8. Windows machine OBSERVE (macOS 1.2.0 dual-identity parity): after KEYGEN/trial Connect, hash client_ed25519.priv under %USERPROFILE%\.restore-privacy\secrets and %LOCALAPPDATA%\Programs\RestorePrivacy\secrets — they must match. If Connect log shows node assigned 10.88.x but residual/Wintun not active, report both hash prefixes + log excerpt (not trial-expired when node IP was assigned). See WINDOWS_HANDOFF section 0b.

Fetch: `python3 scripts/breadcrumbs_vault.py check --fetch` with `RPT_ASSET_FETCH_TOKEN` set.
