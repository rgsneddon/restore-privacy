# Release packaging notes

## Current tag script

| Tag | Script |
|-----|--------|
| **0.4.0** | `scripts/build_release_0.4.0.py` |
| **0.4.0 Windows multihop PE** | `scripts/build_windows_multihop.py` / `scripts/build_windows_multihop.bat` (Windows x64 only; handoff `client/windows/WINDOWS_HANDOFF_0.4.0.md`) |
| **0.4.0 laptop checklist** | `scripts/LAPTOP_BUILD_CHECKLIST_0.4.0.md` |
| **0.4.0 Apple handoff** | `client_app/APPLE_HANDOFF_0.4.0.md` |
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

Product node: **82.221.101.241:44044**. See `scripts/RELEASE_NOTES_0.4.0.md`.

### 0.4.0 platform build status (Mac operator vs laptop)

| Platform | Fully frozen on Mac? | Operator action |
|----------|----------------------|-----------------|
| Windows setup.exe | **No** (cannot PyInstaller-freeze PE on Darwin) | **Windows laptop:** `scripts\build_windows_multihop.bat` after `git pull` — see `client/windows/WINDOWS_HANDOFF_0.4.0.md` |
| Android APK | Yes (Flutter release rebuild) | Optional: re-upload GH if release asset is still pre-rebuild |
| macOS zip | Yes (DevID + notarized) | Done |
| iOS zip | Yes (Team-signed) | Done |
| Linux tgz | Yes | Done |

**Check without building (any OS):**

```bash
python3 scripts/build_windows_multihop.py --check-only
```

**0.4.0 highlights:** brand icons, privacy-scale Settings, free-tier 3.3.3 local flavor, rus@ contact, Apple Settings parity.

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
python scripts/build_release_0.4.0.py --apple-only
# Confirm releases/0.4.0/ has macos (+ ios if built) zip(s)
# Full catalog: python scripts/build_release_0.4.0.py
# Windows PE: on Windows x64 only — scripts\build_windows_multihop.bat
# gh release create 0.4.0 with those files (operator)
```
