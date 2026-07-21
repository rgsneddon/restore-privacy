# Apple handoff — Restore Privacy **0.3.2**

Prior catalog **0.3.0** remains published; **0.3.2** is the current Apple-fixed catalog.

Production RPT node: **82.221.101.241:44044** (UDP).

## Public package status (current)

| Asset | Signing (GitHub Release **0.3.2**) |
|-------|-------------------------------------|
| `restore-privacy-client-0.3.2-macos.zip` | **Developer ID Application** (SFCBP95595) + **notarized** (stapled) |
| `restore-privacy-client-0.3.2-ios.zip` | **Apple Distribution** Team-signed sideload (Runner + Packet Tunnel) |

Both inject **`node_elgamal.pub` only**. No `*.priv` in packages. Per-device Ed25519 is generated on first run.

Download: https://github.com/rgsneddon/restore-privacy/releases/tag/0.3.2

**Do not treat 0.3.2 public Apple assets as prep-only.** Prep-stage wording applies only if you are rebuilding from source before re-sign.

### macOS open fix (Developer ID host entitlements)

If open fails with *The application “restore_privacy_client” can’t be opened*
(`RBSRequestErrorDomain` / POSIX 163, binary exit 137):

1. Strip any embedded **development** `embedded.provisionprofile` before DevID re-sign.
2. Sign the **host** with `macos/Runner/DeveloperID.entitlements` — Flutter CS keys
   (allow-jit / unsigned-executable-memory / disable-library-validation), network,
   App Group — **without** `com.apple.developer.networking.networkextension` on the host.
3. Keep `packet-tunnel-provider` NE only on `PacketTunnel.appex` (`PacketTunnel.entitlements`).
4. Re-run `scripts/sign_and_notarize_macos.py` and replace the GitHub **0.3.2** macOS zip.

Restricted NE on a Developer ID–signed host without a matching Developer ID profile
is killed by AMFI; that was the root cause of the public zip not opening.

### macOS tray (0.3.2)

After product full-tunnel Connect, the main window hides to a menu-bar tray
(Show / Disconnect / Quit). Hide and window-close do **not** stop the Packet Tunnel.

## Residual honesty

- Residual public IP changes only when the OS Packet Tunnel is **connected**.
- Host-side HELLO alone is diagnostic; it does not install system residual routes.

## Rebuild on a Mac (optional operator path)

1. Checkout tag **0.3.2** (or current `main` with 0.3.2 surfaces).
2. Confirm `client_app/lib/rpt_config.dart` host = `82.221.101.241`.
3. Inject **only** `node_elgamal.pub` via `scripts/inject_apple_secrets.py` — never `node_elgamal.priv` / never shared `client_ed25519.priv`.
4. Follow `APPLE_BUILD.md`, `macos/BUILD_ON_MAC.md`, `ios/BUILD_ON_MAC.md`.
5. Sign/notarize: `scripts/sign_and_notarize_macos.py` (macOS); Distribution codesign for iOS.
6. Package via `scripts/build_release_0.3.2.py` and attach to GitHub Release **0.3.2** if replacing assets.

## Product UI notes (in-tree)

- Licence acceptance before Connect.
- Connection log, leak test, DPI mitigation disclaimer on Settings.
- macOS menu-bar tray after full-tunnel Connect.
- NativePrep residual engines: pad/cover + outer obfs + PFS (product obfs key **33** bytes).
