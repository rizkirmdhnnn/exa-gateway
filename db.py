"""Shared SQLite storage for the Exa Gateway plugin.

Both the web provider (gateway process) and the dashboard backend
(dashboard process) use this module — SQLite gives us atomic writes and
built-in locking so the two processes never corrupt each other's data.

Tables:
    keys   — Exa API keys (one per row)
    stats  — per-account usage counters
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

# Allow override so the standalone server can share the plugin's DB.
DB_FILE = Path(os.environ.get("EXA_GATEWAY_DB_PATH", str(Path(__file__).resolve().parent / "exa_gateway.db")))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS stats (
    account_id TEXT PRIMARY KEY,
    requests INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    last_used INTEGER NOT NULL DEFAULT 0
);
"""


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db() -> None:
    con = _connect()
    try:
        con.executescript(_SCHEMA)
        con.commit()
    finally:
        con.close()


# ── keys ──────────────────────────────────────────────────────────────

def list_keys() -> list[dict]:
    init_db()
    con = _connect()
    try:
        rows = con.execute("SELECT id, key FROM keys ORDER BY id").fetchall()
        return [{"id": r["id"], "key": r["key"]} for r in rows]
    finally:
        con.close()


def add_key(key: str) -> None:
    init_db()
    con = _connect()
    try:
        con.execute("INSERT OR IGNORE INTO keys (key) VALUES (?)", (key,))
        con.commit()
    finally:
        con.close()


def remove_key(index: int) -> bool:
    """Remove the key at list index (0-based) — matches dashboard display."""
    init_db()
    con = _connect()
    try:
        rows = con.execute("SELECT id FROM keys ORDER BY id").fetchall()
        if 0 <= index < len(rows):
            con.execute("DELETE FROM keys WHERE id = ?", (rows[index]["id"],))
            con.commit()
            return True
        return False
    finally:
        con.close()


# ── stats ─────────────────────────────────────────────────────────────

def bump_request(account_id: str) -> None:
    init_db()
    con = _connect()
    try:
        con.execute(
            """INSERT INTO stats (account_id, requests, last_used)
               VALUES (?, 1, ?)
               ON CONFLICT(account_id) DO UPDATE SET
                 requests = requests + 1, last_used = ?""",
            (account_id, int(time.time()), int(time.time())),
        )
        con.commit()
    finally:
        con.close()


def bump_error(account_id: str, message: str) -> None:
    init_db()
    con = _connect()
    try:
        con.execute(
            """INSERT INTO stats (account_id, errors, last_error)
               VALUES (?, 1, ?)
               ON CONFLICT(account_id) DO UPDATE SET
                 errors = errors + 1, last_error = ?""",
            (account_id, message[:200], message[:200]),
        )
        con.commit()
    finally:
        con.close()


def clear_error(account_id: str) -> None:
    init_db()
    con = _connect()
    try:
        con.execute("UPDATE stats SET errors = 0, last_error = '' WHERE account_id = ?", (account_id,))
        con.commit()
    finally:
        con.close()


def get_stats() -> dict[str, dict]:
    init_db()
    con = _connect()
    try:
        rows = con.execute("SELECT * FROM stats").fetchall()
        return {r["account_id"]: dict(r) for r in rows}
    finally:
        con.close()
