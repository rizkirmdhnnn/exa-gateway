"""Local SQLite storage for Exa keys, usage statistics, health, and events."""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

DB_FILE = Path(os.environ.get("EXA_GATEWAY_DB_PATH", str(Path(__file__).resolve().parent / "exa_gateway.db")))
SCHEMA_VERSION = 2
KEY_COLUMNS = {
    "enabled": "INTEGER NOT NULL DEFAULT 1",
    "last_checked": "INTEGER NOT NULL DEFAULT 0",
    "last_status": "TEXT NOT NULL DEFAULT 'unknown'",
    "last_latency_ms": "INTEGER NOT NULL DEFAULT 0",
    "last_check_error": "TEXT NOT NULL DEFAULT ''",
}
_SCHEMA = """
CREATE TABLE IF NOT EXISTS keys (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS stats (account_id TEXT PRIMARY KEY, requests INTEGER NOT NULL DEFAULT 0, errors INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '', last_used INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at INTEGER NOT NULL, key_id INTEGER, operation TEXT NOT NULL, status TEXT NOT NULL, http_status INTEGER NOT NULL DEFAULT 0, latency_ms INTEGER NOT NULL DEFAULT 0, error_code TEXT NOT NULL DEFAULT '', FOREIGN KEY(key_id) REFERENCES keys(id) ON DELETE SET NULL);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_key_id ON events(key_id);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    return con

def migrate(con: sqlite3.Connection) -> None:
    con.executescript(_SCHEMA)
    columns = {r[1] for r in con.execute("PRAGMA table_info(keys)")}
    for name, definition in KEY_COLUMNS.items():
        if name not in columns:
            con.execute(f"ALTER TABLE keys ADD COLUMN {name} {definition}")
    con.executemany("INSERT OR IGNORE INTO settings(name, value) VALUES (?, ?)", [("retention_days", "30"), ("max_events", "10000")])
    con.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

def init_db() -> None:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    con = _connect()
    try:
        migrate(con)
        con.commit()
    finally:
        con.close()
    for path in (DB_FILE, Path(f"{DB_FILE}-wal"), Path(f"{DB_FILE}-shm")):
        if path.exists(): os.chmod(path, 0o600)

def list_keys() -> list[dict]:
    init_db(); con = _connect()
    try: return [dict(r) for r in con.execute("SELECT id,key,enabled,created_at FROM keys ORDER BY id")]
    finally: con.close()

def add_key(key: str) -> None:
    init_db(); con = _connect()
    try:
        con.execute("INSERT OR IGNORE INTO keys(key) VALUES (?)", (key,)); con.commit()
    finally: con.close()

def remove_key(index: int) -> bool:
    rows = list_keys()
    return remove_key_id(rows[index]["id"]) if 0 <= index < len(rows) else False

def remove_key_id(key_id: int) -> bool:
    init_db(); con = _connect()
    try:
        result = con.execute("DELETE FROM keys WHERE id=?", (key_id,)); con.commit(); return result.rowcount > 0
    finally: con.close()

def key_by_id(key_id: int) -> dict | None:
    init_db(); con = _connect()
    try:
        row = con.execute("SELECT id,key,enabled,created_at FROM keys WHERE id=?", (key_id,)).fetchone()
        return dict(row) if row else None
    finally: con.close()

def _mask(key: str) -> str:
    return f"{key[:12]}...{key[-4:]}" if len(key) > 16 else "***"

def set_key_enabled(key_id: int, enabled: bool) -> bool:
    init_db(); con = _connect()
    try:
        result = con.execute("UPDATE keys SET enabled=? WHERE id=?", (int(enabled), key_id)); con.commit(); return result.rowcount > 0
    finally: con.close()

def update_key_check(key_id: int, status: str, latency_ms: int, error: str = "") -> bool:
    init_db(); con = _connect()
    try:
        result = con.execute("UPDATE keys SET last_checked=?,last_status=?,last_latency_ms=?,last_check_error=? WHERE id=?", (int(time.time()), status[:40], max(0, int(latency_ms)), error[:200], key_id)); con.commit(); return result.rowcount > 0
    finally: con.close()

def list_key_summaries() -> list[dict]:
    init_db(); con = _connect()
    try:
        rows = con.execute("SELECT id,key,created_at,enabled,last_checked,last_status,last_latency_ms,last_check_error FROM keys ORDER BY id").fetchall()
        raw_stats = {r["account_id"]: dict(r) for r in con.execute("SELECT * FROM stats")}
        by_prefix = {r["key"][:12]: f"key:{r['id']}" for r in rows}
        stats = {}
        for account_id, value in raw_stats.items():
            canonical = by_prefix.get(account_id.split(":", 1)[-1], account_id)
            current = stats.setdefault(canonical, {"requests": 0, "errors": 0, "last_error": "", "last_used": 0})
            current["requests"] += value["requests"]
            current["errors"] += value["errors"]
            if value["last_used"] >= current["last_used"]:
                current["last_error"] = value["last_error"]
                current["last_used"] = value["last_used"]
        result = []
        for row in rows:
            item = {name: row[name] for name in row.keys() if name != "key"}
            item.update(stats.get(f"key:{row['id']}", {"requests": 0, "errors": 0, "last_error": "", "last_used": 0}))
            item["masked_key"] = _mask(row["key"])
            item["enabled"] = bool(row["enabled"])
            result.append(item)
        return result
    finally: con.close()

def bump_request(account_id: str) -> None:
    _bump(account_id, "requests", 1, int(time.time()))
def bump_error(account_id: str, message: str) -> None:
    init_db(); con = _connect()
    try:
        m = message[:200]; con.execute("INSERT INTO stats(account_id,errors,last_error) VALUES(?,?,?) ON CONFLICT(account_id) DO UPDATE SET errors=errors+1,last_error=?", (account_id,1,m,m)); con.commit()
    finally: con.close()
def _bump(account_id: str, field: str, amount: int, last_used: int) -> None:
    init_db(); con = _connect()
    try:
        con.execute("INSERT INTO stats(account_id,requests,last_used) VALUES(?,?,?) ON CONFLICT(account_id) DO UPDATE SET requests=requests+?,last_used=?", (account_id, amount, last_used, amount, last_used)); con.commit()
    finally: con.close()
def clear_error(account_id: str) -> None:
    init_db(); con = _connect()
    try: con.execute("UPDATE stats SET errors=0,last_error='' WHERE account_id=?", (account_id,)); con.commit()
    finally: con.close()
def get_stats() -> dict[str, dict]:
    init_db(); con = _connect()
    try:
        stats = {r["account_id"]: dict(r) for r in con.execute("SELECT * FROM stats")}; keys = con.execute("SELECT id,key FROM keys").fetchall(); by_prefix = {r["key"][:12]: f"key:{r['id']}" for r in keys}; out = {}
        for aid, val in stats.items():
            canonical = by_prefix.get(aid.split(":",1)[-1], aid); cur = out.setdefault(canonical, {"account_id":canonical,"requests":0,"errors":0,"last_error":"","last_used":0}); cur["requests"] += val["requests"]; cur["errors"] += val["errors"]
            if val["last_used"] >= cur["last_used"]: cur["last_error"],cur["last_used"] = val["last_error"],val["last_used"]
        return out
    finally: con.close()

def record_event(operation: str, status: str, key_id: int | None = None, http_status: int = 0, latency_ms: int = 0, error_code: str = "", created_at: int | None = None) -> int:
    init_db(); con = _connect()
    try:
        cur = con.execute("INSERT INTO events(created_at,key_id,operation,status,http_status,latency_ms,error_code) VALUES(?,?,?,?,?,?,?)", (created_at or int(time.time()), key_id, operation[:40], status[:40], int(http_status), max(0,int(latency_ms)), error_code[:120])); con.commit(); return int(cur.lastrowid)
    finally: con.close()

def recent_events(limit: int = 20, offset: int = 0, operation: str | None = None, status: str | None = None) -> list[dict]:
    limit = min(100, max(1,int(limit))); offset = max(0,int(offset)); init_db(); con = _connect()
    try:
        where=[]; args=[]
        if operation: where.append("operation=?"); args.append(operation)
        if status: where.append("status=?"); args.append(status)
        sql="SELECT id,created_at,key_id,operation,status,http_status,latency_ms,error_code FROM events" + ((" WHERE "+" AND ".join(where)) if where else "") + " ORDER BY id DESC LIMIT ? OFFSET ?"; args += [limit,offset]
        return [dict(r) for r in con.execute(sql,args)]
    finally: con.close()

def event_summary(since: int, until: int) -> dict:
    init_db(); con = _connect()
    try:
        rows=con.execute("SELECT COUNT(*) requests, SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) successful_requests, SUM(CASE WHEN status IN ('error','failed') THEN 1 ELSE 0 END) errors, SUM(CASE WHEN status='rate_limited' OR http_status=429 THEN 1 ELSE 0 END) rate_limits, COALESCE(AVG(latency_ms),0) average_latency_ms, MAX(created_at) last_activity FROM events WHERE created_at BETWEEN ? AND ?",(since,until)).fetchone(); d=dict(rows); d={k:(0 if v is None else v) for k,v in d.items()}; d["success_rate"]=round(d["successful_requests"]*100/d["requests"],2) if d["requests"] else 0.0; return d
    finally: con.close()

def hourly_activity(since: int, until: int) -> list[dict]:
    init_db(); con = _connect()
    try: return [dict(r) for r in con.execute("SELECT (created_at/3600)*3600 hour, COUNT(*) requests, SUM(CASE WHEN status IN ('error','failed') THEN 1 ELSE 0 END) errors, SUM(CASE WHEN status='rate_limited' OR http_status=429 THEN 1 ELSE 0 END) rate_limits FROM events WHERE created_at BETWEEN ? AND ? GROUP BY hour ORDER BY hour",(since,until))]
    finally: con.close()

def get_setting(name: str, default: str = "") -> str:
    init_db(); con = _connect()
    try:
        row=con.execute("SELECT value FROM settings WHERE name=?",(name,)).fetchone(); return row[0] if row else default
    finally: con.close()
def set_setting(name: str, value: str) -> None:
    init_db(); con = _connect()
    try: con.execute("INSERT INTO settings(name,value) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(name,str(value))); con.commit()
    finally: con.close()
def prune_events(retention_days: int, max_events: int) -> int:
    retention_days=max(1,int(retention_days)); max_events=max(100,int(max_events)); init_db(); con=_connect()
    try:
        cur=con.execute("DELETE FROM events WHERE created_at < ? OR id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT ?)",(int(time.time())-retention_days*86400,max_events)); con.commit(); return cur.rowcount
    finally: con.close()

def account_export(since: int) -> list[dict]:
    summaries=list_key_summaries(); return [{"account_id":f"key:{r['id']}","requests":r["requests"],"errors":r["errors"],"last_used":r["last_used"],"status":r["last_status"]} for r in summaries]

def _ensure_for_tests(): init_db()

auto_init = _ensure_for_tests
init_db()

# Backward-compatible alias used by older integrations.
SCHEMA = _SCHEMA
