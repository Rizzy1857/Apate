"""Read-only, snapshot-consistent raw or allowlist-redacted evidence export."""

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


EXPORT_SCHEMA_VERSION = 2
RUN_RECORD_SCHEMA_VERSION = 1
REDACTION_POLICY = "apate-structural-allowlist-v1"
REQUIRED_RUN_FIELDS = (
    "run_id", "source_revision", "configuration_digest", "profile_digest",
)
RUN_RECORD_FIELDS = frozenset({
    "run_id", "source_revision", "configuration_digest", "profile_digest",
    "model_identifier", "session_id", "database_snapshot_at", "exported_at",
    "selection", "pending_spool_events_included", "artifact_treatment",
    "inference_mode",
})

# Only collector-controlled enums, booleans and measurements are shareable.
# Unknown/free-text fields are omitted even if they appear harmless.
SHAREABLE_METADATA = frozenset({
    "accepted", "actual_bytes", "command_id", "created", "delivery_reason",
    "effective_username", "elapsed_seconds", "errno", "exit_status",
    "generated_response_bytes", "identity_mismatch", "identity_policy", "method",
    "new_gid", "new_mode", "new_size", "new_uid", "offset", "old_gid", "old_mode",
    "old_size", "old_uid", "origin", "outcome", "reason", "request_id",
    "request_type", "requested_bytes", "response_bytes", "response_delivery",
    "schema_version", "server_elapsed_seconds", "state_may_have_changed",
    "transport_response_bytes",
})
PSEUDONYM_METADATA = frozenset({
    "claimed_username", "effective_username", "command_id", "request_id",
})
SAFE_STRING_VALUES = frozenset({
    "accepted_by_transport", "command_failed", "completed", "denied", "failed",
    "interrupted", "no_response", "participant", "password", "publickey",
    "scripted_test", "synthetic", "timed_out", "unattributed", "uncertain",
    "unknown", "unsupported", "emulated_success",
    "accept_any_claim_profile_identity",
})


def load_session(connection, session_id):
    import psycopg2.extras
    session_id = str(uuid.UUID(session_id))
    connection.set_session(isolation_level="REPEATABLE READ", readonly=True, autocommit=False)
    with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
        cursor.execute("SET LOCAL statement_timeout = 60000")
        cursor.execute("SELECT CURRENT_TIMESTAMP AS snapshot_at")
        snapshot_at = cursor.fetchone()["snapshot_at"].isoformat()
        cursor.execute("""SELECT id, event_id::text, session_id::text, timestamp,
                          operation, path, inode, metadata FROM audit_log
                          WHERE session_id = %s ORDER BY id ASC""", (session_id,))
        events = []
        for row in cursor:
            row = dict(row)
            row["timestamp"] = row["timestamp"].isoformat()
            events.append(row)
    return events, snapshot_at


def _canonical_hash(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def _pseudonym(kind, value):
    return f"{kind}:sha256:{_canonical_hash(value)[:16]}"


def redact_events(events):
    """Return a minimal structural projection plus a disclosure summary.

    This is data minimization, not a guarantee that arbitrary secrets can be
    recognized. Free text is omitted by default rather than pattern-matched.
    """
    redacted = []
    omitted = {}
    for original in events:
        event = {
            key: original[key] for key in (
                "id", "event_id", "timestamp", "operation", "inode"
            ) if key in original
        }
        if original.get("session_id") is not None:
            event["session_id"] = _pseudonym("session", original["session_id"])
        if original.get("path") is not None:
            event["path"] = _pseudonym("path", original["path"])

        metadata = original.get("metadata") or {}
        shared = {"redaction_policy": REDACTION_POLICY}
        omitted_names = []
        for key, value in metadata.items():
            if key == "command":
                shared["command_token"] = _pseudonym("command", value)
                omitted_names.append(key)
            elif key in PSEUDONYM_METADATA:
                shared[key] = _pseudonym(key, value)
            elif key in SHAREABLE_METADATA:
                if isinstance(value, (bool, int)) or value is None:
                    shared[key] = value
                elif isinstance(value, float) and value == value and abs(value) != float("inf"):
                    shared[key] = value
                elif isinstance(value, str) and value in SAFE_STRING_VALUES:
                    shared[key] = value
                else:
                    omitted_names.append(key)
            else:
                omitted_names.append(key)
        if omitted_names:
            shared["redaction_omitted_fields"] = sorted(set(omitted_names))
            for name in set(omitted_names):
                omitted[name] = omitted.get(name, 0) + 1
        event["metadata"] = shared
        redacted.append(event)

    summary = {
        "schema_version": 1,
        "policy": REDACTION_POLICY,
        "strategy": "structural allowlist with stable truncated SHA-256 pseudonyms",
        "omitted_field_event_counts": dict(sorted(omitted.items())),
        "limitations": [
            "This artifact minimizes known free-text fields; it cannot guarantee removal of every secret.",
            "Pseudonyms permit within-bundle correlation and may still reveal equality.",
            "Use the private raw bundle for authoritative incident review.",
        ],
    }
    return redacted, summary


def _run_record(metadata, mode, parent_input_sha256=None):
    supplied = dict(metadata or {})
    missing = [field for field in REQUIRED_RUN_FIELDS if not supplied.get(field)]
    if mode == "redacted":
        projected = {}
        for key, value in supplied.items():
            if key not in RUN_RECORD_FIELDS:
                continue
            if isinstance(value, str):
                projected[key] = _pseudonym(f"run_metadata.{key}", value)
            elif isinstance(value, (bool, int, float)) or value is None:
                projected[key] = value
        supplied = projected
    record = {
        "schema_version": RUN_RECORD_SCHEMA_VERSION,
        "export_schema_version": EXPORT_SCHEMA_VERSION,
        "export_mode": mode,
        "metadata_values_pseudonymized": mode == "redacted",
        **supplied,
    }
    if parent_input_sha256 is not None:
        record["parent_raw_input_sha256"] = parent_input_sha256
    record["missing_reproducibility_fields"] = missing
    record["reproducibility_metadata_complete"] = not record[
        "missing_reproducibility_fields"
    ]
    return record


def _safe_csv(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def write_bundle(destination, events, metadata, *, mode="raw"):
    """Write a new private bundle; `complete.json` is the final marker."""
    if mode not in ("raw", "redacted"):
        raise ValueError("mode must be 'raw' or 'redacted'")
    destination = Path(destination)
    parent_hash = _canonical_hash(events)
    disclosure = None
    selected_events = events
    if mode == "redacted":
        selected_events, disclosure = redact_events(events)
    run_record = _run_record(
        metadata, mode, parent_hash if mode == "redacted" else None
    )
    report = build_report(selected_events, run_record)
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    hashes = {}

    def save(name, content):
        data = content.encode("utf-8")
        fd = os.open(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        hashes[name] = hashlib.sha256(data).hexdigest()

    save("events.json", json.dumps(selected_events, indent=2, ensure_ascii=True,
                                   allow_nan=False))
    save("run_record.json", json.dumps(run_record, indent=2, ensure_ascii=True,
                                       allow_nan=False))
    if disclosure is not None:
        disclosure["parent_raw_input_sha256"] = parent_hash
        save("redaction.json", json.dumps(disclosure, indent=2, ensure_ascii=True,
                                          allow_nan=False))
    save("report.json", json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False))

    table = io.StringIO(newline="")
    writer = csv.writer(table)
    command_fields = (
        "session_id", "command_id", "origin", "claimed_username",
        "effective_username", "identity_mismatch", "identity_policy", "outcome",
        "exit_status", "server_elapsed_seconds", "submission_event_id",
    )
    writer.writerow(command_fields)
    for command in report["commands"]:
        writer.writerow([_safe_csv(command.get(field)) for field in command_fields])
    save("commands.csv", table.getvalue())

    request_table = io.StringIO(newline="")
    writer = csv.writer(request_table)
    request_fields = (
        "session_id", "request_id", "request_type", "origin", "claimed_username",
        "effective_username", "identity_mismatch", "identity_policy", "outcome",
        "accepted", "event_id",
    )
    writer.writerow(request_fields)
    for request in report["ssh_requests"]:
        writer.writerow([_safe_csv(request.get(field)) for field in request_fields])
    save("ssh_requests.csv", request_table.getvalue())

    latency = report["participant_server_latency"]
    lines = [
        "# Apate session evidence report", "", f"Export mode: {mode}",
        f"Unique recorded events: {report['unique_events']}",
        f"Correlated command submissions: {len(report['commands'])}",
        f"Correlated rejected SSH requests: {len(report['ssh_requests'])}",
        f"Legacy submissions without command IDs: {len(report['legacy_submission_event_ids'])}",
        f"Legacy requests without request IDs: {len(report['legacy_request_event_ids'])}",
        f"Unmatched result events: {len(report['unmatched_result_event_ids'])}",
        f"Participant timing samples: {latency['sample_count']}", "",
        "## Interpretation limits", "",
    ]
    lines.extend("- " + limit for limit in report["limitations"])
    if disclosure is not None:
        lines.extend(["", "## Redaction limits", ""])
        lines.extend("- " + limit for limit in disclosure["limitations"])
    else:
        lines.extend(["", "This private raw bundle may contain secrets."])
    lines.extend([
        "", "This bundle contains recorded evidence, not an AI interpretation.",
        "Inspect report.json for reconciliation and run_record.json for provenance gaps.",
        "Absence of complete.json means the export did not finish.", "",
    ])
    save("report.md", "\n".join(lines))
    manifest = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "artifact_type": f"{mode}_evidence_bundle",
        "redaction_policy": REDACTION_POLICY if mode == "redacted" else None,
        "parent_raw_input_sha256": parent_hash if mode == "redacted" else None,
        "reproducibility_metadata_complete": run_record["reproducibility_metadata_complete"],
        "sha256": dict(hashes),
    }
    save("complete.json", json.dumps(manifest, indent=2, ensure_ascii=True))
    return report


def _metadata_from_environment(args, snapshot_at):
    return {
        "run_id": args.run_id or os.environ.get("APATE_RUN_ID"),
        "source_revision": os.environ.get("APATE_SOURCE_REVISION"),
        "configuration_digest": os.environ.get("APATE_CONFIGURATION_DIGEST"),
        "profile_digest": os.environ.get("APATE_PROFILE_DIGEST"),
        "model_identifier": os.environ.get("APATE_MODEL_IDENTIFIER"),
        "artifact_treatment": os.environ.get(
            "CHRONOS_ARTIFACT_TREATMENT", "deterministic"
        ),
        "inference_mode": os.environ.get(
            "CHRONOS_INFERENCE_MODE", "deterministic"
        ),
        "session_id": str(args.session_id),
        "database_snapshot_at": snapshot_at,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "selection": "all committed audit rows for selected session at snapshot",
        "pending_spool_events_included": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True, type=uuid.UUID)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mode", choices=("raw", "redacted"), default="raw")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    import psycopg2
    connection = psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5433")),
        user=os.environ.get("POSTGRES_USER", "chronos"),
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ.get("POSTGRES_DB", "chronos"), connect_timeout=5,
    )
    try:
        events, snapshot_at = load_session(connection, str(args.session_id))
    finally:
        connection.close()
    write_bundle(
        args.output, events, _metadata_from_environment(args, snapshot_at), mode=args.mode
    )
    warning = "raw records may contain secrets" if args.mode == "raw" else (
        "redaction is allowlist-based but cannot guarantee removal of every secret"
    )
    print(f"Evidence exported to {args.output}; {warning}.")


if __name__ == "__main__":
    main()
