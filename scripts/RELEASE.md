# Release packaging notes

## Current tag script

| Tag | Script |
|-----|--------|
| **0.4.2** (current) | `scripts/build_release_0.4.2.py` |
| **0.4.2 Windows multihop PE** | `scripts/build_windows_multihop.py` / `scripts/build_windows_multihop.bat` (Windows x64 only; handoff `client/windows/WINDOWS_HANDOFF_0.4.2.md`) |
| **0.4.2 notes** | `scripts/RELEASE_NOTES_0.4.2.md` |
| 0.4.1 | `scripts/build_release_0.4.1.py` (archive) |
| 0.4.0 | `scripts/build_release_0.4.0.py` (archive) |
| 0.3.8 | `scripts/build_release_0.3.8.py` (archive) |
| 0.3.7 | `scripts/build_release_0.3.7.py` (archive) |
| 0.3.6 | `scripts/build_release_0.3.6.py` (archive) |
| 0.3.4 | `scripts/build_release_0.3.4.py` (archive) |
| 0.3.3 | `scripts/build_release_0.3.3.py` (archive) |
| 0.3.0 | `scripts/build_release_0.3.0.py` (archive) |
| 0.2.3 | `scripts/build_release_0.2.3.py` (archive) |
| 0.2.2 | `scripts/build_release_0.2.2.py` (archive) |
| 0.2.1 | `scripts/build_release_0.2.1.py` (archive) |
| 0.2.0 | `scripts/build_release_0.2.0.py` (archive) |
| 0.1.8 | `scripts/build_release_0.1.8.py` (archive) |

Product node: **82.221.101.241:44044**. See `scripts/RELEASE_NOTES_0.4.2.md`.

### 0.4.2 platform build status (Mac operator vs laptop)

| Platform | Fully frozen on Mac? | Operator action |
|----------|----------------------|-----------------|
| Windows setup.exe | **No** (cannot PyInstaller-freeze PE on Darwin) | **Windows laptop:** `scripts\build_windows_multihop.bat` after `git pull` — see `client/windows/WINDOWS_HANDOFF_0.4.2.md` |
| Android APK | Flutter release when SDK present; else residual-wire carry-forward | Rebuild on host with Android SDK for native freeze |
| macOS zip | Yes (DevID + notarized) when secrets present | `flutter build macos` + `build_release_0.4.2.py` |
| iOS zip | Yes (Team-signed) when secrets present | `flutter build ios --no-codesign` + package |
| Linux tgz | Yes | `package_linux.py` / full release builder |

**Check without building (any OS):**

```bash
python3 scripts/build_windows_multihop.py --check-only
```

**0.4.2 highlights:** lean Settings defaults (startup/autoconnect/shape/obfs/multihop **off**; residual core always on), catalog monopin **0.4.2**, honest Windows/Android carry-forward breadcrumbs.

Older `build_release_0.*.py` files are historical archives. Prefer copying the
**latest** script when starting a new version.

Shared gates every release must keep:

1. **`_assert_no_priv(OUT)`** on the release output directory.
2. Inject / provision **only** `node_elgamal.pub` — never `node_elgamal.priv` (prefer `product/node_elgamal.pub`).
3. **Never force-add `secrets/`** to git.
4. **Linux wheels:** re-run `python scripts/package_linux.py` so manylinux **CPython 3.8–3.12** wheels stay current.

## Checklist (short)

```bash
# Bump VERSION / downloads catalog / installer VERSION first
# Mac: flutter build macos --release, then package (DevID + notarize)
python scripts/build_release_0.4.2.py --apple-only
# Confirm releases/0.4.2/ has macos (+ ios if built) zip(s)
# Full catalog: python scripts/build_release_0.4.2.py
# Windows PE: on Windows x64 only — scripts\build_windows_multihop.bat
# gh release create 0.4.2 with those files (operator)
```
