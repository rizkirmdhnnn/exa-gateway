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
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    if DB_FILE.exists():
        os.chmod(DB_FILE, 0o600)
    con = _connect()
    try:
        con.executescript(_SCHEMA)
        con.commit()
    finally:
        con.close()
    # Apply restrictive permissions after SQLite creates the database too.
    if DB_FILE.exists():
        os.chmod(DB_FILE, 0o600)
    # SQLite creates sidecar files when WAL mode is active.
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{DB_FILE}{suffix}")
        if sidecar.exists():
            os.chmod(sidecar, 0o600)


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
    """Remove the key at list index (0-based), kept for compatibility."""
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


def remove_key_id(key_id: int) -> bool:
    """Remove one key by its immutable database ID."""
    init_db()
    con = _connect()
    try:
        result = con.execute("DELETE FROM keys WHERE id = ?", (key_id,))
        con.commit()
        return result.rowcount > 0
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
        stats = {r["account_id"]: dict(r) for r in rows}
        keys = con.execute("SELECT id, key FROM keys ORDER BY id").fetchall()
        by_prefix = {r["key"][:12]: f"key:{r['id']}" for r in keys}
        migrated: dict[str, dict] = {}
        for account_id, value in stats.items():
            # Older releases used "index:key-prefix". Keep those counters
            # attached to the same key after deletions or reordering.
            prefix = account_id.split(":", 1)[-1]
            canonical = by_prefix.get(prefix, account_id)
            current = migrated.setdefault(canonical, {
                "account_id": canonical,
                "requests": 0,
                "errors": 0,
                "last_error": "",
                "last_used": 0,
            })
            current["requests"] += value["requests"]
            current["errors"] += value["errors"]
            if value["last_used"] >= current["last_used"]:
                current["last_error"] = value["last_error"]
                current["last_used"] = value["last_used"]
        return migrated
    finally:
        con.close()
