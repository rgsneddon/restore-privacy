# Windows handoff — catalog **0.4.8**

## Pins
1. `client/VERSION` → `0.4.8`
2. Catalog `status_page/downloads.py` `RELEASE_VERSION` / `RELEASE_TAG` → `0.4.8`
3. Filename: `restore-privacy-client-0.4.8-windows-x64-setup.exe`

## Product UI (this pin)
- Banner: **Virtual Private Network**
- Main shell **country picker** above Connect (IS / RO / DE + flags; default IS)
- Faster warm Connect (skip serial status-host when local entitlement ready)
- Faster Disconnect/Quit residual teardown (single restore pass; capped shell timeouts)

## Settings defaults (unchanged lean)
Optional residual scale (shape / outer obfs / multi-hop) **off** by default; core residual always required.

## Build (Windows x64)

```bat
python scripts\build_windows_multihop.py
python scripts\build_release_0.4.8.py --windows-only
```

Or full multi-platform stage:

```bat
python scripts\build_release_0.4.8.py
```

Then stage paid assets:

```bat
python scripts\host_paid_assets_vps.py --stage --upload --version 0.4.8 --force
```

## Honesty
- Catalog 0.4.8 filename alone is not proof of native Windows code freeze — prefer multihop PE rebuild on this host.
- Do not ship `*.priv` keys.
