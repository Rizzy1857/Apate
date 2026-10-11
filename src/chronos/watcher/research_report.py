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

    submissions, results, effects, requests = {}, {}, {}, {}
    origins = Counter()
    request_origins = Counter()
    legacy_submissions = []
    legacy_requests = []
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
        elif operation in ('ssh_request', 'ssh_exec'):
            request_id = metadata.get('request_id')
            request_key = (event.get('session_id'), request_id)
            request_origins[metadata.get('origin', 'unknown')] += 1
            if not all(request_key):
                legacy_requests.append(identity)
                continue
            if request_key in requests:
                raise ValueError('Multiple SSH requests share a session/request identity')
            requests[request_key] = (identity, event)
        elif operation in ('read', 'write', 'create', 'unlink', 'mkdir', 'rmdir',
                           'truncate', 'chmod', 'chown', 'utimens'):
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
            'claimed_username': metadata.get('claimed_username'),
            'effective_username': metadata.get('effective_username'),
            'identity_mismatch': metadata.get('identity_mismatch'),
            'identity_policy': metadata.get('identity_policy'),
            'outcome': outcome, 'exit_status': result.get('exit_status'),
            'stage_results': result.get('stage_results', []),
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

    reconciled_requests = []
    for key, (identity, event) in sorted(requests.items()):
        metadata = event.get('metadata') or {}
        reconciled_requests.append({
            'session_id': key[0], 'request_id': key[1],
            'request_type': metadata.get(
                'request_type', 'exec' if event.get('operation') == 'ssh_exec' else 'unknown'
            ),
            'origin': metadata.get('origin', 'unknown'),
            'outcome': metadata.get('outcome', 'unknown'),
            'accepted': metadata.get('accepted'),
            'claimed_username': metadata.get('claimed_username'),
            'effective_username': metadata.get('effective_username'),
            'identity_mismatch': metadata.get('identity_mismatch'),
            'identity_policy': metadata.get('identity_policy'),
            'event_id': identity,
            'command': metadata.get('command'),
            'details': {name: value for name, value in metadata.items() if name not in {
                'request_id', 'request_type', 'origin', 'outcome', 'accepted', 'command',
                'claimed_username', 'effective_username', 'identity_mismatch',
                'identity_policy'
            }},
        })

    command_outcomes = Counter(c['outcome'] for c in commands
                               if c['origin'] == 'participant')
    request_outcomes = Counter(r['outcome'] for r in reconciled_requests
                               if r['origin'] == 'participant')
    interaction_outcomes = command_outcomes + request_outcomes
    canonical = json.dumps(sorted(unique.items()), sort_keys=True, separators=(',', ':'),
                           ensure_ascii=True, allow_nan=False).encode()
    return {
        'schema_version': 1, 'run_metadata': dict(run_metadata or {}),
        'input_sha256': hashlib.sha256(canonical).hexdigest(),
        'unique_events': len(unique), 'duplicate_events_removed': duplicates,
        'submissions_by_origin': dict(origins), 'commands': commands,
        'requests_by_origin': dict(request_origins), 'ssh_requests': reconciled_requests,
        'legacy_submission_event_ids': legacy_submissions,
        'legacy_request_event_ids': legacy_requests,
        'unmatched_result_event_ids': [eid for key, items in results.items()
                                       if key not in submissions for eid, _ in items],
        'unmatched_file_event_ids': [eid for key, items in effects.items()
                                     if key not in submissions for eid, _ in items],
        'participant_outcomes': dict(command_outcomes),
        'participant_request_outcomes': dict(request_outcomes),
        'participant_interaction_outcomes': dict(interaction_outcomes),
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
