# Gatekeeper fix — restore_privacy_client "Apple could not verify… / Not Opened"

## Cause
Catalog monopin zip was signed with **Apple Development** (and had a broken
deep codesign on FlutterMacOS). Gatekeeper rejects Development-signed downloads.

## Fix (executed this session)
1. `flutter build macos --release --build-name=1.0.2`
2. `scripts/sign_and_notarize_macos.py` with **Developer ID Application** +
   notarytool (AuthKey_L4R8L26JA5) + staple
3. Notary submission `1125790c-c5c8-40b1-b272-a6412f1f1a28` → **Accepted**
4. `spctl`: **accepted / source=Notarized Developer ID**
5. Staged `releases/1.0.2/` + `status_page/assets/1.0.2/` catalog basename
6. Uploaded Helsinki `paid_assets/1.0.2/restore-privacy-client-1.0.2-macos.zip`

## Honesty
- `sign_and_notarize_macos.py` now fails if leaf authority is not Developer ID
- `apple_package_audit.distribution_seal_ok_from_codesign` rejects Apple Development
- Live assess of monopin zip requires Notarized Developer ID via spctl
