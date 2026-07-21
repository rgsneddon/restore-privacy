# Restore Privacy client

## Restore Internet (failsafe) — BIG WARNING

Each platform ships a user-facing **Restore Internet** artifact for residual
network restore **plus** complete product removal.

> **WARNING:** Running **Restore Internet** will **ERASE ALL** parts of
> **Restore Privacy** from the device (app, tunnel residual, shortcuts, product
> secrets). You may **not** be able to automatically re-download your
> subscription app afterward. Contact **russell.gray.sneddon@gmail.com** to
> obtain a new download link.

| Platform | Artifact |
|----------|----------|
| Windows | `client/windows/Restore Internet.bat` |
| Linux | `client/linux/Restore Internet` |
| macOS | `client_app/macos/Restore Internet.command` |
| iOS | `client_app/ios/Restore Internet.txt` |
| Android | `client_app/android/app/src/main/assets/Restore Internet.txt` |

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
