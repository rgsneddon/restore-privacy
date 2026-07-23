# Laptop checklist — catalog **0.4.0** platforms not fully frozen on the Mac

Use this on the **Windows x64 laptop** after `git pull origin main`.

## 1. Clone / update

```bat
git clone https://github.com/rgsneddon/restore-privacy.git
cd restore-privacy
git checkout main
git pull
```

Confirm pin:

```bat
type client\VERSION
REM expect: 0.4.0
```

## 2. Windows PE (required — not freezable on macOS)

### Read handoff

```text
client\windows\WINDOWS_HANDOFF_0.4.0.md
```

### Check source readiness (no freeze)

```bat
python scripts\build_windows_multihop.py --check-only
```

Expect exit code **0** and `VERSION=0.4.0`.

### Build the real multihop setup.exe

```bat
scripts\build_windows_multihop.bat
```

Output:

```text
releases\0.4.0\restore-privacy-client-0.4.0-windows-x64-setup.exe
```

### Publish after smoke test

```bat
gh release upload 0.4.0 releases\0.4.0\restore-privacy-client-0.4.0-windows-x64-setup.exe --clobber
python scripts\host_paid_assets_vps.py --stage
```

## 3. Android APK (optional GH refresh)

Mac already ran a full Flutter `assembleRelease` for **0.4.0** (local
`releases/0.4.0/…-android.apk`). If GitHub Release **0.4.0** still has the
older APK (smaller / pre-brand rebuild), re-upload from a machine that has
the rebuilt file, or rebuild:

```bash
# macOS / Linux with Android SDK + JDK 17
export JAVA_HOME=…   # e.g. Homebrew openjdk@17
export ANDROID_HOME=~/Library/Android/sdk
cd client_app && flutter build apk --release
cp build/app/outputs/flutter-apk/app-release.apk \
  ../releases/0.4.0/restore-privacy-client-0.4.0-android.apk
gh release upload 0.4.0 ../releases/0.4.0/restore-privacy-client-0.4.0-android.apk --clobber
```

## 4. Already complete (no laptop rebuild)

| Package | Status |
|---------|--------|
| macOS zip | Notarized Developer ID — on GH 0.4.0 |
| iOS zip | Team-signed sideload — on GH 0.4.0 |
| Linux tgz | Rebuilt package_linux — on GH 0.4.0 |

## 5. Free tier 3.3.3

Local only under `releases/free/3.3.3/` — **do not** upload to GH/VPS paid catalog
until explicitly requested.

## 6. Verify on GitHub (no build)

After push of this handoff, on any machine:

```bash
git pull
test -f client/windows/WINDOWS_HANDOFF_0.4.0.md && echo handoff_ok
python3 scripts/build_windows_multihop.py --check-only
python3 -m unittest tests.test_release_0_4_0_package_pins.Test040SourcePins -v
```
