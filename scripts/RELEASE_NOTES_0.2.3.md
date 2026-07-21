# Restore Privacy **0.2.3** — release notes

**Status:** Public package release (signed Apple packages published).  
**Tag:** `0.2.3`  
**URL:** https://github.com/rgsneddon/restore-privacy/releases/tag/0.2.3

## Highlights

- Production node remains **`82.221.101.241:44044`**.
- **Settings transparency:** local-only connection log (exportable), leak test control, DPI / traffic-analysis mitigation disclaimers.
- **Licence acceptance gate** before Connect (and autoconnect); anonymous device registration (OS elevation for residual still separate).
- **Native residual wire parity:** Android + Apple NativePrep dual-wire pad/cover, outer obfs, PFS (product obfs key **33** bytes).
- **Monitoring without logging:** process-wide aggregates only; public status stays title-only.
- Threat model docs in `audit.md`, `PRIVACY_POLICY.md`, and `README.md`.
- Node FDE and ephemeral / short-lived node operator helpers.

## Downloads

| Asset | Notes |
|-------|--------|
| `restore-privacy-client-0.2.3-windows-x64-setup.exe` | Setup installer |
| `restore-privacy-client-0.2.3-android.apk` | Flutter APK |
| `restore-privacy-client-0.2.3-linux-x64.tar.gz` | Installer package |
| `restore-privacy-client-0.2.3-macos.zip` | **Developer ID signed + notarized** (`node_elgamal.pub` only) |
| `restore-privacy-client-0.2.3-ios.zip` | **Team-signed sideload** (`node_elgamal.pub` only) |

## Signing / privacy

- macOS: Developer ID Application (SFCBP95595) + notarized/stapled.
- iOS: Apple Distribution team-signed sideload (Runner + Packet Tunnel).
- Packages never ship `node_elgamal.priv` or a shared `client_ed25519.priv`.
- Residual public IP only when OS tunnel is connected.

## Upgrade

Install **0.2.3** from this GitHub Release or the status page. Accept the end-user licence on first Connect.
