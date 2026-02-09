"""
Event Processor
Analyzes audit log events to detect patterns and suspicious behavior
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Set
from collections import defaultdict, deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EventProcessor:
    """
    Processes audit log events to detect attack patterns
    Maintains sliding window of recent activity for correlation
    """
    
    def __init__(self, window_seconds: int = 300):
        """
        Args:
            window_seconds: Time window for pattern detection (default: 5 minutes)
        """
        self.window_seconds = window_seconds
        self.event_window = deque(maxlen=10000)  # Sliding window of recent events
        self.session_activity = defaultdict(list)  # Activity per session
        self.file_access_patterns = defaultdict(set)  # Files accessed per session
        
    def process_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single audit event and detect patterns
        
        Returns:
            Analysis result with detected patterns and risk score
        """
        self.event_window.append(event)
        
        session_id = event.get('session_id')
        if session_id:
            self.session_activity[session_id].append(event)
            
            if event.get('path'):
                self.file_access_patterns[session_id].add(event['path'])
        
        # Analyze the event
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
        
        # Calculate overall risk score
        analysis['risk_level'] = self._calculate_risk_level(analysis['risk_score'])
        
        if analysis['patterns']:
            logger.warning(f"[EventProcessor] Detected patterns: {analysis['patterns']} (Risk: {analysis['risk_level']})")
        
        return analysis
        
    def _detect_enumeration(self, event: Dict[str, Any], analysis: Dict[str, Any]):
        """Detect enumeration/reconnaissance patterns"""
        operation = event.get('operation', '')
        path = event.get('path', '')
        session_id = event.get('session_id')
        
        # Rapid directory listings
        if operation in ['readdir', 'getattr']:
            recent_ops = [e for e in self.event_window 
                         if e.get('session_id') == session_id 
                         and e.get('operation') in ['readdir', 'getattr']]
            
            if len(recent_ops) > 50:  # More than 50 reads in window
                analysis['patterns'].append('rapid_enumeration')
                analysis['risk_score'] += 15
                analysis['tags'].append('reconnaissance')
        
        # Access to sensitive system files
        sensitive_paths = ['/etc/passwd', '/etc/shadow', '/etc/group', '/root/.ssh']
        if any(sensitive in path for sensitive in sensitive_paths):
            analysis['patterns'].append('sensitive_file_access')
            analysis['risk_score'] += 20
            analysis['tags'].append('enumeration')
            
    def _detect_privilege_escalation(self, event: Dict[str, Any], analysis: Dict[str, Any]):
        """Detect privilege escalation attempts"""
        path = event.get('path', '')
        operation = event.get('operation', '')
        
        # SUID binary access
        suid_paths = ['/usr/bin/sudo', '/bin/su', '/usr/bin/passwd']
        if any(suid in path for suid in suid_paths):
            analysis['patterns'].append('suid_binary_access')
            analysis['risk_score'] += 25
            analysis['tags'].append('privilege_escalation')
        
        # Attempting to write to system directories
        if operation in ['create', 'write', 'mkdir'] and path.startswith(('/bin', '/sbin', '/usr/bin', '/etc')):
            analysis['patterns'].append('system_dir_modification')
            analysis['risk_score'] += 30
            analysis['tags'].append('privilege_escalation')
            
    def _detect_data_exfiltration(self, event: Dict[str, Any], analysis: Dict[str, Any]):
        """Detect data exfiltration patterns"""
        operation = event.get('operation', '')
        path = event.get('path', '')
        session_id = event.get('session_id')
        
        # Large number of file reads
        if operation == 'read':
            recent_reads = [e for e in self.event_window 
                           if e.get('session_id') == session_id 
                           and e.get('operation') == 'read']
            
            if len(recent_reads) > 100:
                analysis['patterns'].append('mass_file_read')
                analysis['risk_score'] += 20
                analysis['tags'].append('exfiltration')
        
        # Access to database files
        db_extensions = ['.db', '.sql', '.mdb', '.sqlite']
        if any(path.endswith(ext) for ext in db_extensions):
            analysis['patterns'].append('database_access')
            analysis['risk_score'] += 15
            analysis['tags'].append('exfiltration')
            
    def _detect_persistence(self, event: Dict[str, Any], analysis: Dict[str, Any]):
        """Detect persistence mechanism installation"""
        path = event.get('path', '')
        operation = event.get('operation', '')
        
        # Cron job manipulation
        if 'cron' in path and operation in ['create', 'write']:
            analysis['patterns'].append('cron_modification')
            analysis['risk_score'] += 35
            analysis['tags'].append('persistence')
        
        # SSH key installation
        if '.ssh' in path and operation in ['create', 'write']:
            analysis['patterns'].append('ssh_key_installation')
            analysis['risk_score'] += 40
            analysis['tags'].append('persistence')
        
        # RC file modification
        rc_files = ['.bashrc', '.bash_profile', '.profile', '/etc/rc.local']
        if any(rc in path for rc in rc_files) and operation == 'write':
            analysis['patterns'].append('rc_file_modification')
            analysis['risk_score'] += 35
            analysis['tags'].append('persistence')
            
    def _detect_lateral_movement(self, event: Dict[str, Any], analysis: Dict[str, Any]):
        """Detect lateral movement attempts"""
        path = event.get('path', '')
        
        # Access to network config
        network_files = ['/etc/hosts', '/etc/resolv.conf', '/etc/network']
        if any(nf in path for nf in network_files):
            analysis['patterns'].append('network_config_access')
            analysis['risk_score'] += 10
            analysis['tags'].append('lateral_movement')
            
    def _calculate_risk_level(self, score: int) -> str:
        """Calculate risk level from score"""
        if score >= 50:
            return "critical"
        elif score >= 30:
            return "high"
        elif score >= 15:
            return "medium"
        elif score > 0:
            return "low"
        else:
            return "info"
            
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
            "files_accessed": list(files)[:50]  # Limit output
        }
        
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs"""
        return list(self.session_activity.keys())
        
    def clear_old_data(self):
        """Clear old data outside the window"""
        # This could be enhanced to actually track timestamps
        # For now, deque maxlen handles the window automatically
        pass


# Example usage
if __name__ == "__main__":
    processor = EventProcessor(window_seconds=300)
    
    # Simulate events
    test_events = [
        {
            "id": 1,
            "timestamp": datetime.now().isoformat(),
            "session_id": "sess_001",
            "operation": "readdir",
            "path": "/etc",
            "inode": 100
        },
        {
            "id": 2,
            "timestamp": datetime.now().isoformat(),
            "session_id": "sess_001",
            "operation": "read",
            "path": "/etc/passwd",
            "inode": 101
        },
        {
            "id": 3,
            "timestamp": datetime.now().isoformat(),
            "session_id": "sess_001",
            "operation": "write",
            "path": "/root/.ssh/authorized_keys",
            "inode": 102
        }
    ]
    
    for event in test_events:
        analysis = processor.process_event(event)
        print(f"\nEvent {event['id']}: {event['operation']} {event['path']}")
        print(f"  Patterns: {analysis['patterns']}")
        print(f"  Risk: {analysis['risk_level']} (score: {analysis['risk_score']})")
        print(f"  Tags: {analysis['tags']}")
    
    print(f"\n\nSession Summary:")
    summary = processor.get_session_summary("sess_001")
    print(json.dumps(summary, indent=2))
