# Apple breadcrumbs checklist — monopin 1.0.6

Generated: 2026-08-02T09:01:09Z
Source of truth: **helsinki_breadcrumbs_vault** (GitHub breadcrumb pull: **deprecated**)

## Operator mandate (monopin 1.0.6)

- **Built this:** Windows / Linux / Android packages for **1.0.6** (restore-privacy-client-1.0.6-windows-x64-setup.exe, …-linux-x64.tar.gz, …-android.apk).
- **Update these docs:** APPLE_HANDOFF_1.0.6.md, RELEASE_NOTES_1.0.6.md, PRIVACY_POLICY, AUDIT, settings explainer, downloads monopin — all to **1.0.6**.
- **Publish all to the version number of this build (1.0.6):** every platform installer under paid_assets/1.0.6/ and status assets — macOS + iOS after Mac seal. Do not invent a different version or wait for a separate commit command.

## Actions
- `rebuild_ios_team_sign`

## Platform honesty
- **macos**: status=`native_monopin` needs_work=`False` bundle=`1.0.6` — CFBundle/marketing version 1.0.6 matches monopin 1.0.6.
- **ios**: status=`carry_forward_or_lag` needs_work=`True` bundle=`1.0.2` — Internal version '1.0.2' != monopin '1.0.6' — native rebuild/seal needed for honest ios.

## Steps
- BUILT (this build monopin 1.0.6): Windows setup.exe, Linux tar.gz, Android APK as restore-privacy-client-1.0.6-* (this host). Apple packages not sealed here — Mac rebuild/sign required.
- UPDATE THESE DOCS to monopin 1.0.6: client_app/APPLE_HANDOFF_1.0.6.md, scripts/RELEASE_NOTES_1.0.6.md, PRIVACY_POLICY.md, AUDIT.md, status_page/settings_explainer.py (Settings guide), status_page/downloads.py RELEASE_VERSION, client/VERSION.
- PUBLISH ALL to the version number of this build (1.0.6): stage/upload every platform package under paid_assets/1.0.6/ and status_page/assets/1.0.6/ (Windows + Linux + Android already built; macOS + iOS after native seal). No separate commit/version guess — use monopin 1.0.6 everywhere.
- 1. Fetch vault: breadcrumbs_vault.py check --fetch
- 2. If macos needs_work: flutter build macos + notarize per APPLE_HANDOFF
- 3. If ios needs_work: flutter build ios + Team-sign per APPLE_HANDOFF
- 4. Stage/upload paid assets for 1.0.6 (Helsinki), then re-publish breadcrumbs
- 5. Re-run check until needs_any_apple_work is false
- 6. Windows machine: set RPT_WINDOWS_DRIVE to the large drive; python scripts/windows_brand_mirror.py apply — monorepo + all brand installer slots (35 packages); then native PE seal + upload

Fetch: `python3 scripts/breadcrumbs_vault.py check --fetch` with `RPT_ASSET_FETCH_TOKEN` set.
