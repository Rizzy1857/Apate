"""Run against a disposable PostgreSQL database, never an operator database."""
import os
import tempfile
import threading
import time
import uuid
from chronos.core.persistence import PersistenceLayer


def wait_for(predicate):
    for _ in range(150):
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError('Audit recovery timed out')


def main():
    with tempfile.TemporaryDirectory() as directory:
        os.environ['CHRONOS_AUDIT_SPOOL'] = directory + '/audit.sqlite3'
        store = PersistenceLayer()
        store.connect()
        store.running = False
        store.worker_thread.join(5)
        store.conn.close()
        store.conn = None
        original_host = store.host
        store.host = '127.0.0.1'  # No PostgreSQL in this test client container.
        sid = str(uuid.uuid4())
        store.log_operation(sid, 'ssh_command', '', 0, {'command': 'id', 'password': 'secret'})
        pending = store.spool.pending()
        assert 'secret' not in repr(pending)
        real_ack = store.spool.acknowledge
        calls = []

        def uncertain_ack(ids):
            calls.append(ids)
            if len(calls) == 1:
                raise OSError('Simulated process failure after PostgreSQL commit')
            real_ack(ids)

        store.spool.acknowledge = uncertain_ack
        store.running = True
        store.worker_thread = threading.Thread(target=store._audit_worker)
        store.worker_thread.start()
        try:
            time.sleep(1.2)
            assert store.spool.pending() == pending
            store.host = original_host
            wait_for(lambda: not store.spool.pending())
            assert len(calls) >= 2
            import psycopg2
            conn = psycopg2.connect(host=original_host, user=store.user,
                                    password=store.password, dbname=store.dbname)
            try:
                with conn.cursor() as cur:
                    cur.execute('SELECT COUNT(*) FROM audit_log WHERE session_id=%s', (sid,))
                    assert cur.fetchone()[0] == 1
                evidence = {'start_time': '2026-09-09T00:00:00',
                            'last_event_id': 10, 'commands': [{'command': 'id'}]}
                assert store.flush_evidence(sid, evidence)
                store.save_evidence_progress(sid, evidence)
                store.save_evidence_progress(sid, {**evidence, 'last_event_id': 9, 'commands': []})
                assert store.load_evidence_progress(sid)['commands'] == [{'command': 'id'}]
                assert store.flush_evidence(sid, {**evidence, 'commands': []})
                assert store.flush_evidence(sid, {**evidence, 'last_event_id': 9, 'commands': []})
                with conn.cursor() as cur:
                    cur.execute('SELECT commands FROM session_evidence WHERE session_id=%s', (sid,))
                    assert cur.fetchone()[0] == [{'command': 'id'}]
            finally:
                conn.close()
            print('PASS: database outage retains events; uncertain commits deduplicate; evidence replay cannot overwrite newer data')
        finally:
            store.close()


if __name__ == '__main__':
    main()
