"""Produce explicitly synthetic export examples using the frozen release code.

Run from the repository root with PYTHONPATH pointing to extracted src/.
These examples are not captured attacker sessions or additional test runs.
"""
import hashlib
import json
from pathlib import Path
import uuid

from chronos.watcher.export_report import write_bundle

root = Path(__file__).resolve().parents[2]
candidate = json.loads((root / "evidence/release_candidate_20261011/candidate.json").read_text())
sid = str(uuid.uuid5(uuid.NAMESPACE_URL, "mirage-release-example-20261011"))
cid = str(uuid.uuid5(uuid.UUID(sid), "command"))
events = []
for number, operation, metadata in [
    (1, "ssh_command", {"command_id": cid, "command": "echo SYNTHETIC_SECRET", "origin": "synthetic"}),
    (2, "ssh_command_result", {"command_id": cid, "outcome": "emulated_success", "exit_status": 0, "origin": "synthetic"}),
]:
    events.append({"id": number, "event_id": str(uuid.uuid5(uuid.UUID(sid), str(number))),
                   "session_id": sid, "timestamp": f"2026-10-11T00:00:0{number}+00:00",
                   "operation": operation, "path": "", "metadata": metadata})
metadata = {
    "run_id": "synthetic-export-example-20261011",
    "source_revision": candidate["source_archive_sha256"],
    "configuration_digest": hashlib.sha256((root / "config/generation_policy.yaml").read_bytes()).hexdigest(),
    "profile_digest": hashlib.sha256((root / "config/ubuntu.yaml").read_bytes()).hexdigest(),
}
for mode in ("raw", "redacted"):
    destination = Path(__file__).parent / f"example-{mode}"
    write_bundle(destination, events, metadata, mode=mode)
    complete = json.loads((destination / "complete.json").read_text())
    for name, digest in complete["sha256"].items():
        assert hashlib.sha256((destination / name).read_bytes()).hexdigest() == digest
    content = "".join(p.read_text() for p in destination.iterdir() if p.is_file())
    assert ("SYNTHETIC_SECRET" in content) == (mode == "raw")
print("PASS: synthetic raw/redacted examples, hashes and sentinel separation")
