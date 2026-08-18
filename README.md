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

## Hermes integration

Hermes uses a companion provider plugin (`plugins/web/exa-gateway` in the Hermes home) that calls this gateway over HTTP instead of the Exa SDK, so the gateway actually gets used. Configure:

```yaml
web:
  backend: exa-gateway
  extract_backend: exa-gateway
```

```bash
# in ~/.hermes/.env
EXA_GATEWAY_URL=http://<gateway-host>:8123
```

## Notes

- Free-tier Exa credits expire at month end (no rollover) — the gateway spreads usage but doesn't meter the $10 budget itself. Watch `/accounts` for usage.
- If all accounts are erroring, the gateway resets and tries the first key anyway (better than hard-failing).
