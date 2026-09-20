import os
import time
import threading
import logging
import psycopg2
import psycopg2.extras
from psycopg2.extras import Json
from datetime import datetime
from chronos.core.audit_spool import AuditSpool

class PersistenceLayer:
    def __init__(self):
        self.host = os.environ.get("POSTGRES_HOST", "localhost")
        self.user = os.environ.get("POSTGRES_USER", "chronos")
        self.password = os.environ.get("POSTGRES_PASSWORD", "chronos_dev_password")
        self.dbname = os.environ.get("POSTGRES_DB", "chronos")
        self.conn = None
        self.spool = AuditSpool(os.environ.get('CHRONOS_AUDIT_SPOOL', '/var/lib/chronos/audit.sqlite3'))
        self.worker_thread = None
        self.running = False

    def connect(self):
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                dbname=self.dbname,
                connect_timeout=5
            )
            print("Connected to PostgreSQL persistence layer.")
            self._init_schema()
            
            if not self.running:
                self.running = True
                self.worker_thread = threading.Thread(target=self._audit_worker, daemon=True)
                self.worker_thread.start()
                print("Audit worker thread started.")
        except Exception as e:
            raise RuntimeError('PostgreSQL audit storage is required at startup') from e

    def _init_schema(self):
        """Initialize the basic schema if needed"""
        if not self.conn: return
        
        with self.conn.cursor() as cur:
            # Session Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id UUID PRIMARY KEY,
                    attacker_ip INET NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    metadata JSONB
                );
            """)
            
            # Audit Log
            cur.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id BIGSERIAL PRIMARY KEY,
                    session_id UUID,
                    timestamp TIMESTAMP NOT NULL,
                    operation VARCHAR(50),
                    path TEXT,
                    inode BIGINT,
                    metadata JSONB
                );
            """)
            
            # Session Evidence
            cur.execute("""
                CREATE TABLE IF NOT EXISTS session_evidence (
                    session_id UUID PRIMARY KEY,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    duration_seconds INT,
                    detection_status VARCHAR(50),
                    detection_confidence FLOAT,
                    exit_reason VARCHAR(50),
                    first_suspicious_command TEXT,
                    last_successful_interaction TIMESTAMP,
                    commands JSONB,
                    visited_files JSONB,
                    traversal_graph JSONB,
                    skill_assessment JSONB
                );
            """)
            self.conn.commit()

        with self.conn.cursor() as cur:
            cur.execute('ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS event_id UUID')
            cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS audit_event_id ON audit_log(event_id)')
            cur.execute('ALTER TABLE session_evidence ADD COLUMN IF NOT EXISTS last_event_id BIGINT NOT NULL DEFAULT 0')
            cur.execute('CREATE TABLE IF NOT EXISTS evidence_progress (session_id UUID PRIMARY KEY, last_event_id BIGINT NOT NULL, payload JSONB NOT NULL)')
        self.conn.commit()

    def _audit_worker(self):
        """Replay durable outbox; UUIDs fence uncertain commit retries."""
        while self.running:
            batch = self.spool.pending()
            if not batch:
                time.sleep(0.1)
                continue
            try:
                if self.conn is None or self.conn.closed:
                    self.conn = psycopg2.connect(host=self.host, user=self.user,
                        password=self.password, dbname=self.dbname, connect_timeout=5)
                with self.conn.cursor() as cur:
                    psycopg2.extras.execute_batch(cur, """
                        INSERT INTO audit_log (event_id, session_id, timestamp, operation, path, inode, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (event_id) DO NOTHING
                    """, [(eid, *payload[:5], Json(payload[5])) for eid, payload in batch])
                self.conn.commit()
                self.spool.acknowledge([eid for eid, _ in batch])
            except Exception:
                logging.exception("Audit delivery failed; durable events retained")
                if self.conn:
                    self.conn.close()
                self.conn = None
                time.sleep(1)

    def log_operation(self, session_id, operation, path, inode, metadata=None):
        """Durably admit before returning; storage failures reach the caller."""
        if not session_id:
            return
        self.spool.append((session_id, datetime.utcnow().isoformat(), operation,
                           path, inode,
                           {k: v for k, v in (metadata or {}).items()
                            if k.lower() != 'password'}))

    def close(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=10)
            if self.worker_thread.is_alive():
                return
        if self.conn:
            self.conn.close()
        self.spool.close()

    def flush_evidence(self, session_id: str, evidence_data: dict):
        if not self.conn:
            return False
        conn = None
        try:
            # Evidence commits must not race the audit worker on a shared transaction.
            conn = psycopg2.connect(host=self.host, user=self.user, password=self.password,
                                    dbname=self.dbname, connect_timeout=5)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO session_evidence (
                        session_id, start_time, end_time, duration_seconds, 
                        detection_status, detection_confidence, exit_reason, 
                        first_suspicious_command, last_successful_interaction, 
                        commands, visited_files, traversal_graph, skill_assessment, last_event_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (session_id) DO UPDATE SET
                        end_time = EXCLUDED.end_time,
                        duration_seconds = EXCLUDED.duration_seconds,
                        detection_status = EXCLUDED.detection_status,
                        detection_confidence = EXCLUDED.detection_confidence,
                        exit_reason = EXCLUDED.exit_reason,
                        first_suspicious_command = EXCLUDED.first_suspicious_command,
                        last_successful_interaction = EXCLUDED.last_successful_interaction,
                        commands = EXCLUDED.commands,
                        visited_files = EXCLUDED.visited_files,
                        traversal_graph = EXCLUDED.traversal_graph,
                        skill_assessment = EXCLUDED.skill_assessment,
                        last_event_id = EXCLUDED.last_event_id
                    WHERE session_evidence.last_event_id < EXCLUDED.last_event_id
                """, (
                    session_id,
                    evidence_data.get('start_time'),
                    evidence_data.get('end_time'),
                    evidence_data.get('duration_seconds'),
                    evidence_data.get('detection_status'),
                    evidence_data.get('detection_confidence'),
                    evidence_data.get('exit_reason'),
                    evidence_data.get('first_suspicious_command'),
                    evidence_data.get('last_successful_interaction'),
                    Json(evidence_data.get('commands', [])),
                    Json(evidence_data.get('visited_files', [])),
                    Json(evidence_data.get('traversal_graph', {})),
                    Json(evidence_data.get('skill_assessment')),
                    evidence_data.get('last_event_id', 0)
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Failed to flush evidence: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def load_evidence_progress(self, session_id):
        conn = psycopg2.connect(host=self.host, user=self.user, password=self.password,
                               dbname=self.dbname, connect_timeout=5,
                               options='-c statement_timeout=5000')
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT payload FROM evidence_progress WHERE session_id=%s', (session_id,))
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            conn.close()

    def save_evidence_progress(self, session_id, data):
        conn = psycopg2.connect(host=self.host, user=self.user, password=self.password,
                               dbname=self.dbname, connect_timeout=5,
                               options='-c statement_timeout=5000')
        try:
            with conn.cursor() as cur:
                cur.execute('''INSERT INTO evidence_progress VALUES (%s, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE SET
                    last_event_id=EXCLUDED.last_event_id, payload=EXCLUDED.payload
                    WHERE evidence_progress.last_event_id < EXCLUDED.last_event_id''',
                    (session_id, data.get('last_event_id', 0), Json(data)))
            conn.commit()
        finally:
            conn.close()
