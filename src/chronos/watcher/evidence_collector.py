import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional

import redis

from chronos.watcher.log_streamer import AuditLogStreamer
from chronos.core.persistence import PersistenceLayer
from chronos.skills.command_analyzer import CommandAnalyzer
from chronos.skills.threat_library import ThreatLibrary

logger = logging.getLogger(__name__)

class EvidenceCollector:
    """
    Subscribes to the AuditLogStreamer to build up deterministic telemetry
    for a given session. Zero AI involvement. Flushes to PostgreSQL on session end.
    """

    def __init__(self, streamer: AuditLogStreamer, persistence: PersistenceLayer):
        self.streamer = streamer
        self.persistence = persistence
        self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        self.streamer.subscribe(self._process_event)
        self.command_analyzer = CommandAnalyzer()
        self.threat_library = ThreatLibrary()

        logger.info("[EvidenceCollector] Subscribed to AuditLogStreamer")

    def _get_evidence(self, session_id: str, default_timestamp: str = None) -> Dict[str, Any]:
        key = f"chronos:evidence:{session_id}"
        data = self.redis.get(key)
        if data:
            return json.loads(data)
        
        return {
            "session_id": session_id,
            "start_time": default_timestamp or datetime.utcnow().isoformat(),
            "end_time": None,
            "duration_seconds": 0,
            "detection_status": "undected",
            "detection_confidence": 0.0,
            "exit_reason": "active",
            "first_suspicious_command": None,
            "last_successful_interaction": None,
            "commands": [],
            "visited_files": [],
            "traversal_graph": {}
        }

    def _save_evidence(self, session_id: str, data: Dict[str, Any]):
        key = f"chronos:evidence:{session_id}"
        self.redis.set(key, json.dumps(data))
        # Optional: set TTL so it doesn't linger forever if it crashes
        self.redis.expire(key, 86400) # 24 hours

    def _process_event(self, event: Dict[str, Any]):
        session_id = event.get('session_id')
        if not session_id:
            return

        timestamp_str = event.get('timestamp')
        evidence = self._get_evidence(session_id, timestamp_str)
        operation = event.get('operation')

        if operation == 'ssh_command':
            metadata = event.get('metadata', {})
            cmd = metadata.get('command')
            if cmd:
                evidence['commands'].append({
                    "timestamp": timestamp_str,
                    "command": cmd
                })
                evidence['last_successful_interaction'] = timestamp_str

                # Update detection state
                analysis = self.command_analyzer.analyze(cmd)
                matches = self.threat_library.match(cmd)
                if analysis.risk_score > 0 or matches:
                    if evidence['first_suspicious_command'] is None:
                        evidence['first_suspicious_command'] = cmd
                    evidence['detection_status'] = 'detected'
                    evidence['detection_confidence'] = min(1.0, evidence['detection_confidence'] + 0.2)

        elif operation in ('read', 'create', 'getattr', 'readdir'):
            path = event.get('path')
            if path and path not in evidence['visited_files']:
                evidence['visited_files'].append(path)
            
            # Simple traversal tracking (parent to child)
            if path:
                parts = path.rsplit('/', 1)
                if len(parts) == 2:
                    parent, child = parts
                    if not parent:
                        parent = '/'
                    if parent not in evidence['traversal_graph']:
                        evidence['traversal_graph'][parent] = []
                    if child not in evidence['traversal_graph'][parent]:
                        evidence['traversal_graph'][parent].append(child)

        elif operation == 'ssh_disconnect':
            evidence['end_time'] = timestamp_str
            start_dt = datetime.fromisoformat(evidence['start_time'])
            end_dt = datetime.fromisoformat(evidence['end_time'])
            evidence['duration_seconds'] = int((end_dt - start_dt).total_seconds())
            evidence['exit_reason'] = "disconnect"
            
            self._save_evidence(session_id, evidence)
            self._flush(session_id, evidence)
            return

        self._save_evidence(session_id, evidence)

    def _flush(self, session_id: str, evidence: Dict[str, Any]):
        logger.info(f"[EvidenceCollector] Flushing session {session_id[:8]} to Postgres")
        self.persistence.flush_evidence(session_id, evidence)
        self.redis.delete(f"chronos:evidence:{session_id}")
