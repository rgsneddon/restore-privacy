# Windows handoff â€” Restore Privacy **0.3.9** (multi-hop residual)

Catalog monopin: **0.3.9**  
Production entry (default): **82.221.101.241:44044** (Iceland)  
Production exit (multi-hop residual): **185.146.232.107:44044** (Romania)

Catalog **0.3.9** Windows multihop residual PE is built on a **Windows x64**
machine via the one-command path below (macOS cannot freeze a Windows PE).
Paid asset name: `restore-privacy-client-0.3.9-windows-x64-setup.exe`.

## One command (Windows laptop)

From the **repo root** after checkout:

```bat
scripts\build_windows_multihop.bat
```

Or:

```bat
python scripts\build_windows_multihop.py
```

**Output:**

```text
releases\0.3.9\restore-privacy-client-0.3.9-windows-x64-setup.exe
```

That PE embeds:

- Current `client/` residual path including **`client/multihop.py`**
  (`MULTI_HOP_ROUTING_IMPLEMENTED = True`, residual-via-exit when enabled)
- **`product/node_elgamal.pub`** (entry) + **`product/exit_node_elgamal.pub`** (exit)
- Wintun, frozen runtime â€” **no** `*.priv` (device Ed25519 generated on first run)

### Prereqs

| Need | Notes |
|------|--------|
| Windows **x64** | Build host |
| Python 3.11+ (3.12/3.14 OK if PyInstaller supports it) | `py -3` or `python` on PATH |
| Network once | `pip install pyinstaller cryptography` (bat does this) |
| Repo at **0.3.9** / `main` | `git checkout 0.3.9` or latest `main` with handoff |
| Tracked pubs | `product/node_elgamal.pub`, `product/exit_node_elgamal.pub` (in git) |
| Wintun | `client/windows/native/wintun.dll` or `wintun-amd64.dll` (in git) |

Check without building:

```bat
python scripts\build_windows_multihop.py --check-only
```

## What the builder does

1. Pins `client/VERSION` â†’ `0.3.9`
2. PyInstaller **onedir** of `client/windows/app.py` (hidden-import `client.multihop`, â€¦)
3. Injects entry + exit **public** keys into `secrets/` and `product/`
4. PyInstaller **onefile** setup wrapping `client/windows/installer.py` + payload
5. Writes `releases/0.3.9/â€¦-windows-x64-setup.exe` and refreshes `SHA256SUMS.json` / `manifest.json` when present

Recipe core: `scripts/build_release_0.0.8.py` (version constants overridden for 0.3.9).

## After a successful build

### 1. Smoke-check the PE (on the build PC)

```bat
python scripts\build_windows_multihop.py --check-only
dir releases\0.3.9\restore-privacy-client-0.3.9-windows-x64-setup.exe
```

Optional: search the binary (PowerShell) for multihop markers:

```powershell
Select-String -Path releases\0.3.9\restore-privacy-client-0.3.9-windows-x64-setup.exe -Pattern "exit_node_elgamal","185.146.232.107","multihop" -Encoding byte -ErrorAction SilentlyContinue
# Or install and run with:
#   set RPT_MULTIHOP_ENABLED=1
# then Connect â€” residual should dial Romania exit when multihop is active.
```

Install the setup.exe, confirm:

- Default Connect â†’ Iceland entry  
- `RPT_MULTIHOP_ENABLED=1` â†’ residual via Romania exit  
- No free public installers; payment/entitlement unchanged  

### 2. Publish for paid downloads

```bat
gh release upload 0.3.9 releases\0.3.9\restore-privacy-client-0.3.9-windows-x64-setup.exe --clobber
python scripts\host_paid_assets_vps.py --stage
REM when Iceland SSH works:
REM python scripts\host_paid_assets_vps.py --stage --upload
```

Render / status host fulfils via **private GH API** (`RPT_GITHUB_TOKEN`) and/or
staged `status_page/assets/0.3.9/` + VPS paid_assets when configured.

### 3. Commit / tag (if you change source while building)

Usually the handoff only **produces the PE**; source is already on `main`.
If you change Windows code, open a PR or push as usual â€” **do not commit secrets**.

## Multi-hop honesty (Windows)

| Mode | Behaviour |
|------|-----------|
| Default | Single-hop residual â†’ Iceland entry + `node_elgamal.pub` |
| `RPT_MULTIHOP_ENABLED=1` | Residual-via-exit â†’ Romania + `exit_node_elgamal.pub` |
| Not claimed | Full intermediate onion encapsulation through the entry hop |

Node-only zram + LUKS2 never ships in the client package.

## Logs if build fails

| Log | Path |
|-----|------|
| Client freeze | `dist/0.3.9/pyinstaller_client.log` |
| Installer freeze | `dist/0.3.9/pyinstaller_installer.log` |

Common issues:

- **PyInstaller missing** â†’ bat installs it; or `pip install pyinstaller`
- **Missing exit pub** â†’ pull latest `product/exit_node_elgamal.pub` from git
- **Wrong arch** â†’ use Windows **x64**, not ARM64-only Python unless you know you need it
- **Antivirus** â†’ may quarantine freshly frozen PE; allowlist the repo `dist/` and `releases/`

## Related

- Catalog / release notes: `scripts/RELEASE_NOTES_0.3.9.md`
- Full multi-platform release script: `scripts/build_release_0.3.9.py` (`--windows-only` rebuilds Windows via this path)
- Multihop unit tests: `tests/test_multihop.py`
- Package pin honesty: `tests/test_release_0_3_6_package_pins.py` (Windows PE multihop gates run when the rebuilt setup is present under `releases/0.3.9/`)

