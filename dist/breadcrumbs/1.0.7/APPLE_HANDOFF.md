# Apple ship — monopin 1.0.7

## macOS
Build Suite from `client_app` (`flutter build macos --release`), wrap as  
`restore-privacy-client-1.0.7-macos.zip`, then:

```bash
python3 scripts/sign_and_notarize_macos.py --app path/to/restore_privacy_client.app
```

Developer ID + notarize + staple. Team **SFCBP95595**.

## iOS
Catalog package is a Flutter release **Runner.app** zip  
(`restore-privacy-client-1.0.7-ios.zip`) with residual pins injected (no `.priv`).
The host `Runner.app` in this monopin is **not** Apple Distribution–signed
(no top-level `_CodeSignature`; built with Flutter `--no-codesign` path).
Full Distribution IPA needs `ios/ExportOptions.plist` + Xcode archive export —
do that on a Mac with the Distribution identity before claiming Team-signed
sideload for App Store–style install.

## Paid path
Stage under `releases/1.0.7/` and `status_page/assets/1.0.7/`, then Helsinki upload  
(`scripts/build_suite_1.0.7.py --host-paid` or `stage_paid_assets` / `host_paid_assets_vps`).

## KEYGEN
Unlock UI always offers **Get keygen** → `https://restoreprivacy.online/pay`.

---

> **Breadcrumbs vault (Helsinki)** is the source of truth for “what to update” on this monopin. Do **not** treat a private GitHub pull of this file as the primary task queue.
> Fetch: `https://135.181.152.10.sslip.io/breadcrumbs/current/manifest.json` with `X-RPT-Asset-Token`.
