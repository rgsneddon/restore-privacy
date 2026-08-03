> **On this site:** CERBERUS documentation mirrored from the public [CERBERUS README](https://github.com/rgsneddon/CERBERUS/blob/main/README.md). That GitHub file remains the source of truth.

# CERBERUS

**Private** residual-fleet oracle for Restore Privacy — Helsinki-style
collation of co-joined satellite heartbeats and honest fleet growth
parameters.

## Privacy contract

- **No user data observation retained.** Operational fleet signals only
  (capacity, co-join readiness, fleet surface counters without PII).
- **Forbidden keys are stripped** at the collate / learn boundary:
  connection logs, seed phrases / mnemonics, backup passphrases, backup file
  bytes, licence-acceptance prose, private keys.
- **No durable save of user secrets** — even encrypted. `strip_user_data` and
  `sanitize_stats_for_persist` drop fields; they do not encrypt-and-store.

## Package

```text
cerberus/
  oracle_master.py   # collate + Ned learn + strip
  cojoined_roles.py  # three-role residual stack helpers
tests/
  test_cerberus_privacy.py
```

## Quick test

```bash
python3 -m unittest discover -s tests -v
```

## Integration

Import pure helpers:

```python
from cerberus import collate_satellite_heartbeats, ned_learn_oracle, strip_user_data
```

Satellite payloads may include `host`, `cojoined`, `capacity`, `suite` /
`suite_architecture` / `suite_surfaces`. User-secret fields are ignored.

## License

Proprietary — Restore Privacy. Private repository; not for public redistribution
without authorization.
