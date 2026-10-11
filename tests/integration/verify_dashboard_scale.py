"""Exercise frozen pagination and raw/redacted export against disposable PostgreSQL."""

from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import tempfile
import uuid

import psycopg2
from psycopg2.extras import Json, execute_batch

from chronos.watcher.export_report import load_session, write_bundle


PAGE_SIZE = 50
SESSION_COUNT = 125
EVENTS_PER_SESSION = 10


def page(conn, snapshot, offset):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT session_id::text FROM session_evidence "
            "WHERE end_time IS NOT NULL AND finalized_at <= %s "
            "ORDER BY start_time DESC NULLS LAST, session_id DESC "
            "LIMIT %s OFFSET %s",
            (snapshot, PAGE_SIZE, offset),
        )
        return [row[0] for row in cur.fetchall()]


def main():
    conn = psycopg2.connect(
        host=os.environ["POSTGRES_HOST"], user="chronos",
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        password="chronos_dev_password", dbname="chronos",
    )
    base = datetime(2026, 1, 1)
    sessions = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"apate-scale-{i}"))
                for i in range(SESSION_COUNT)]
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE session_evidence (
                    session_id UUID PRIMARY KEY, start_time TIMESTAMP,
                    end_time TIMESTAMP, duration_seconds INT,
                    detection_status VARCHAR(50), detection_confidence FLOAT,
                    exit_reason VARCHAR(50), first_suspicious_command TEXT,
                    last_successful_interaction TIMESTAMP, commands JSONB,
                    visited_files JSONB, traversal_graph JSONB,
                    skill_assessment JSONB, last_event_id BIGINT NOT NULL DEFAULT 0,
                    finalized_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE audit_log (
                    id BIGSERIAL PRIMARY KEY, event_id UUID UNIQUE,
                    session_id UUID, timestamp TIMESTAMP NOT NULL,
                    operation VARCHAR(50), path TEXT, inode BIGINT, metadata JSONB
                );
            """)
            execute_batch(cur, """
                INSERT INTO session_evidence (
                    session_id, start_time, end_time, duration_seconds,
                    detection_status, exit_reason, commands, visited_files,
                    traversal_graph, last_event_id, finalized_at
                ) VALUES (%s,%s,%s,60,'undetected','disconnect','[]','[]','{}',10,%s)
            """, [
                (sid, base + timedelta(minutes=index),
                 base + timedelta(minutes=index, seconds=60),
                 base + timedelta(days=1))
                for index, sid in enumerate(sessions)
            ])
            events = []
            for index, sid in enumerate(sessions):
                command_id = str(uuid.uuid5(uuid.UUID(sid), "command"))
                for event_index in range(EVENTS_PER_SESSION):
                    if event_index == 0:
                        operation = "ssh_command"
                        metadata = {"command": "echo SCALE_SECRET", "command_id": command_id,
                                    "origin": "scripted_test"}
                        path = ""
                    elif event_index == 1:
                        operation = "ssh_command_result"
                        metadata = {"command_id": command_id, "outcome": "emulated_success",
                                    "exit_status": 0, "server_elapsed_seconds": 0.01,
                                    "origin": "scripted_test"}
                        path = ""
                    else:
                        operation = "read"
                        metadata = {"outcome": "completed", "origin": "scripted_test"}
                        path = f"/tmp/SCALE_SECRET/{event_index}"
                    event_id = str(uuid.uuid5(uuid.UUID(sid), f"event-{event_index}"))
                    events.append((event_id, sid, base + timedelta(minutes=index,
                                  seconds=event_index), operation, path, event_index, Json(metadata)))
            execute_batch(cur, """
                INSERT INTO audit_log
                (event_id,session_id,timestamp,operation,path,inode,metadata)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, events, page_size=500)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT CURRENT_TIMESTAMP::timestamp")
            snapshot = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM audit_log")
            assert cur.fetchone()[0] == SESSION_COUNT * EVENTS_PER_SESSION

        first = page(conn, snapshot, 0)
        conn.commit()
        inserted = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO session_evidence
                (session_id,start_time,end_time,duration_seconds,detection_status,
                 exit_reason,commands,visited_files,traversal_graph,last_event_id)
                VALUES (%s,%s,%s,1,'undetected','disconnect','[]','[]','{}',1)
            """, (inserted, base + timedelta(days=365), base + timedelta(days=365, seconds=1)))
        conn.commit()
        frozen = first + page(conn, snapshot, 50) + page(conn, snapshot, 100)
        assert len(frozen) == SESSION_COUNT
        assert len(set(frozen)) == SESSION_COUNT
        assert inserted not in frozen

        with conn.cursor() as cur:
            cur.execute("SELECT CURRENT_TIMESTAMP::timestamp")
            refreshed = cur.fetchone()[0]
        assert page(conn, refreshed, 0)[0] == inserted
        conn.rollback()

        old_session = sessions[0]
        events, snapshot_at = load_session(conn, old_session)
        assert len(events) == EVENTS_PER_SESSION
        conn.rollback()
        with tempfile.TemporaryDirectory() as folder:
            raw_dir = Path(folder) / "raw"
            redacted_dir = Path(folder) / "redacted"
            metadata = {
                "run_id": "scale", "source_revision": "working-tree",
                "configuration_digest": "scale-config", "profile_digest": "scale-profile",
                "database_snapshot_at": snapshot_at,
            }
            write_bundle(raw_dir, events, metadata, mode="raw")
            write_bundle(redacted_dir, events, metadata, mode="redacted")
            assert (raw_dir / "complete.json").exists()
            assert (redacted_dir / "complete.json").exists()
            assert "SCALE_SECRET" in (raw_dir / "events.json").read_text()
            assert "SCALE_SECRET" not in "".join(
                path.read_text() for path in redacted_dir.iterdir() if path.is_file()
            )
            complete = json.loads((redacted_dir / "complete.json").read_text())
            assert complete["artifact_type"] == "redacted_evidence_bundle"

        print(json.dumps({
            "result": "PASS", "sessions_in_snapshot": len(frozen),
            "events": SESSION_COUNT * EVENTS_PER_SESSION,
            "page_sizes": [len(first), len(page(conn, snapshot, 50)),
                           len(page(conn, snapshot, 100))],
            "concurrent_insert_visible_after_refresh": True,
            "old_session_export_events": len(events),
        }))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
