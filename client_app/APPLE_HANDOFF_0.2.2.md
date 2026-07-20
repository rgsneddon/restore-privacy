# Apple handoff — Restore Privacy 0.2.2

Production RPT node: **82.221.101.241:44044** (UDP).

## What this zip is

Release **macOS/iOS** packages for 0.2.2 may be **prep packages** staged on Windows for sideload / further Mac work. Residual public IP requires a **signed Packet Tunnel / Network Extension** built from current `client_app` sources on a Mac.

## On a Mac

1. Clone / pull `main` at tag **0.2.2**.
2. Confirm `lib/rpt_config.dart` host = `82.221.101.241`.
3. Inject **only** `node_elgamal.pub` (from `product/node_elgamal.pub` or node secrets) — never `node_elgamal.priv` / never shared `client_ed25519.priv`.
4. Follow:
   - `APPLE_BUILD.md`
   - `macos/BUILD_ON_MAC.md`
   - `ios/BUILD_ON_MAC.md`
5. Team-sign + notarize macOS; provision iOS for device install.
6. Rebuild zips and attach to GitHub Release **0.2.2** if replacing prep assets.

## Privacy notes for Apple residual

- Do not market residual IP change until NE is signed and active.
- Host-side HELLO alone is diagnostic only.
- Device Ed25519 keys generate on first run.
- Flutter Settings includes audit / privacy policy / end user licence links (rebuild APK/app for full UI).

## Product keys

| Ship | Never ship |
|------|------------|
| `node_elgamal.pub` | `node_elgamal.priv`, shared `client_ed25519.priv` |
