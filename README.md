# Exa Gateway for Hermes

A self-hosted Hermes plugin for Exa web search and page extraction with multiple API keys.

> Independent community plugin. Not an official Exa or Hermes product.

## Features

- Round-robin requests across multiple Exa API keys.
- Retry with another key after `402`, `429`, or transient `5xx` responses.
- Exa search and page contents/extraction.
- Hermes dashboard tab for key management and usage statistics.
- Dashboard includes masked account health, enable/disable/test controls, parallel test-all with live progress, events, hourly activity, retention, safe settings, and event clearing.
- Local SQLite storage.
- Stable account IDs that survive key reordering or deletion.
- Compatible reading of statistics from older plugin versions.

## Requirements

- Hermes Agent `0.20.x` or later.
- An Exa API key.
- Hermes dashboard authentication enabled before exposing the dashboard beyond localhost.

## Install

Clone the repository, then copy it to the Hermes user plugin directory:

```bash
git clone https://github.com/rizkirmdhnnn/exa-gateway.git
cp -a exa-gateway ~/.hermes/plugins/exa-gateway
```

Restart the Hermes dashboard or gateway after installation. Use the restart method recommended by your Hermes setup.

The plugin creates its database on first use. Never copy a production `exa_gateway.db` into the repository.

## Configure

1. Open the Hermes dashboard.
2. Open the **Exa Gateway** tab.
3. Paste an Exa API key.
4. Click **Add account** and paste the key in the popup.
5. Set Hermes web search to `exa-gateway` when this provider should handle search and extraction.

On the Accounts tab, **Test all accounts** checks enabled accounts in parallel and shows live progress. The Events tab supports pruning old events and clearing all event history.

The plugin does not read an API key from the repository or from a checked-in configuration file. Keys are stored locally in SQLite.

## How it works

Each request reads the current key list and advances a process-local round-robin cursor. For example, with three keys the requests use key 1, key 2, key 3, then repeat.

When Exa returns `402`, `429`, or a transient `5xx` response, the provider retries once with the next key. Other errors are returned to the caller.

Usage statistics are stored per stable database key ID and shown in the dashboard. Statistics written by older versions using `index:key-prefix` IDs are mapped to the current key when read.

## Storage and security

The default database path is:

```text
~/.hermes/plugins/exa-gateway/exa_gateway.db
```

Set `EXA_GATEWAY_DB_PATH` to use another local path. The plugin stores API keys in SQLite. The database and SQLite WAL sidecar files are set to mode `0600` after initialization.

The dashboard API relies on Hermes dashboard authentication. Do not run Hermes with an unauthenticated or insecure dashboard on a network that other people can reach.

Dashboard event records contain operation, status, HTTP status, latency, and stable key ID only. Queries, URLs, headers, response bodies, and full API keys are not stored or exported. Events default to 30 days and 10,000 rows; retention can be changed within the safe dashboard bounds. Disabled keys remain stored but are skipped by provider round-robin selection.

If an API key was ever committed to Git, rotate it. Removing it from the latest commit is not enough because Git history can retain secrets.

See [SECURITY.md](SECURITY.md) for vulnerability reports and secret-handling rules.

## Plugin layout

- `__init__.py`: registers the web provider.
- `provider.py`: round-robin search and extraction provider.
- `db.py`: SQLite storage, permissions, and usage counters.
- `dashboard/plugin_api.py`: dashboard API routes.
- `dashboard/dist/index.js`: standalone dashboard bundle loaded by Hermes.
- `dashboard/manifest.json`: dashboard tab metadata.
- `tests/`: local unit tests.

The dashboard source is intentionally plain JavaScript using the Hermes dashboard SDK. No separate frontend toolchain is required for this plugin.

## Tests

Run locally without network access:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile db.py provider.py dashboard/plugin_api.py

# For API route tests, use the Hermes environment where FastAPI is installed:
~/.hermes/hermes-agent/venv/bin/python -m unittest discover -s tests -v
```

Tests use a temporary database and do not touch a production database.

## Limitations

- Exa controls account, API-key, quota, and rate limits.
- This plugin does not create, rotate, or recover Exa accounts.
- The round-robin cursor is process-local. SQLite protects shared key storage across processes, but separate Hermes processes have separate cursors.
- A fallback retry covers only the configured transient statuses.

## Responsible use

Use this plugin only with Exa accounts and API keys you are authorized to operate. Follow Exa's terms, rate limits, and API policies.

## License

MIT. See [LICENSE](LICENSE).

Maintainer: `rizkirmdhn`

Support: open a GitHub issue with the Hermes version, plugin version, and redacted logs. Never include API keys.

Repository: [github.com/rizkirmdhnnn/exa-gateway](https://github.com/rizkirmdhnnn/exa-gateway)
