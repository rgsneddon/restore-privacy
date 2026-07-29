# Windows handoff — Restore Privacy **0.5.6**

Catalog monopin: **0.5.6**

| Platform | Package | Notes |
|----------|---------|--------|
| Windows | `restore-privacy-client-0.5.6-windows-x64-setup.exe` | **native** multihop PE — US residual pin (`us_node_elgamal.pub`), lean residual defaults |
| Android | `restore-privacy-client-0.5.6-android.apk` | **native** Flutter rebuild — residual wire + US pin |
| Linux | `restore-privacy-client-0.5.6-linux-x64.tar.gz` | catalog pin with IS/RO/US pubs |
| macOS / iOS | not sealed on this host for 0.5.6 | Apple residual seal separate |

## Build

```text
python scripts\build_windows_multihop.py
# or
python scripts\build_release_0.5.6.py --windows-only
```

Android:

```text
cd client_app
flutter build apk --release
copy build\app\outputs\flutter-apk\app-release.apk ..\releases\0.5.6\restore-privacy-client-0.5.6-android.apk
```

## Host

```text
python scripts\host_paid_assets_vps.py --stage --upload --version 0.5.6 --force --allow-missing
```

## App testers (unlinked)

Direct URL only: `https://restoreprivacy.online/app-testers`  
Not linked from homepage/downloads/footer. Licence accept → one package → KEYGEN + download. Second package refused.
