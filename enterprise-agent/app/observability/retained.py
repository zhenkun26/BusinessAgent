"""Single-host retained outboxes. No filesystem or row deletion, including acknowledgements."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Iterator
import uuid


class RetainedStore:
    def __init__(self, path: str, connection: Any = None) -> None:
        self.path = path
        self.connection = connection  # Injected memory connection for offline verification only.

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        own = self.connection is None
        if own:
            path = Path(self.path)
            if any(p.is_symlink() for p in (path, *path.parents)):
                raise ValueError('OBSERVABILITY_PATH_REJECTED')
            path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(path, timeout=2, isolation_level=None)
        else:
            db = self.connection
        try:
            mode = db.execute('PRAGMA journal_mode=PERSIST').fetchone()[0]
            if mode != ('persist' if own else 'memory'):
                raise RuntimeError('OBSERVABILITY_JOURNAL_REJECTED')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('PRAGMA temp_store=MEMORY')
            db.execute('PRAGMA busy_timeout=2000')
            db.execute('''CREATE TABLE IF NOT EXISTS retained_events (
                seq INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE,
                channel TEXT NOT NULL, body TEXT NOT NULL, created REAL NOT NULL,
                acknowledged REAL, attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt REAL NOT NULL DEFAULT 0)''')
            db.execute('''CREATE INDEX IF NOT EXISTS retained_pending
                ON retained_events(channel, acknowledged, next_attempt, seq)''')
            db.execute('''CREATE TABLE IF NOT EXISTS observed_conditions (
                name TEXT PRIMARY KEY, failing INTEGER NOT NULL, updated REAL NOT NULL)''')
            yield db
        finally:
            if own:
                db.close()

    def append(self, channel: str, event_id: str, body: dict[str, Any]) -> None:
        if channel not in {'audit', 'alert', 'receipt'}:
            raise ValueError('OBSERVABILITY_CHANNEL_REJECTED')
        encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        if len(encoded.encode()) > 262144:
            raise ValueError('OBSERVABILITY_RECORD_TOO_LARGE')
        with self.connect() as db:
            db.execute('INSERT INTO retained_events(event_id,channel,body,created) VALUES(?,?,?,?) '
                       'ON CONFLICT(event_id) DO NOTHING', (event_id, channel, encoded, time.time()))
            stored = db.execute('SELECT channel,body FROM retained_events WHERE event_id=?',
                                (event_id,)).fetchone()
            if stored != (channel, encoded):
                raise ValueError('OBSERVABILITY_ID_CONFLICT')

    def pending(self, channel: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute('''SELECT event_id,body FROM retained_events
                WHERE channel=? AND acknowledged IS NULL AND next_attempt<=?
                ORDER BY next_attempt,seq LIMIT ?''',
                (channel, time.time(), min(max(limit, 1), 100))).fetchall()
        return [{'event_id': row[0], 'body': json.loads(row[1])} for row in rows]

    def acknowledge(self, event_id: str) -> None:
        with self.connect() as db:
            db.execute('UPDATE retained_events SET acknowledged=COALESCE(acknowledged,?) '
                       'WHERE event_id=?', (time.time(), event_id))

    def defer(self, event_id: str) -> None:
        with self.connect() as db:
            db.execute('UPDATE retained_events SET attempts=attempts+1,next_attempt=? '
                       'WHERE event_id=? AND acknowledged IS NULL', (time.time()+30, event_id))

    def stats(self, channel: str = 'audit') -> dict[str, Any]:
        with self.connect() as db:
            db.execute("INSERT INTO observed_conditions VALUES('__retention_probe',0,?) "
                       'ON CONFLICT(name) DO UPDATE SET updated=excluded.updated', (time.time(),))
            row = db.execute('SELECT COUNT(*),MIN(created) FROM retained_events '
                             'WHERE channel=? AND acknowledged IS NULL', (channel,)).fetchone()
        return {'pending': row[0], 'oldest_seconds': max(0, time.time()-row[1]) if row[1] else 0}

    def observe(self, name: str, failing: bool) -> None:
        """Atomically retain each condition transition; initial healthy is a baseline, not recovery."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                prior = db.execute('SELECT failing FROM observed_conditions WHERE name=?',
                                   (name,)).fetchone()
                if prior is None or bool(prior[0]) != failing:
                    if failing or prior is not None:
                        event_id = str(uuid.uuid4())
                        body = {'event_id': event_id, 'condition': name,
                                'state': 'firing' if failing else 'resolved'}
                        db.execute('INSERT INTO retained_events(event_id,channel,body,created) '
                                   "VALUES(?,'alert',?,?)", (event_id, json.dumps(body), time.time()))
                    db.execute('INSERT INTO observed_conditions VALUES(?,?,?) ON CONFLICT(name) '
                               'DO UPDATE SET failing=excluded.failing,updated=excluded.updated',
                               (name, int(failing), time.time()))
                db.commit()
            except BaseException:
                db.rollback()
                raise
