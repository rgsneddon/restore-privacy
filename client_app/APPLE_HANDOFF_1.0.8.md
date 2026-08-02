# Apple ship — monopin 1.0.8

First-run: Suite account + 12-word seed + licence **before** VPN permissions.
Connect: 72h KEYGEN-free trial then KEYGEN.

## Residual public pins (inject)

Live catalog only: `node_elgamal.pub` (IS), `de_node_elgamal.pub` (DE),
`exit_node_elgamal.pub` (multihop exit). **`us_node_elgamal.pub` is retired** and
is **not** injected into Runner.app / restore_privacy_client.app.

## macOS (Developer ID + notarize)

`flutter build macos --release --build-name=1.0.8`  
`python3 scripts/sign_and_notarize_macos.py --app path/to/restore_privacy_client.app`  

**Developer ID Application** + **notarytool** notarize + staple. Team SFCBP95595.  
This Gatekeeper path applies to **macOS only**.

## iOS (Apple Distribution — not DevID/notarize)

`python3 scripts/build_suite_1.0.8.py --ios-only`  
Inject residual pubs (IS/DE/exit), then **Apple Distribution** Team-signed
Runner.app zip for sideload (same Team).

**Developer ID + notarytool cannot be used for iOS.** Apple notarization is a
macOS distribution process. iOS uses **Apple Distribution** (or App Store /
Development) identities — there is no “notarized Developer ID iOS app” acceptance
path equivalent to Gatekeeper.

## Paid path
`python3 scripts/build_suite_1.0.8.py --host-paid` or host_paid_assets_vps.
