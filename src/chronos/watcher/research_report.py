"""Deterministic evidence reconciliation. No inference and no database writes."""
from collections import Counter
import hashlib
import json
import math


def build_report(events, run_metadata=None):
    """Reconcile an explicit input snapshot; never claim collection completeness.

    IDs deduplicate replay, while command identity includes the session. Input
    order is immaterial. Unknown-origin legacy evidence stays visible separately.
    Caller must supply all selected events, not a dashboard preview buffer.
    """
    unique = {}
    duplicates = 0
    for original in events:
        event = dict(original)
        identity = event.get('event_id') or event.get('id')
        if identity is None:
            raise ValueError('Every event requires a stable event_id or database id')
        identity = str(identity)
        if identity in unique:
            if unique[identity] != event:
                raise ValueError('Conflicting records share an event identifier')
            duplicates += 1
        else:
            unique[identity] = event

    submissions, results, effects = {}, {}, {}
    origins = Counter()
    legacy_submissions = []
    for identity, event in unique.items():
        metadata = event.get('metadata') or {}
        key = (event.get('session_id'), metadata.get('command_id'))
        operation = event.get('operation')
        if operation == 'ssh_command':
            origins[metadata.get('origin', 'unknown')] += 1
            if not all(key):
                legacy_submissions.append(identity)
                continue
            if key in submissions:
                raise ValueError('Multiple submissions share a session/command identity')
            submissions[key] = (identity, event)
        elif operation == 'ssh_command_result':
            results.setdefault(key, []).append((identity, metadata))
        elif operation in ('read', 'write', 'create', 'unlink'):
            effects.setdefault(key, []).append((identity, event))

    commands = []
    measured = []
    for key, (identity, event) in sorted(submissions.items()):
        metadata = event.get('metadata') or {}
        completions = results.get(key, [])
        result = completions[0][1] if len(completions) == 1 else {}
        outcome = result.get('outcome', 'unknown')
        origin = metadata.get('origin', 'unknown')
        duration = result.get('server_elapsed_seconds')
        valid_duration = (type(duration) in (int, float)
                          and math.isfinite(duration) and duration >= 0)
        if origin == 'participant' and valid_duration and len(completions) == 1:
            measured.append(duration)
        commands.append({
            'session_id': key[0], 'command_id': key[1], 'origin': origin,
            'submission_event_id': identity, 'command': metadata.get('command'),
            'outcome': outcome, 'exit_status': result.get('exit_status'),
            'server_elapsed_seconds': duration if valid_duration else None,
            'result_event_ids': [item[0] for item in completions],
            'conflicting_results': len(completions) > 1,
            'file_events': [{'event_id': eid, 'operation': effect['operation'],
                             'path': effect.get('path'), 'metadata': effect.get('metadata', {})}
                            for eid, effect in effects.get(key, [])],
        })

    measured.sort()
    def percentile(fraction):
        # Explicit nearest-rank convention, not an interpolated estimate.
        return measured[max(0, math.ceil(len(measured) * fraction) - 1)] if measured else None

    canonical = json.dumps(sorted(unique.items()), sort_keys=True, separators=(',', ':'),
                           ensure_ascii=True, allow_nan=False).encode()
    return {
        'schema_version': 1, 'run_metadata': dict(run_metadata or {}),
        'input_sha256': hashlib.sha256(canonical).hexdigest(),
        'unique_events': len(unique), 'duplicate_events_removed': duplicates,
        'submissions_by_origin': dict(origins), 'commands': commands,
        'legacy_submission_event_ids': legacy_submissions,
        'unmatched_result_event_ids': [eid for key, items in results.items()
                                       if key not in submissions for eid, _ in items],
        'unmatched_file_event_ids': [eid for key, items in effects.items()
                                     if key not in submissions for eid, _ in items],
        'participant_outcomes': dict(Counter(c['outcome'] for c in commands
                                             if c['origin'] == 'participant')),
        'participant_server_latency': {
            'sample_count': len(measured), 'method': 'nearest_rank',
            'p50_seconds': percentile(.5), 'p95_seconds': percentile(.95),
            'p99_seconds': percentile(.99),
        },
        'limitations': [
            'Completeness is relative to the supplied snapshot, not the collection system.',
            'Server elapsed time is not client-observed or network latency.',
            'Unknown outcomes and legacy records do not prove successful execution.',
            'No participant discovery time or calibrated threat probability is inferred.',
            'Raw command evidence may contain secrets; restrict access before sharing.',
        ],
    }
