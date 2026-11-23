"""SQLite storage. Only events are kept: no audio, video or images ever exist."""

import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      REAL NOT NULL,
    kind    TEXT NOT NULL,      -- see detector.py, plus game_* / alert_* / family_message
    device  TEXT,
    room    TEXT,
    value   REAL,
    meta    TEXT                -- JSON
);
CREATE INDEX IF NOT EXISTS events_ts ON events (ts);

CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL NOT NULL,
    kind        TEXT NOT NULL,   -- fall | bathroom_still | bathroom_long | sos
    level       TEXT NOT NULL,   -- urgent | warning
    device      TEXT,
    room        TEXT,
    title       TEXT,
    detail      TEXT,
    status      TEXT NOT NULL DEFAULT 'open',   -- open | acked | resolved
    acked_by    TEXT,
    acked_ts    REAL,
    resolved_ts REAL,
    last_sent   REAL,
    sends       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS family (
    user_id TEXT PRIMARY KEY,
    name    TEXT,
    added   REAL
);

CREATE TABLE IF NOT EXISTS plays (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        REAL NOT NULL,
    game_id   TEXT NOT NULL,
    source    TEXT NOT NULL,     -- ai | rules | family | elder
    sent_by   TEXT,              -- family member's name / LINE id
    status    TEXT NOT NULL DEFAULT 'offered',  -- offered | playing | done | skipped
    score     REAL,
    ended     REAL
);
"""


class Store:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.lock = threading.Lock()

    def _exec(self, sql: str, args=()) -> sqlite3.Cursor:
        with self.lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur

    def _all(self, sql: str, args=()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    # events
    def add_event(self, kind: str, device: str | None = None, room: str | None = None,
                  value: float | None = None, meta: dict | None = None, ts: float | None = None) -> None:
        self._exec("INSERT INTO events (ts, kind, device, room, value, meta) VALUES (?, ?, ?, ?, ?, ?)",
                   (ts or time.time(), kind, device, room, value, json.dumps(meta or {}, ensure_ascii=False)))

    def events(self, limit: int = 50) -> list[dict]:
        rows = self._all("SELECT * FROM events ORDER BY ts DESC, id DESC LIMIT ?", (limit,))
        for r in rows:
            r["meta"] = json.loads(r["meta"] or "{}")
        return rows

    def count_since(self, kind: str, since: float) -> int:
        return self._all("SELECT COUNT(*) AS n FROM events WHERE kind = ? AND ts >= ?", (kind, since))[0]["n"]

    # alerts
    def open_alert(self, kind, level, device, room, title, detail) -> dict:
        now = time.time()
        cur = self._exec(
            "INSERT INTO alerts (ts, kind, level, device, room, title, detail, last_sent, sends) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (now, kind, level, device, room, title, detail, now))
        return self.alert(cur.lastrowid)

    def alert(self, alert_id: int) -> dict | None:
        rows = self._all("SELECT * FROM alerts WHERE id = ?", (alert_id,))
        return rows[0] if rows else None

    def active_alerts(self) -> list[dict]:
        return self._all("SELECT * FROM alerts WHERE status != 'resolved' ORDER BY ts DESC")

    def recent_alerts(self, limit: int = 20) -> list[dict]:
        return self._all("SELECT * FROM alerts ORDER BY ts DESC LIMIT ?", (limit,))

    def ack_alert(self, alert_id: int, by: str) -> dict | None:
        self._exec("UPDATE alerts SET status = 'acked', acked_by = ?, acked_ts = ? WHERE id = ? AND status = 'open'",
                   (by, time.time(), alert_id))
        return self.alert(alert_id)

    def resolve_alert(self, alert_id: int) -> None:
        self._exec("UPDATE alerts SET status = 'resolved', resolved_ts = ? WHERE id = ?", (time.time(), alert_id))

    def mark_resent(self, alert_id: int) -> None:
        self._exec("UPDATE alerts SET last_sent = ?, sends = sends + 1 WHERE id = ?", (time.time(), alert_id))

    # family
    def add_family(self, user_id: str, name: str) -> None:
        self._exec("INSERT OR REPLACE INTO family (user_id, name, added) VALUES (?, ?, ?)", (user_id, name, time.time()))

    def remove_family(self, user_id: str) -> None:
        self._exec("DELETE FROM family WHERE user_id = ?", (user_id,))

    def family(self) -> list[dict]:
        return self._all("SELECT * FROM family ORDER BY added")

    def family_name(self, user_id: str) -> str | None:
        rows = self._all("SELECT name FROM family WHERE user_id = ?", (user_id,))
        return rows[0]["name"] if rows else None

    # games
    def add_play(self, game_id: str, source: str, sent_by: str | None = None) -> int:
        return self._exec("INSERT INTO plays (ts, game_id, source, sent_by) VALUES (?, ?, ?, ?)",
                          (time.time(), game_id, source, sent_by)).lastrowid

    def play(self, play_id: int) -> dict | None:
        rows = self._all("SELECT * FROM plays WHERE id = ?", (play_id,))
        return rows[0] if rows else None

    def update_play(self, play_id: int, status: str, score: float | None = None) -> None:
        ended = time.time() if status in ("done", "skipped") else None
        self._exec("UPDATE plays SET status = ?, score = COALESCE(?, score), ended = COALESCE(?, ended) WHERE id = ?",
                   (status, score, ended, play_id))

    def plays_since(self, since: float) -> list[dict]:
        return self._all("SELECT * FROM plays WHERE ts >= ? ORDER BY ts", (since,))
