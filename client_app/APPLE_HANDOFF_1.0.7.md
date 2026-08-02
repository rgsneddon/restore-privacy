# Apple ship — monopin 1.0.7

## macOS
Build Suite from `client_app` (`flutter build macos --release`), wrap as  
`restore-privacy-client-1.0.7-macos.zip`, then:

```bash
python3 scripts/sign_and_notarize_macos.py --app path/to/restore_privacy_client.app
```

Developer ID + notarize + staple. Team **SFCBP95595**.

## iOS
Catalog package is an **Apple Distribution** Team-signed **Runner.app** zip  
(`restore-privacy-client-1.0.7-ios.zip`) with residual **public** pins injected
(no `.priv`): `node_elgamal.pub`, `de_`, `exit_`, `us_`.

`scripts/build_suite_1.0.7.py` **always** runs inject (`inject_apple_secrets`
with iOS layout) **before** Distribution codesign and catalog zip — do not skip
inject as a manual afterthought. Equivalent one-liner:

```bash
python3 scripts/inject_apple_secrets.py \
  --app client_app/build/ios/iphoneos/Runner.app --ios
```

Full App Store–style IPA still needs `ios/ExportOptions.plist` + Xcode archive
export — not required for the catalog sideload zip.

## Paid path
Stage under `releases/1.0.7/` and `status_page/assets/1.0.7/`, then Helsinki upload  
(`scripts/build_suite_1.0.7.py --host-paid` or `stage_paid_assets` / `host_paid_assets_vps`).

## KEYGEN
Unlock UI always offers **Get keygen** → `https://restoreprivacy.online/pay`.
