# Apple breadcrumbs checklist — monopin 1.0.2

Generated: 2026-08-01T07:50:36Z
Source of truth: **helsinki_breadcrumbs_vault** (GitHub breadcrumb pull: **deprecated**)

## Operator mandate (monopin 1.0.2)

- **Built this:** Windows / Linux / Android packages for **1.0.2** (restore-privacy-client-1.0.2-windows-x64-setup.exe, …-linux-x64.tar.gz, …-android.apk).
- **Update these docs:** APPLE_HANDOFF_1.0.2.md, RELEASE_NOTES_1.0.2.md, PRIVACY_POLICY, AUDIT, settings explainer, downloads monopin — all to **1.0.2**.
- **Publish all to the version number of this build (1.0.2):** every platform installer under paid_assets/1.0.2/ and status assets — macOS + iOS after Mac seal. Do not invent a different version or wait for a separate commit command.

## Actions
- `none_apple_up_to_date`

## Platform honesty
- **macos**: status=`native_monopin` needs_work=`False` bundle=`1.0.2` — CFBundle/marketing version 1.0.2 matches monopin 1.0.2.
- **ios**: status=`native_monopin` needs_work=`False` bundle=`1.0.2` — CFBundle/marketing version 1.0.2 matches monopin 1.0.2.

## Steps
- BUILT (this build monopin 1.0.2): Windows setup.exe, Linux tar.gz, Android APK as restore-privacy-client-1.0.2-* (this host). Apple packages not sealed here — Mac rebuild/sign required.
- UPDATE THESE DOCS to monopin 1.0.2: client_app/APPLE_HANDOFF_1.0.2.md, scripts/RELEASE_NOTES_1.0.2.md, PRIVACY_POLICY.md, AUDIT.md, status_page/settings_explainer.py (Settings guide), status_page/downloads.py RELEASE_VERSION, client/VERSION.
- PUBLISH ALL to the version number of this build (1.0.2): stage/upload every platform package under paid_assets/1.0.2/ and status_page/assets/1.0.2/ (Windows + Linux + Android already built; macOS + iOS after native seal). No separate commit/version guess — use monopin 1.0.2 everywhere.
- 1. Fetch vault: breadcrumbs_vault.py check --fetch
- 2. If macos needs_work: flutter build macos + notarize per APPLE_HANDOFF
- 3. If ios needs_work: flutter build ios + Team-sign per APPLE_HANDOFF
- 4. Stage/upload paid assets for 1.0.2 (Helsinki), then re-publish breadcrumbs
- 5. Re-run check until needs_any_apple_work is false
- 6. Windows machine: set RPT_WINDOWS_DRIVE to the large drive; python scripts/windows_brand_mirror.py apply — monorepo + all brand installer slots (35 packages); then native PE seal + upload

Fetch: `python3 scripts/breadcrumbs_vault.py check --fetch` with `RPT_ASSET_FETCH_TOKEN` set.
