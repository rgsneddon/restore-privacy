# Windows handoff — catalog **0.4.6**

## Pins
1. `client/VERSION` → `0.4.6`
2. Catalog `status_page/downloads.py` `RELEASE_VERSION` / `RELEASE_TAG` → `0.4.6`
3. Filename: `restore-privacy-client-0.4.6-windows-x64-setup.exe`

## Settings defaults (unchanged lean)
Optional residual scale (shape / outer obfs / multi-hop) **off** by default; core residual always required.

## Build (Windows x64)

```bat
python scripts\build_windows_multihop.py
python scripts\build_release_0.4.6.py --windows-only
```

Or full multi-platform stage:

```bat
python scripts\build_release_0.4.6.py
```

Then stage paid assets:

```bat
python scripts\host_paid_assets_vps.py --stage --upload --version 0.4.6 --force
```

## Honesty
- Catalog 0.4.6 filename alone is not proof of native Windows code freeze — prefer multihop PE rebuild on this host.
- Do not ship `*.priv` keys.
