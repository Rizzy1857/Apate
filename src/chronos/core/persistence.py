import os
import time
import queue
import threading
import psycopg2
import psycopg2.extras
from psycopg2.extras import Json
from datetime import datetime

class PersistenceLayer:
    def __init__(self):
        self.host = os.environ.get("POSTGRES_HOST", "localhost")
        self.user = os.environ.get("POSTGRES_USER", "chronos")
        self.password = os.environ.get("POSTGRES_PASSWORD", "chronos_dev_password")
        self.dbname = os.environ.get("POSTGRES_DB", "chronos")
        self.conn = None
        self.audit_queue = queue.Queue()
        self.worker_thread = None
        self.running = False

    def connect(self):
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                dbname=self.dbname
            )
            print("Connected to PostgreSQL persistence layer.")
            self._init_schema()
            
            if not self.running:
                self.running = True
                self.worker_thread = threading.Thread(target=self._audit_worker, daemon=True)
                self.worker_thread.start()
                print("Audit worker thread started.")
        except Exception as e:
            print(f"Failed to connect to PostgreSQL: {e}")

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

    def _audit_worker(self):
        """Background thread to process audit logs in batches"""
        while self.running:
            batch = []
            try:
                item = self.audit_queue.get(timeout=1.0)
                batch.append(item)
                while len(batch) < 100:
                    try:
                        item = self.audit_queue.get_nowait()
                        batch.append(item)
                    except queue.Empty:
                        break
            except queue.Empty:
                pass
                
            if batch and self.conn:
                try:
                    with self.conn.cursor() as cur:
                        psycopg2.extras.execute_batch(
                            cur,
                            """
                            INSERT INTO audit_log (session_id, timestamp, operation, path, inode, metadata)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            batch
                        )
                    self.conn.commit()
                except Exception as e:
                    print(f"Failed to batch insert audit logs: {e}")
                    self.conn.rollback()
                finally:
                    for _ in batch:
                        self.audit_queue.task_done()

    def log_operation(self, session_id: str, operation: str, path: str, inode: int, metadata: dict = {}):
        """Queue an operation for background logging (non-blocking)"""
        if not session_id:
            return
            
        self.audit_queue.put((
            session_id,
            datetime.utcnow(),
            operation,
            path,
            inode,
            Json(metadata)
        ))

    def flush_evidence(self, session_id: str, evidence_data: dict):
        if not self.conn: return
        
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO session_evidence (
                        session_id, start_time, end_time, duration_seconds, 
                        detection_status, detection_confidence, exit_reason, 
                        first_suspicious_command, last_successful_interaction, 
                        commands, visited_files, traversal_graph, skill_assessment
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
                        skill_assessment = EXCLUDED.skill_assessment
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
                    Json(evidence_data.get('skill_assessment'))
                ))
                self.conn.commit()
        except Exception as e:
            print(f"Failed to flush evidence: {e}")
            self.conn.rollback()
