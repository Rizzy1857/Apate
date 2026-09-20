"""Read-only, snapshot-consistent session evidence export."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import uuid

from chronos.watcher.research_report import build_report


def load_session(connection, session_id):
    import psycopg2.extras
    session_id = str(uuid.UUID(session_id))
    connection.set_session(isolation_level='REPEATABLE READ', readonly=True, autocommit=False)
    with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute('SET LOCAL statement_timeout = 60000')
        cursor.execute('SELECT CURRENT_TIMESTAMP AS snapshot_at')
        snapshot_at = cursor.fetchone()['snapshot_at'].isoformat()
        cursor.execute('''SELECT id, event_id::text, session_id::text, timestamp,
                          operation, path, inode, metadata FROM audit_log
                          WHERE session_id = %s ORDER BY id ASC''', (session_id,))
        events = []
        for row in cursor:
            row = dict(row)
            row['timestamp'] = row['timestamp'].isoformat()
            events.append(row)
    return events, snapshot_at


def write_bundle(destination, events, metadata):
    """New private directory only; complete.json is written last as completion marker."""
    destination = Path(destination)
    report = build_report(events, metadata)
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    hashes = {}

    def save(name, content):
        data = content.encode('utf-8')
        fd = os.open(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        hashes[name] = hashlib.sha256(data).hexdigest()

    save('events.json', json.dumps(events, indent=2, ensure_ascii=True, allow_nan=False))
    save('report.json', json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False))
    table = io.StringIO(newline='')
    writer = csv.writer(table)
    writer.writerow(['session_id', 'command_id', 'origin', 'outcome', 'exit_status',
                     'server_elapsed_seconds', 'submission_event_id'])
    for command in report['commands']:
        # Spreadsheet formula injection is possible even in metadata fields.
        values = [command.get(field) for field in ('session_id', 'command_id', 'origin',
                  'outcome', 'exit_status', 'server_elapsed_seconds', 'submission_event_id')]
        writer.writerow(["'" + str(v) if isinstance(v, str) and
                         v.lstrip().startswith(('=', '+', '-', '@')) else v for v in values])
    save('commands.csv', table.getvalue())
    latency = report['participant_server_latency']
    lines = ['# Apate session evidence report', '',
             f"Unique recorded events: {report['unique_events']}",
             f"Correlated command submissions: {len(report['commands'])}",
             f"Legacy submissions without command IDs: {len(report['legacy_submission_event_ids'])}",
             f"Unmatched result events: {len(report['unmatched_result_event_ids'])}",
             f"Participant timing samples: {latency['sample_count']}", '',
             '## Interpretation limits', '']
    lines.extend('- ' + limit for limit in report['limitations'])
    lines.extend(['', 'This bundle contains raw evidence, not an AI interpretation.',
                  'Inspect report.json for linked outcomes and events.json for original records.',
                  'Absence of complete.json means the export did not finish.', ''])
    save('report.md', '\n'.join(lines))
    save('complete.json', json.dumps({'schema_version': 1, 'sha256': dict(hashes)}, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-id', required=True, type=uuid.UUID)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    import psycopg2
    connection = psycopg2.connect(
        host=os.environ.get('POSTGRES_HOST', '127.0.0.1'),
        port=int(os.environ.get('POSTGRES_PORT', '5433')),
        user=os.environ.get('POSTGRES_USER', 'chronos'),
        password=os.environ['POSTGRES_PASSWORD'],
        dbname=os.environ.get('POSTGRES_DB', 'chronos'), connect_timeout=5,
    )
    try:
        events, snapshot_at = load_session(connection, str(args.session_id))
    finally:
        connection.close()
    write_bundle(args.output, events, {
        'session_id': str(args.session_id), 'database_snapshot_at': snapshot_at,
        'exported_at': datetime.now(timezone.utc).isoformat(),
        'selection': 'all committed audit rows for selected session at snapshot',
        'pending_spool_events_included': False,
    })
    print(f'Evidence exported to {args.output}; raw records may contain secrets.')


if __name__ == '__main__':
    main()
