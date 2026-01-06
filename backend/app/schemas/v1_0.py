from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Literal

SCHEMA_VERSION = "v1.0"

@dataclass
class SessionRecord:
    session_id: str
    protocol: Literal["ssh", "http", "tcp", "unknown"]
    start_time: datetime
    end_time: Optional[datetime]
    interaction_count: int
    layer_reached: Literal["L0", "L1", "L2", "L3", "L4"]
    discovered: bool

@dataclass
class SequenceRecord:
    session_id: str
    commands: List[str]  # canonicalized
    timing_buckets: List[Literal["fast", "medium", "slow"]]
    errors: List[bool]

@dataclass
class OutcomeSignals:
    session_duration_bucket: Literal["<1m", "1-5m", "5-15m", "15-60m", ">60m"]
    honeytoken_triggered: bool
    protocol_switched: bool
    repeated_after_error: bool
    abandoned_after_delay: bool
