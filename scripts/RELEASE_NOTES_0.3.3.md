**0.3.3** — Removed flyclient connect fast path; Connect always runs HELLO.

# Restore Privacy **0.3.3** — release notes

**Status:** Public package release (catalog + packaging).  
**Tag:** `0.3.3`  
**URL:** https://github.com/rgsneddon/restore-privacy/releases/tag/0.3.3

Catalog advances to **0.3.3**.

## Highlights

- **Flyclient removed** from product Connect: no residual HELLO/route skip path; Connect always performs a real HELLO (idempotent “already connected” only when not force-reconnecting).
- Production node remains **`82.221.101.241:44044`**.
- Wintun IF settle poll with legacy-floor max (~0.9s) and ASAP return.
- **Status / payments:** private `/admin` payment-processor settings + grants; paid downloads (£2.45 Stripe).
- Carries forward: macOS hide-to-tray after full-tunnel Connect; residual Team NE path; Settings transparency, licence gate, native pad/obfs/PFS.

## Downloads

| Asset | Notes |
|-------|--------|
| `restore-privacy-client-0.3.3-windows-x64-setup.exe` | Setup installer (rebuilt without flyclient) |
| `restore-privacy-client-0.3.3-android.apk` | Flutter APK |
| `restore-privacy-client-0.3.3-linux-x64.tar.gz` | Installer package (rebuilt without flyclient) |
| `restore-privacy-client-0.3.3-macos.zip` | **Developer ID signed + notarized** |
| `restore-privacy-client-0.3.3-ios.zip` | **Team-signed sideload** |

## Signing / privacy

- macOS: Developer ID Application + notarized/stapled.
- iOS: Apple Distribution team-signed sideload.
- Packages never ship `node_elgamal.priv` or a shared `client_ed25519.priv`.
- Residual public IP only when OS tunnel is connected.

## Upgrade

Paid catalog pin is **v0.3.3**. Replace prior installers.
