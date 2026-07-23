# Windows handoff — Restore Privacy **0.4.1** (multi-hop residual)

Catalog monopin: **0.4.1**  
Production entry (default): **82.221.101.241:44044** (Iceland)  
Production exit (multi-hop residual): **185.146.232.107:44044** (Romania)

## Honesty (read first)

| Claim | Truth |
|-------|--------|
| Fresh Windows multihop PE from **macOS** | **Not possible** with the shipped PyInstaller path |
| File named `…-0.4.1-windows-x64-setup.exe` on Darwin | **Filename pin** of a prior multihop SFX — **not** a new freeze |
| Real multihop residual PE | Build **only on Windows x64** with the one-command path below |

Paid asset name after a real rebuild:

```text
releases\0.4.1\restore-privacy-client-0.4.1-windows-x64-setup.exe
```

## Windows laptop — quick start

```bat
git clone https://github.com/rgsneddon/restore-privacy.git
cd restore-privacy
git checkout main
git pull

REM 1) Source readiness (no freeze)
python scripts\build_windows_multihop.py --check-only

REM 2) Full PE rebuild (installs pyinstaller in .venv via bat)
scripts\build_windows_multihop.bat
```

Or without bat:

```bat
python -m pip install pyinstaller cryptography
python scripts\build_windows_multihop.py
```

**Output after success:**

```text
releases\0.4.1\restore-privacy-client-0.4.1-windows-x64-setup.exe
```

### Prereqs

| Need | Notes |
|------|--------|
| Windows **x64** | Build host (not Darwin) |
| Python 3.11+ | `py -3` or `python` on PATH |
| Network once | `pip install pyinstaller cryptography` (bat does this) |
| Repo at **0.4.1** / `main` | `git pull` latest |
| Tracked pubs | `product/node_elgamal.pub`, `product/exit_node_elgamal.pub` |
| Wintun | `client/windows/native/wintun.dll` or `wintun-amd64.dll` |

### What the PE embeds

- Current `client/` residual path including **`client/multihop.py`**
  (`MULTI_HOP_ROUTING_IMPLEMENTED = True`, residual-via-exit when enabled)
- **`product/node_elgamal.pub`** (entry) + **`product/exit_node_elgamal.pub`** (exit)
- Wintun, frozen runtime — **no** `*.priv` (device Ed25519 generated on first run)
- Privacy-scale Settings, hot-apply, node ping, keygen gate

## Check-only (safe on any OS)

```bat
python scripts\build_windows_multihop.py --check-only
```

```bash
# same on macOS (source readiness; PE freeze still requires Windows)
python3 scripts/build_windows_multihop.py --check-only
```

Expect: exit **0**, `VERSION=0.4.1`, entry+exit pubs, `multihop.py`, Wintun present.
PyInstaller missing → **warning** only for `--check-only` (install before full build).

## After a successful PE build

### 1. Smoke-check

```bat
dir releases\0.4.1\restore-privacy-client-0.4.1-windows-x64-setup.exe
python scripts\build_windows_multihop.py --check-only
```

Install the setup.exe:

- Default Connect → Iceland entry  
- `set RPT_MULTIHOP_ENABLED=1` then Connect → residual via Romania exit when multihop active  

### 2. Publish (operator)

```bat
gh release upload 0.4.1 releases\0.4.1\restore-privacy-client-0.4.1-windows-x64-setup.exe --clobber
python scripts\host_paid_assets_vps.py --stage
REM when Iceland SSH works:
REM python scripts\host_paid_assets_vps.py --stage --upload
```

### 3. Source commits

Usually you only **produce the PE**; source is already on `main`.
Do **not** commit secrets or `*.priv`.

## Multi-hop honesty (Windows)

| Mode | Behaviour |
|------|-----------|
| Default | Single-hop residual → Iceland entry + `node_elgamal.pub` |
| `RPT_MULTIHOP_ENABLED=1` | Residual-via-exit → Romania + `exit_node_elgamal.pub` |
| Not claimed | Full intermediate onion encapsulation through the entry hop |

## Logs if build fails

| Log | Path |
|-----|------|
| Client freeze | `dist/0.4.1/pyinstaller_client.log` |
| Installer freeze | `dist/0.4.1/pyinstaller_installer.log` |

- **PyInstaller missing** → bat installs it; or `pip install pyinstaller`
- **Missing exit pub** → `git pull` for `product/exit_node_elgamal.pub`
- **Wrong arch** → Windows **x64**
- **Antivirus** → allowlist `dist/` and `releases/`

## Related

- Catalog notes: `scripts/RELEASE_NOTES_0.4.1.md`
- Release index: `scripts/RELEASE.md` (platform status table)
- Laptop checklist: `scripts/LAPTOP_BUILD_CHECKLIST_0.4.1.md`
- Full multi-platform: `scripts/build_release_0.4.1.py`
- Multihop tests: `tests/test_multihop.py`
- Package pins: `tests/test_release_0_4_0_package_pins.py`

## Other 0.4.1 platforms (status for operators)

| Platform | Built on Mac? | Action on laptop if needed |
|----------|---------------|----------------------------|
| **Windows** | No (PE freeze) | **This handoff** — rebuild PE |
| **Android** | Yes (Flutter APK rebuilt) | Re-upload GH if release still has pre-rebuild APK |
| macOS | Yes (notarized) | None |
| iOS | Yes (Team-signed zip) | None |
| Linux | Yes | None |
