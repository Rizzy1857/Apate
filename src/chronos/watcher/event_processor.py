import logging
import json
from datetime import datetime
from typing import Dict, Any, List
from collections import defaultdict, deque
from chronos.core.threat_scoring import calculate_risk_level_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EventProcessor:
    """Processes audit log events to detect attack patterns"""

    def __init__(self, window_seconds: int = 300):
        self.window_seconds = window_seconds
        self.event_window = deque(maxlen=10000)
        self.session_activity = defaultdict(list)
        self.file_access_patterns = defaultdict(set)
        
    def process_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process audit event and detect patterns"""
        self.event_window.append(event)

        session_id = event.get('session_id')
        if session_id:
            self.session_activity[session_id].append(event)
            if event.get('path'):
                self.file_access_patterns[session_id].add(event['path'])

        analysis = {
            "event_id": event.get('id'),
            "timestamp": event.get('timestamp'),
            "session_id": session_id,
            "patterns": [],
            "risk_score": 0,
            "tags": []
        }

        # Pattern detection
        self._detect_enumeration(event, analysis)
        self._detect_privilege_escalation(event, analysis)
        self._detect_data_exfiltration(event, analysis)
        self._detect_persistence(event, analysis)
        self._detect_lateral_movement(event, analysis)

        analysis['risk_level'] = calculate_risk_level_event(analysis['risk_score'])

        if analysis['patterns']:
            logger.warning(f"Detected: {analysis['patterns']} (Risk: {analysis['risk_level']})")

        return analysis
        
    def _detect_enumeration(self, event: Dict[str, Any], analysis: Dict[str, Any]):
        """Detect enumeration patterns"""
        operation = event.get('operation', '')
        path = event.get('path', '')
        session_id = event.get('session_id')

        if operation in ['readdir', 'getattr']:
            recent_ops = [e for e in self.event_window
                         if e.get('session_id') == session_id
                         and e.get('operation') in ['readdir', 'getattr']]

            if len(recent_ops) > 50:
                analysis['patterns'].append('rapid_enumeration')
                analysis['risk_score'] += 15
                analysis['tags'].append('reconnaissance')

        sensitive_paths = ['/etc/passwd', '/etc/shadow', '/etc/group', '/root/.ssh']
        if any(sensitive in path for sensitive in sensitive_paths):
            analysis['patterns'].append('sensitive_file_access')
            analysis['risk_score'] += 20
            analysis['tags'].append('enumeration')
            
    def _detect_privilege_escalation(self, event: Dict[str, Any], analysis: Dict[str, Any]):
        """Detect privilege escalation attempts"""
        path = event.get('path', '')
        operation = event.get('operation', '')

        suid_paths = ['/usr/bin/sudo', '/bin/su', '/usr/bin/passwd']
        if any(suid in path for suid in suid_paths):
            analysis['patterns'].append('suid_binary_access')
            analysis['risk_score'] += 25
            analysis['tags'].append('privilege_escalation')

        if operation in ['create', 'write', 'mkdir'] and path.startswith(('/bin', '/sbin', '/usr/bin', '/etc')):
            analysis['patterns'].append('system_dir_modification')
            analysis['risk_score'] += 30
            analysis['tags'].append('privilege_escalation')
            
    def _detect_data_exfiltration(self, event: Dict[str, Any], analysis: Dict[str, Any]):
        """Detect data exfiltration patterns"""
        operation = event.get('operation', '')
        path = event.get('path', '')
        session_id = event.get('session_id')

        if operation == 'read':
            recent_reads = [e for e in self.event_window
                           if e.get('session_id') == session_id
                           and e.get('operation') == 'read']

            if len(recent_reads) > 100:
                analysis['patterns'].append('mass_file_read')
                analysis['risk_score'] += 20
                analysis['tags'].append('exfiltration')

        db_extensions = ['.db', '.sql', '.mdb', '.sqlite']
        if any(path.endswith(ext) for ext in db_extensions):
            analysis['patterns'].append('database_access')
            analysis['risk_score'] += 15
            analysis['tags'].append('exfiltration')
            
    def _detect_persistence(self, event: Dict[str, Any], analysis: Dict[str, Any]):
        """Detect persistence mechanism installation"""
        path = event.get('path', '')
        operation = event.get('operation', '')

        if 'cron' in path and operation in ['create', 'write']:
            analysis['patterns'].append('cron_modification')
            analysis['risk_score'] += 35
            analysis['tags'].append('persistence')

        if '.ssh' in path and operation in ['create', 'write']:
            analysis['patterns'].append('ssh_key_installation')
            analysis['risk_score'] += 40
            analysis['tags'].append('persistence')

        rc_files = ['.bashrc', '.bash_profile', '.profile', '/etc/rc.local']
        if any(rc in path for rc in rc_files) and operation == 'write':
            analysis['patterns'].append('rc_file_modification')
            analysis['risk_score'] += 35
            analysis['tags'].append('persistence')
            
    def _detect_lateral_movement(self, event: Dict[str, Any], analysis: Dict[str, Any]):
        """Detect lateral movement attempts"""
        path = event.get('path', '')

        network_files = ['/etc/hosts', '/etc/resolv.conf', '/etc/network']
        if any(nf in path for nf in network_files):
            analysis['patterns'].append('network_config_access')
            analysis['risk_score'] += 10
            analysis['tags'].append('lateral_movement')

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get summary of activity for a session"""
        events = self.session_activity.get(session_id, [])
        files = self.file_access_patterns.get(session_id, set())

        operations = defaultdict(int)
        for event in events:
            operations[event.get('operation', 'unknown')] += 1

        return {
            "session_id": session_id,
            "total_events": len(events),
            "unique_files": len(files),
            "operations": dict(operations),
            "files_accessed": list(files)[:50]
        }

    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs"""
        return list(self.session_activity.keys())
