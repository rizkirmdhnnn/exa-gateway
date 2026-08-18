# Exa Gateway

Multi-account Exa API proxy with round-robin. One endpoint, N Exa API keys — Hermes (or anything else) just points at the gateway and gets Exa search + extract with automatic failover across accounts.

## Why

Exa gives ~$10/month free credits per account. With 10 accounts that's ~$100/month of free search/extract. This gateway spreads requests across those accounts and skips any that hit rate limits or errors — so one stable endpoint uses them all.

## Architecture

```
Client (Hermes, curl, anything)
        │  POST /search, /contents
        ▼
Exa Gateway (FastAPI, port 8123)
        │  round-robin + skip broken accounts
        ▼
api.exa.ai  (account 1..10, one API key each)
```

## Features

- **Round-robin** — requests cycle through configured keys
- **Failover** — accounts returning 402/429/5xx are skipped for the next request (after 5 consecutive errors the account is quarantined until all are down, then it resets)
- **Health tracking** — per-account request count, error count, last error, last used
- **Transparent** — request/response bodies are passed through unchanged (mirrors the Exa API exactly)
- **Zero config keys needed at runtime** — keys come from env

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/search` | Proxy to `api.exa.ai/search` |
| POST | `/contents` | Proxy to `api.exa.ai/contents` |
| GET | `/health` | Account count + per-account status |
| GET | `/accounts` | Per-account usage/error details |

## Configuration

Environment variables:

```
# Option 1: comma-separated
EXA_API_KEYS=key1,key2,key3,...

# Option 2: numbered (up to N)
EXA_KEY_1=key1
EXA_KEY_2=key2
...

# Optional: port
PORT=8123
```

## Run locally

```bash
pip install -r requirements.txt
EXA_KEY_1=your_key uvicorn main:app --host 0.0.0.0 --port 8123
```

## Run with Docker

```bash
docker build -t exa-gateway .
docker run -d --name exa-gateway -p 8123:8123 \
  -e EXA_KEY_1=key1 -e EXA_KEY_2=key2 ... \
  exa-gateway
```

## All-in-one Hermes plugin (no container needed)

**One plugin** — `hermes-plugin/exa-gateway` — provides both the web
search/extract provider AND the dashboard tab. No separate container or
server required.

```
~/.hermes/plugins/exa-gateway/
├── plugin.yaml          # kind: backend + provides_web_providers
├── __init__.py          # register() → register_web_search_provider
├── provider.py          # WebSearchProvider (in-process round-robin)
├── db.py                # shared SQLite storage (keys + stats)
├── exa_gateway.db       # SQLite database (created at runtime)
└── dashboard/           # "Exa Gateway" tab (keys + stats UI)
    ├── manifest.json
    ├── plugin_api.py
    └── dist/index.js
```

Storage is **SQLite** (`exa_gateway.db`) — atomic writes, built-in locking,
safe when the gateway process (provider) and dashboard process both touch
it. Keys and stats are shared between them via the same db.

### Install

```bash
# copy the single plugin into your Hermes home
cp -r hermes-plugin/exa-gateway ~/.hermes/plugins/exa-gateway

# enable it
hermes plugins enable exa-gateway

# point web search/extract at it
hermes config set web.backend exa-gateway
hermes config set web.extract_backend exa-gateway

# restart gateway (new session) and dashboard
```

### Usage

1. Open the Hermes dashboard → **Exa Gateway** tab.
2. Paste one or more Exa API keys → they land in the SQLite db.
3. Search/extract now round-robins across the keys automatically.
4. The tab shows per-account requests / errors live.

### Standalone server (optional)

`main.py` + `Dockerfile` are kept as an optional container alternative —
run the round-robin as its own service and point `EXA_GATEWAY_URL` at it.
Most users will prefer the in-process plugin above.

## Notes

- Free-tier Exa credits expire at month end (no rollover) — the gateway spreads usage but doesn't meter the $10 budget itself. Watch `/accounts` for usage.
- If all accounts are erroring, the gateway resets and tries the first key anyway (better than hard-failing).
