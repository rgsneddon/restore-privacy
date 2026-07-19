# Release packaging notes

## Current tag script

| Tag | Script |
|-----|--------|
| **0.2.0** | `scripts/build_release_0.2.0.py` |
| 0.1.8 | `scripts/build_release_0.1.8.py` (archive) |

Product node: **82.221.101.241:44044**. See `scripts/RELEASE_NOTES_0.2.0.md`.

Older `build_release_0.*.py` files are historical archives. Prefer copying the
**latest** script when starting a new version.

Shared gates every release must keep:

1. **`_assert_no_priv(OUT)`** on the release output directory.
2. Inject / provision **only** `node_elgamal.pub` — never `node_elgamal.priv`.
3. **Never force-add `secrets/`** to git.
4. **Linux wheels:** re-run `python scripts/package_linux.py` so manylinux **CPython 3.8–3.12** wheels stay current.

## Checklist (short)

```bash
# Bump VERSION / downloads catalog / installer VERSION first
python scripts/build_release_0.2.0.py
# Confirm releases/0.2.0/ has windows + linux (+ android/apple if built)
# gh release create 0.2.0 with those files
```
