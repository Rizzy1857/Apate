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
                CREATE TABLE IF NOT EXISTS file_audit_log (
                    id BIGSERIAL PRIMARY KEY,
                    session_id UUID,
                    timestamp TIMESTAMP NOT NULL,
                    operation VARCHAR(50),
                    path TEXT,
                    inode BIGINT,
                    metadata JSONB
                );
            """)
            self.conn.commit()

    def log_operation(self, session_id: str, operation: str, path: str, inode: int, metadata: dict = {}):
        if not self.conn: return
        
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO file_audit_log (session_id, timestamp, operation, path, inode, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (session_id, datetime.utcnow(), operation, path, inode, Json(metadata)))
                self.conn.commit()
        except Exception as e:
            print(f"Failed to log operation: {e}")
            self.conn.rollback()
