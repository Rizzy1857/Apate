"""Crash-durable bounded outbox; only acknowledged PostgreSQL rows are removed."""
import json
import os
import sqlite3
import threading
import uuid


class AuditSpool:
    def __init__(self, path, max_events=100000):
        os.makedirs(os.path.dirname(os.path.abspath(path)), mode=0o700, exist_ok=True)
        self.lock = threading.Lock()
        self.limit = max_events
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=5)
        os.chmod(path, 0o600)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA max_page_count=65536')  # 256 MiB at SQLite's 4 KiB default.
        self.db.execute('CREATE TABLE IF NOT EXISTS outbox (sequence INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL)')
        self.db.commit()

    def append(self, payload, event_id=None):
        encoded = json.dumps(payload, separators=(',', ':'))
        if len(encoded.encode()) > 65536:
            raise RuntimeError('Audit event exceeds 64 KiB')
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            event_id = str(uuid.UUID(event_id)) if event_id else str(uuid.uuid4())
            existing = self.db.execute(
                'SELECT payload FROM outbox WHERE event_id=?', (event_id,)
            ).fetchone()
            if existing:
                if existing[0] != encoded:
                    raise RuntimeError('Conflicting audit payload for deterministic event ID')
                return event_id
            if self.db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0] >= self.limit:
                raise RuntimeError('Audit storage full; refusing unaudited operation')
            self.db.execute('INSERT INTO outbox(event_id, payload) VALUES (?, ?)', (event_id, encoded))
        return event_id

    def pending(self, limit=100):
        with self.lock:
            return [(row[0], json.loads(row[1])) for row in self.db.execute(
                'SELECT event_id, payload FROM outbox ORDER BY sequence LIMIT ?', (limit,))]

    def acknowledge(self, ids):
        with self.lock, self.db:
            self.db.executemany('DELETE FROM outbox WHERE event_id=?', [(i,) for i in ids])

    def close(self):
        with self.lock:
            self.db.close()
