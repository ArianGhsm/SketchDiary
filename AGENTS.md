# Agent Instructions (Required)

This repository is **Inline-First Telegram UX**.

## Mandatory Rules

1. Do not implement command-centric navigation.
2. Start new user features from inline callbacks.
3. Keep text input only for data-entry steps.
4. Always keep inline back/cancel/home actions in user flows.
5. Keep operational data under `data/` and do not scatter DB files.
6. Enforce Auth-First: do not expose full user capabilities before verification.

## Documentation Update Rule (Hard Requirement)

When code changes, documentation must also change in the same update.

At minimum, update:
- `README.md`
- `requirements.txt` (if imports/dependencies changed)

Update also if relevant:
- `ARCHITECTURE_FA.md`
- `INLINE_UX_POLICY_FA.md`
- `CONTRIBUTING_FA.md`

Any code change without README update is considered incomplete.
Any dependency/import change without requirements update is considered incomplete.

## Local Gate

Use local git hook path:

```bash
git config core.hooksPath .githooks
```

Hook checker:
- `tools/check_readme_sync.py`
