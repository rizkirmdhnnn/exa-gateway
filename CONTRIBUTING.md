# Contributing

## Before opening a pull request

- Read `README.md` and `SECURITY.md`.
- Do not include API keys, local databases, private email addresses, internal IPs, or machine-specific paths.
- Keep changes focused.
- Add or update tests for behavior changes.
- Do not add CI workflows without discussing the maintenance cost first.

## Local checks

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile db.py provider.py dashboard/plugin_api.py
git diff --check
```

Tests must use a temporary database. Never run test code against a production `exa_gateway.db`.

## Dashboard changes

Keep `dashboard/src/dashboard.js` and `dashboard/dist/index.js` behaviorally aligned. The source file is the maintainable implementation; the `dist` file is the runtime bundle loaded by Hermes.

## Pull requests

Describe:

- What changed.
- Why it changed.
- How it was tested.
- Any Hermes version compatibility considerations.

Redact all credentials and private infrastructure details.
