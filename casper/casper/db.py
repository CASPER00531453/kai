"""Casper'ın hafızası: tek bir SQLite dosyası.

Tablolar:
- people:    kişiler (ad, ilişki, notlar, Casper'ın kişi kartı)
- aliases:   bir kişinin platformlardaki görünen adları
- messages:  içe aktarılan bütün mesajlar (+ FTS5 arama)
- analyses:  Casper'ın bir kişi hakkındaki yorumları
- chat:      Casper ile dertleşme geçmişi
- facts:     Casper'ın senin hakkında hatırladıkları
- watch:     gözcü modunun gördükleri ve yorumları
- summaries: gün sonu raporları
- settings:  ayarlar (anahtar/değer)
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any, Iterable

from . import paths

SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    relation TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    card TEXT DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS aliases (
    id INTEGER PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    platform TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    UNIQUE(person_id, platform, name)
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    chat TEXT NOT NULL DEFAULT '',
    sender TEXT NOT NULL,
    from_me INTEGER NOT NULL,
    ts REAL NOT NULL,
    text TEXT NOT NULL,
    UNIQUE(person_id, platform, chat, ts, sender, text)
);
CREATE INDEX IF NOT EXISTS messages_person_ts ON messages(person_id, ts);
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    text, content='messages', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    source TEXT NOT NULL,
    added INTEGER NOT NULL,
    ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    ts REAL NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chat (
    id INTEGER PRIMARY KEY,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS watch (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    app TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    person_id INTEGER,
    text TEXT NOT NULL DEFAULT '',
    comment TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS watch_ts ON watch(ts);
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    ts REAL NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULTS: dict[str, Any] = {
    "api_key": "",
    "model_chat": "claude-opus-5-5",
    "model_analysis": "claude-opus-5-5",
    "model_watch": "claude-opus-5-5",
    "my_names": [],
    "watch_interval": 3,
    "watch_cooldown": 20,
    "watch_apps": ["whatsapp", "instagram", "discord"],
    "watch_all_windows": False,
    "watch_overlay_screen": -1,
    "watch_blocklist": ["banka", "bank", "şifre", "password", "bitwarden", "1password", "keepass", "inprivate", "incognito", "gizli"],
    "daily_time": "23:30",
    "daily_auto": True,
}

_local = threading.local()
_lock = threading.RLock()


def connect() -> sqlite3.Connection:
    con = getattr(_local, "con", None)
    if con is None:
        con = sqlite3.connect(paths.db_path(), check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA journal_mode = WAL")
        con.executescript(SCHEMA)
        _local.con = con
    return con


def reset_connection() -> None:
    con = getattr(_local, "con", None)
    if con is not None:
        con.close()
        _local.con = None


def rows(sql: str, params: Iterable[Any] = ()) -> list[dict]:
    return [dict(r) for r in connect().execute(sql, tuple(params)).fetchall()]


def row(sql: str, params: Iterable[Any] = ()) -> dict | None:
    r = connect().execute(sql, tuple(params)).fetchone()
    return dict(r) if r else None


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    with _lock:
        con = connect()
        cur = con.execute(sql, tuple(params))
        con.commit()
        return cur.lastrowid or cur.rowcount


# --- ayarlar -----------------------------------------------------------------

def get_setting(key: str) -> Any:
    r = row("SELECT value FROM settings WHERE key = ?", (key,))
    if r is None:
        return DEFAULTS.get(key)
    try:
        return json.loads(r["value"])
    except ValueError:
        return r["value"]


def set_setting(key: str, value: Any) -> None:
    execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, json.dumps(value, ensure_ascii=False)),
    )


def all_settings() -> dict[str, Any]:
    out = dict(DEFAULTS)
    for r in rows("SELECT key, value FROM settings"):
        try:
            out[r["key"]] = json.loads(r["value"])
        except ValueError:
            out[r["key"]] = r["value"]
    return out


# --- kişiler -----------------------------------------------------------------

def create_person(name: str, relation: str = "", notes: str = "") -> int:
    now = time.time()
    pid = execute(
        "INSERT INTO people(name, relation, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (name.strip(), relation.strip(), notes.strip(), now, now),
    )
    add_alias(pid, "", name)
    return pid


def update_person(pid: int, **fields: Any) -> None:
    allowed = {k: v for k, v in fields.items() if k in {"name", "relation", "notes", "card"}}
    if not allowed:
        return
    sets = ", ".join(f"{k} = ?" for k in allowed)
    execute(f"UPDATE people SET {sets}, updated_at = ? WHERE id = ?", (*allowed.values(), time.time(), pid))


def delete_person(pid: int) -> None:
    execute("DELETE FROM people WHERE id = ?", (pid,))


def person(pid: int) -> dict | None:
    p = row("SELECT * FROM people WHERE id = ?", (pid,))
    if p:
        p["aliases"] = rows("SELECT platform, name FROM aliases WHERE person_id = ? ORDER BY platform, name", (pid,))
    return p


def people() -> list[dict]:
    return rows(
        """SELECT p.*, (SELECT COUNT(*) FROM messages m WHERE m.person_id = p.id) AS message_count,
                  (SELECT MAX(ts) FROM messages m WHERE m.person_id = p.id) AS last_ts
           FROM people p ORDER BY p.name COLLATE NOCASE"""
    )


def add_alias(pid: int, platform: str, name: str) -> None:
    name = (name or "").strip()
    if name:
        execute("INSERT OR IGNORE INTO aliases(person_id, platform, name) VALUES (?, ?, ?)", (pid, platform, name))


def set_aliases(pid: int, aliases: list[dict]) -> None:
    execute("DELETE FROM aliases WHERE person_id = ?", (pid,))
    for a in aliases:
        add_alias(pid, a.get("platform", ""), a.get("name", ""))


def all_aliases() -> list[dict]:
    return rows("SELECT a.person_id, a.platform, a.name, p.name AS person FROM aliases a JOIN people p ON p.id = a.person_id")


# --- mesajlar ----------------------------------------------------------------

def add_messages(pid: int, platform: str, chat: str, msgs: list[dict]) -> int:
    """msgs: {sender, from_me, ts, text}. Aynı mesaj iki kez girmez."""
    with _lock:
        con = connect()
        # rowcount sadece messages satırlarını sayar (FTS tetikleyicilerini değil).
        cur = con.executemany(
            "INSERT OR IGNORE INTO messages(person_id, platform, chat, sender, from_me, ts, text) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(pid, platform, chat, m["sender"], int(bool(m["from_me"])), float(m["ts"]), m["text"]) for m in msgs],
        )
        con.commit()
        return max(cur.rowcount, 0)


def messages_for(pid: int, since: float | None = None, limit: int | None = None) -> list[dict]:
    sql = "SELECT platform, chat, sender, from_me, ts, text FROM messages WHERE person_id = ?"
    params: list[Any] = [pid]
    if since is not None:
        sql += " AND ts >= ?"
        params.append(since)
    if limit:
        sql = f"SELECT * FROM ({sql} ORDER BY ts DESC LIMIT ?) ORDER BY ts"
        params.append(limit)
    else:
        sql += " ORDER BY ts"
    return rows(sql, params)


def delete_messages(pid: int, platform: str | None = None) -> None:
    if platform:
        execute("DELETE FROM messages WHERE person_id = ? AND platform = ?", (pid, platform))
    else:
        execute("DELETE FROM messages WHERE person_id = ?", (pid,))


def search_messages(query: str, pid: int | None = None, limit: int = 30) -> list[dict]:
    words = [w for w in "".join(c if c.isalnum() else " " for c in query).split() if len(w) > 2]
    if not words:
        return []
    match = " OR ".join(f'"{w}"' for w in words[:12])
    sql = """SELECT m.person_id, m.platform, m.sender, m.from_me, m.ts, m.text
             FROM messages_fts f JOIN messages m ON m.id = f.rowid
             WHERE messages_fts MATCH ?"""
    params: list[Any] = [match]
    if pid is not None:
        sql += " AND m.person_id = ?"
        params.append(pid)
    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)
    try:
        return rows(sql, params)
    except sqlite3.OperationalError:
        return []


def log_import(pid: int, platform: str, source: str, added: int) -> None:
    execute("INSERT INTO imports(person_id, platform, source, added, ts) VALUES (?, ?, ?, ?, ?)", (pid, platform, source, added, time.time()))


def imports_for(pid: int) -> list[dict]:
    return rows("SELECT platform, source, added, ts FROM imports WHERE person_id = ? ORDER BY ts DESC", (pid,))


# --- analiz, sohbet, hafıza, gözcü, özet -------------------------------------

def add_analysis(pid: int, text: str) -> None:
    execute("INSERT INTO analyses(person_id, ts, text) VALUES (?, ?, ?)", (pid, time.time(), text))


def analyses_for(pid: int, limit: int = 10) -> list[dict]:
    return rows("SELECT ts, text FROM analyses WHERE person_id = ? ORDER BY ts DESC LIMIT ?", (pid, limit))


def add_chat(role: str, content: str) -> None:
    execute("INSERT INTO chat(role, content, ts) VALUES (?, ?, ?)", (role, content, time.time()))


def recent_chat(limit: int = 40) -> list[dict]:
    return rows("SELECT * FROM (SELECT role, content, ts FROM chat ORDER BY id DESC LIMIT ?) ORDER BY ts", (limit,))


def clear_chat() -> None:
    execute("DELETE FROM chat")


def add_fact(text: str) -> None:
    text = text.strip()
    if text and not row("SELECT 1 FROM facts WHERE text = ?", (text,)):
        execute("INSERT INTO facts(text, ts) VALUES (?, ?)", (text, time.time()))


def facts() -> list[dict]:
    return rows("SELECT id, text, ts FROM facts ORDER BY ts")


def delete_fact(fid: int) -> None:
    execute("DELETE FROM facts WHERE id = ?", (fid,))


def add_watch(app: str, title: str, person_id: int | None, text: str, comment: str = "") -> int:
    return execute(
        "INSERT INTO watch(ts, app, title, person_id, text, comment) VALUES (?, ?, ?, ?, ?, ?)",
        (time.time(), app, title, person_id, text, comment),
    )


def set_watch_comment(wid: int, comment: str) -> None:
    execute("UPDATE watch SET comment = ? WHERE id = ?", (comment, wid))


def watch_between(start: float, end: float) -> list[dict]:
    return rows("SELECT * FROM watch WHERE ts >= ? AND ts < ? ORDER BY ts", (start, end))


def add_summary(day: str, text: str) -> None:
    execute("INSERT INTO summaries(day, ts, text) VALUES (?, ?, ?)", (day, time.time(), text))


def summaries(limit: int = 30) -> list[dict]:
    return rows("SELECT day, ts, text FROM summaries ORDER BY ts DESC LIMIT ?", (limit,))


def wipe_everything() -> None:
    with _lock:
        con = connect()
        for table in ("messages", "imports", "analyses", "aliases", "people", "chat", "facts", "watch", "summaries"):
            con.execute(f"DELETE FROM {table}")
        con.execute("INSERT INTO messages_fts(messages_fts) VALUES ('rebuild')")
        con.commit()
        con.execute("VACUUM")
