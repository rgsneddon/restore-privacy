# Restore Privacy client

## Windows (this machine)

```bash
# From repo root, with secrets present:
python -m client.windows
```

Requires:

1. Secrets in `./secrets/` (gitignored) — copy from Vultr `/opt/restore-privacy/secrets/`:
   - `client_ed25519.priv`
   - `node_elgamal.pub`
2. **Elevation for full tunnel** (Wintun NIC + system routes). You do **not** need to
   right-click **Run as administrator**: the app **auto-prompts UAC** on launch, and
   installer shortcuts are marked to elevate on double-click (one **Yes** click).
3. `client/windows/native/wintun.dll` (shipped open-source TUN driver — not the WireGuard protocol).

Without elevation, the session can still handshake but OS-wide routes cannot be installed.
A zero-UAC full-system VPN would need a pre-installed privileged Windows service; the
one-click UAC re-launch is the practical workaround.

Retro UI: dark blue banner, black background, white text, scrolling privacy string; **auto-connect on launch**.

## Android

```bash
cd client_app
flutter run   # device/emulator with VPN permission
# or
flutter build apk
```

## iOS / macOS

See `client_app/ios/BUILD_ON_MAC.md` and `client_app/macos/BUILD_ON_MAC.md`.
