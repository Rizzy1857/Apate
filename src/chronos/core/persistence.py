import os
import psycopg2
from psycopg2.extras import Json
from datetime import datetime

class PersistenceLayer:
    def __init__(self):
        self.host = os.environ.get("POSTGRES_HOST", "localhost")
        self.user = os.environ.get("POSTGRES_USER", "chronos")
        self.password = os.environ.get("POSTGRES_PASSWORD", "chronos_dev_password")
        self.dbname = os.environ.get("POSTGRES_DB", "chronos")
        self.conn = None

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
                    traversal_graph JSONB
                );
            """)
            self.conn.commit()

    def log_operation(self, session_id: str, operation: str, path: str, inode: int, metadata: dict = {}):
        if not self.conn: return
        
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO audit_log (session_id, timestamp, operation, path, inode, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (session_id, datetime.utcnow(), operation, path, inode, Json(metadata)))
                self.conn.commit()
        except Exception as e:
            print(f"Failed to log operation: {e}")
            self.conn.rollback()

    def flush_evidence(self, session_id: str, evidence_data: dict):
        if not self.conn: return
        
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO session_evidence (
                        session_id, start_time, end_time, duration_seconds, 
                        detection_status, detection_confidence, exit_reason, 
                        first_suspicious_command, last_successful_interaction, 
                        commands, visited_files, traversal_graph
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
                        traversal_graph = EXCLUDED.traversal_graph
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
                    Json(evidence_data.get('traversal_graph', {}))
                ))
                self.conn.commit()
        except Exception as e:
            print(f"Failed to flush evidence: {e}")
            self.conn.rollback()
