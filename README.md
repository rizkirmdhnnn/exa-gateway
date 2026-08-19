# Exa Gateway for Hermes

A self-hosted Hermes plugin that adds Exa web search and page extraction through multiple API keys.

## Features

- Round-robin selection across Exa API keys.
- Retry with another key after Exa returns `402`, `429`, or transient `5xx` responses.
- Search and contents/extraction support.
- Hermes dashboard tab for adding, viewing usage, and removing keys.
- SQLite storage with restrictive file permissions.
- Stable account IDs based on database IDs.
- Backward-compatible reading of statistics from older releases.

## Install

Copy this directory to the Hermes user plugin directory:

```bash
cp -a exa-gateway ~/.hermes/plugins/exa-gateway
```

Do not copy a production `exa_gateway.db` into a repository. The database is created on first use.

Restart the Hermes dashboard or gateway after installing the plugin, according to your Hermes deployment setup.

## Configure

1. Open the Hermes dashboard.
2. Open the **Exa Gateway** tab.
3. Paste an Exa API key.
4. Click **Add key**.
5. Select `exa-gateway` as the Hermes web backend when search or extraction should use this provider.

The dashboard API relies on Hermes dashboard authentication. Do not expose an unauthenticated or insecure dashboard to a network that other people can reach.

## Storage and security

The default database path is:

```text
~/.hermes/plugins/exa-gateway/exa_gateway.db
```

Set `EXA_GATEWAY_DB_PATH` to use another local path. The plugin stores API keys in SQLite, so protect the database and its `-wal` and `-shm` files. `db.py` enforces mode `0600` after initialization.

The repository ignores runtime databases, Python bytecode, virtual environments, logs, and local files. Review staged files before publishing:

```bash
git add .
git diff --cached --stat
git diff --cached --name-only
git grep --cached -n -I -E 'sk-|EXA_API_KEY|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
```

Never publish a real API key. If a key was committed before, rotate it. Removing it from the latest tree is not enough because Git history can retain it.

## Plugin layout

- `__init__.py`: registers the provider.
- `provider.py`: round-robin search and extraction provider.
- `db.py`: SQLite storage and usage counters.
- `dashboard/plugin_api.py`: dashboard API routes.
- `dashboard/src/index.js`: readable dashboard source.
- `dashboard/dist/index.js`: runtime bundle loaded by Hermes.
- `dashboard/manifest.json`: dashboard tab metadata.
- `tests/`: local unit tests.

The dashboard uses the Hermes plugin SDK supplied by the dashboard. The runtime bundle is checked in beside its readable source.

## Tests

Run the tests without network access:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile db.py provider.py dashboard/plugin_api.py
```

Tests use a temporary database. They do not touch a production database.

## Limitations

- Exa account, API-key, and rate limits are controlled by Exa.
- The plugin does not create, rotate, or recover Exa accounts.
- Round-robin is process-local. Multiple Hermes processes each maintain their own cursor, while SQLite protects shared storage.
- Existing old statistics are mapped to the current key by matching the stored key prefix.

## Responsible use

Use keys only with accounts and services you are authorized to operate. Follow Exa's terms, rate limits, and API policies.

## Release checklist

- [ ] `exa_gateway.db` is absent from the repository.
- [ ] No API key, token, private email, internal IP, or local path is staged.
- [ ] `python3 -m unittest discover -s tests -v` passes.
- [ ] `python3 -m py_compile db.py provider.py dashboard/plugin_api.py` passes.
- [ ] Installation is tested in a clean Hermes profile.
- [ ] A license and version are present.
- [ ] The staged diff is reviewed before publishing.

No CI configuration is included by design.

## License

MIT. See `LICENSE`.

This is an independent Hermes plugin. It is not an official Exa or Hermes product.

Maintainer: `rizkirmdhn`

Support: open a GitHub issue with the Hermes version, plugin version, and redacted logs. Never include API keys.

Public repository URL: add it after publishing.
