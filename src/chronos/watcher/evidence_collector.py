import logging
import json
import os
from datetime import datetime
from typing import Dict, Any

import redis
from prometheus_client import Counter, Histogram

from chronos.watcher.log_streamer import AuditLogStreamer
from chronos.core.persistence import PersistenceLayer
from chronos.skills.command_analyzer import CommandAnalyzer
from chronos.skills.threat_library import ThreatLibrary
from chronos.skills.skill_detector import SkillDetector

logger = logging.getLogger(__name__)

# Prometheus metrics
SESSION_DURATION_HIST = Histogram(
    'chronos_session_duration_seconds',
    'Session duration in seconds measured at session end'
)
SESSION_COMMANDS_COUNTER = Counter(
    'chronos_session_commands_total',
    'Total number of commands executed across sessions'
)

class EvidenceCollector:
    """
    Subscribes to the AuditLogStreamer to build up deterministic telemetry
    for a given session. Zero AI involvement. Flushes to PostgreSQL on session end.
    """

    def __init__(self, streamer: AuditLogStreamer, persistence: PersistenceLayer):
        self.streamer = streamer
        self.persistence = persistence
        self.redis = redis.Redis(host=os.environ.get('REDIS_HOST', 'localhost'),
                                 port=int(os.environ.get('REDIS_PORT', '6379')),
                                 db=0, decode_responses=True)
        self.streamer.subscribe(self._process_event)
        self.command_analyzer = CommandAnalyzer()
        self.threat_library = ThreatLibrary()
        self.skill_detector = SkillDetector()

        logger.info("[EvidenceCollector] Subscribed to AuditLogStreamer")

    def _get_evidence(self, session_id: str, default_timestamp: str | None = None) -> Dict[str, Any]:
        key = f"chronos:evidence:{session_id}"
        # PostgreSQL progress is authoritative; Redis is only a dashboard cache.
        if hasattr(self.persistence, 'load_evidence_progress'):
            progress = self.persistence.load_evidence_progress(session_id)
            if progress is not None:
                return progress
            data = None
        else:
            data = self.redis.get(key)
        if data and isinstance(data, (str, bytes, bytearray)):
            return json.loads(data)
        
        return {
            "session_id": session_id,
            "start_time": default_timestamp or datetime.utcnow().isoformat(),
            "end_time": None,
            "duration_seconds": 0,
            "detection_status": "undetected",
            "detection_confidence": None,
            "exit_reason": "active",
            "first_suspicious_command": None,
            "last_successful_interaction": None,
            "commands": [],
            "visited_files": [],
            "traversal_graph": {}
        }

    def _save_evidence(self, session_id: str, data: Dict[str, Any]):
        key = f"chronos:evidence:{session_id}"
        if hasattr(self.persistence, 'save_evidence_progress'):
            self.persistence.save_evidence_progress(session_id, data)
        self.redis.set(key, json.dumps(data), ex=86400)

    def _process_event(self, event: Dict[str, Any]):
        session_id = event.get('session_id')
        if not session_id:
            return

        timestamp_str = event.get('timestamp')
        timestamp_val = str(timestamp_str) if timestamp_str else None
        evidence = self._get_evidence(session_id, timestamp_val)
        event_id = event.get('id')
        if event_id is not None:
            if event_id <= evidence.get('last_event_id', 0):
                if event.get('operation') == 'ssh_disconnect':
                    self._flush(session_id, evidence)
                return
            evidence['last_event_id'] = event_id
        operation = event.get('operation')

        if operation == 'ssh_command':
            metadata = event.get('metadata', {})
            cmd = metadata.get('command')
            if cmd:
                # Analyze command for techniques and threat signatures
                analysis = self.command_analyzer.analyze(cmd)
                matches = self.threat_library.match(cmd)

                evidence['commands'].append({
                    "timestamp": timestamp_str,
                    "command": cmd,
                    "command_id": metadata.get("command_id"),
                    "outcome": "unknown",
                    "techniques": analysis.techniques,
                    "risk_score": analysis.risk_score,
                    "signatures": [m.id for m in matches],
                })

                # Update detection state
                if analysis.risk_score > 0 or matches:
                    if evidence['first_suspicious_command'] is None:
                        evidence['first_suspicious_command'] = cmd
                    evidence['detection_status'] = 'detected'
                    # Rule matches are not calibrated probabilities. Preserve
                    # compatibility with the nullable database column, not the
                    # old repetition-inflated score.
                    evidence['detection_confidence'] = None

        elif operation == 'ssh_command_result':
            metadata = event.get('metadata', {})
            command_id = metadata.get('command_id')
            command = next((c for c in evidence['commands']
                            if command_id and c.get('command_id') == command_id), None)
            if command is not None:
                command.update({key: metadata.get(key) for key in (
                    'outcome', 'exit_status', 'server_elapsed_seconds', 'response_bytes', 'reason'
                ) if key in metadata})
                command['completed_at'] = timestamp_str
                if metadata.get('outcome') == 'emulated_success':
                    evidence['last_successful_interaction'] = timestamp_str

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

            # Persist skill assessment atomically with evidence flush
            command_analyses = self.command_analyzer.batch_analyze(
                [c['command'] for c in evidence['commands'] if 'command' in c]
            )
            if command_analyses:
                skill_assessment = self.skill_detector.analyze_session(session_id, command_analyses)
                evidence['skill_assessment'] = skill_assessment
            # Emit basic Prometheus metrics before flushing
            try:
                SESSION_DURATION_HIST.observe(evidence['duration_seconds'])
                SESSION_COMMANDS_COUNTER.inc(len(evidence.get('commands', [])))
            except Exception:
                logger.exception("Failed to emit Prometheus metrics for session %s", session_id)

            self._save_evidence(session_id, evidence)
            self._flush(session_id, evidence)
            return

        self._save_evidence(session_id, evidence)

    def _flush(self, session_id: str, evidence: Dict[str, Any]):
        logger.info(f"[EvidenceCollector] Flushing session {session_id[:8]} to Postgres")
        if self.persistence.flush_evidence(session_id, evidence):
            self.redis.delete(f"chronos:evidence:{session_id}")
        else:
            logger.error('Evidence retained in Redis after failed flush session=%s', session_id)
            raise RuntimeError('Evidence flush failed; retry event')
