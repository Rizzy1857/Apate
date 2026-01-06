import os
import csv
from datetime import datetime
from typing import List, Optional

DATA_DIR = os.environ.get("APATE_DATA_DIR", "data")
SESSIONS_CSV = os.path.join(DATA_DIR, "sessions.csv")
SEQUENCES_CSV = os.path.join(DATA_DIR, "sequences.csv")
OUTCOMES_CSV = os.path.join(DATA_DIR, "outcomes.csv")

os.makedirs(DATA_DIR, exist_ok=True)


def _append_csv(path: str, header: List[str], row: List[str]) -> None:
    exists = os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(header)
        writer.writerow(row)


def log_session_start(session_id: str, protocol: str, start_time: Optional[datetime] = None) -> None:
    start_iso = (start_time or datetime.utcnow()).isoformat()
    header = ["session_id", "protocol", "start_time", "end_time", "interaction_count", "layer_reached", "discovered"]
    row = [session_id, protocol, start_iso, "", "0", "L0", "false"]
    _append_csv(SESSIONS_CSV, header, row)


def log_session_end(session_id: str, end_time: Optional[datetime] = None, interaction_count: int = 0,
                     layer_reached: str = "L1", discovered: bool = False) -> None:
    # For simplicity, append a terminal row; downstream analysis can reconcile starts/ends
    end_iso = (end_time or datetime.utcnow()).isoformat()
    header = ["session_id", "protocol", "start_time", "end_time", "interaction_count", "layer_reached", "discovered"]
    row = [session_id, "", "", end_iso, str(interaction_count), layer_reached, str(discovered).lower()]
    _append_csv(SESSIONS_CSV, header, row)


def log_sequence(session_id: str, commands: List[str], timing_buckets: Optional[List[str]] = None,
                 errors: Optional[List[bool]] = None) -> None:
    cmd_str = " ".join(commands)
    timing_str = " ".join(timing_buckets or ["medium"] * len(commands))
    errors_str = " ".join(["true" if e else "false" for e in (errors or [False] * len(commands))])
    header = ["session_id", "commands", "timing_buckets", "errors"]
    row = [session_id, cmd_str, timing_str, errors_str]
    _append_csv(SEQUENCES_CSV, header, row)


def log_outcome(session_id: str, session_duration_bucket: str, honeytoken_triggered: bool,
                protocol_switched: bool, repeated_after_error: bool, abandoned_after_delay: bool) -> None:
    header = [
        "session_id", "session_duration_bucket", "honeytoken_triggered", "protocol_switched",
        "repeated_after_error", "abandoned_after_delay"
    ]
    row = [
        session_id, session_duration_bucket, str(honeytoken_triggered).lower(),
        str(protocol_switched).lower(), str(repeated_after_error).lower(), str(abandoned_after_delay).lower()
    ]
    _append_csv(OUTCOMES_CSV, header, row)
