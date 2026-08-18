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

The repo ships **two Hermes plugins** — together they make the gateway
fully in-process: no separate container or server required.

### 1. Web provider — `hermes-plugin/web/exa-gw`

Round-robins across keys **inside the Hermes gateway process** and calls
Exa directly. Keys are read from `keys.json` next to the provider.

```bash
cp -r hermes-plugin/web/exa-gw ~/.hermes/plugins/web/exa-gw
hermes plugins enable web/exa-gw
hermes config set web.backend exa-gateway
hermes config set web.extract_backend exa-gateway
```

### 2. Dashboard tab — `hermes-plugin/exa-gateway`

Adds an **"Exa Gateway" tab** to the Hermes dashboard: paste API keys,
remove them, and watch per-account usage (requests / errors). Keys and
stats are shared with the provider via `keys.json` + `stats.json`.

```bash
cp -r hermes-plugin/exa-gateway ~/.hermes/plugins/exa-gateway
hermes plugins enable exa-gateway
# restart dashboard; tab appears under Plugins
```

### Key files

| File | Written by | Read by |
|---|---|---|
| `~/.hermes/plugins/web/exa-gw/keys.json` | dashboard (add/remove key) | provider (round-robin) |
| `~/.hermes/plugins/web/exa-gw/stats.json` | provider (per request) | dashboard (display) |

### Repo layout

```
exa-gateway/
├── main.py                    # (standalone server — optional if you want a
│                              #  container instead of the in-process plugin)
├── Dockerfile
├── requirements.txt
└── hermes-plugin/
    ├── web/
    │   └── exa-gw/            # WebSearchProvider (in-process round-robin)
    │       ├── plugin.yaml
    │       ├── provider.py
    │       └── __init__.py
    └── exa-gateway/           # Dashboard tab (keys + stats)
        ├── plugin.yaml
        └── dashboard/
            ├── manifest.json
            ├── plugin_api.py
            └── dist/index.js
```

## Notes

- Free-tier Exa credits expire at month end (no rollover) — the gateway spreads usage but doesn't meter the $10 budget itself. Watch `/accounts` for usage.
- If all accounts are erroring, the gateway resets and tries the first key anyway (better than hard-failing).
