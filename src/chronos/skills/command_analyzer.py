import re
import logging
from typing import Dict, List, Any
from dataclasses import dataclass
from chronos.core.threat_scoring import calculate_risk_level

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CommandAnalysis:
    command: str
    techniques: List[str]
    risk_score: int
    risk_level: str
    indicators: List[str]
    metadata: Dict[str, Any]


class CommandAnalyzer:
    """Analyzes shell commands for attack patterns using MITRE ATT&CK"""
    
    def __init__(self):
        self._compile_patterns()
        
    def _compile_patterns(self):
        """Compile regex patterns once for performance"""
        # Reconnaissance patterns
        self.recon_patterns = {
            'system_info': re.compile(r'\b(uname|hostname|whoami|id|uptime|arch)\b'),
            'network_scan': re.compile(r'\b(nmap|netstat|ss|ifconfig|ip\s+addr)\b'),
            'process_enum': re.compile(r'\b(ps|top|htop|pgrep|pidof)\b'),
            'user_enum': re.compile(r'\b(cat|less|more|grep)\s+.*(/etc/passwd|/etc/group|/etc/shadow)\b'),
            'service_enum': re.compile(r'\b(systemctl|service|chkconfig)\b'),
        }
        
        # Persistence patterns
        self.persistence_patterns = {
            'cron_job': re.compile(r'\b(crontab|/etc/cron)\b'),
            'ssh_key': re.compile(r'\b(ssh-keygen|authorized_keys)\b'),
            'rc_file': re.compile(r'\b(\.bashrc|\.bash_profile|\.profile|rc\.local)\b'),
            'systemd_service': re.compile(r'\b(systemctl.*enable|/etc/systemd)\b'),
            'at_job': re.compile(r'\b(at|batch)\b'),
        }
        
        # Privilege escalation patterns
        self.privesc_patterns = {
            'sudo_abuse': re.compile(r'\b(sudo|su)\b'),
            'suid_search': re.compile(r'find.*-perm.*4000'),
            'capability_search': re.compile(r'getcap.*-r'),
            'passwd_change': re.compile(r'\b(passwd|chpasswd)\b'),
            'sudoers_edit': re.compile(r'/etc/sudoers'),
        }
        
        # Lateral movement patterns
        self.lateral_patterns = {
            'ssh_connection': re.compile(r'\bssh\s+.*@'),
            'scp_transfer': re.compile(r'\bscp\b'),
            'rsync_transfer': re.compile(r'\brsync\b'),
            'network_share': re.compile(r'\b(mount|smbclient|showmount)\b'),
        }
        
        # Data exfiltration patterns
        self.exfil_patterns = {
            'wget_download': re.compile(r'\b(wget|curl).*http'),
            'base64_encode': re.compile(r'\bbase64\b'),
            'tar_archive': re.compile(r'\b(tar|zip|gzip|bzip2)\b'),
            'nc_transfer': re.compile(r'\b(nc|netcat)\b'),
            'dns_exfil': re.compile(r'\b(nslookup|dig|host).*\$'),
        }
        
        # Execution patterns
        self.execution_patterns = {
            'reverse_shell': re.compile(r'(bash.*-i|sh.*-i|/bin/(ba)?sh.*0>&1|nc.*-e)'),
            'download_execute': re.compile(r'(wget|curl).*\|.*(bash|sh|python)'),
            'encoded_command': re.compile(r'(echo.*\|.*base64.*-d|eval.*\$\()'),
            'python_execution': re.compile(r'python.*-c'),
            'perl_execution': re.compile(r'perl.*-e'),
        }
        
        # Defense evasion patterns
        self.evasion_patterns = {
            'history_clear': re.compile(r'\b(history.*-c|unset.*HISTFILE|rm.*bash_history)\b'),
            'log_clear': re.compile(r'\b(rm|truncate|>).*(/var/log|\.log)\b'),
            'process_hide': re.compile(r'\b(nohup|disown|&)\s*$'),
            'timestamp_modify': re.compile(r'\b(touch.*-t|touch.*-d)\b'),
        }
        
        # Credential access patterns
        self.credential_patterns = {
            'passwd_dump': re.compile(r'(cat|grep|awk).*/(etc/)?shadow'),
            'ssh_key_theft': re.compile(r'(cat|cp).*\.ssh/(id_rsa|id_dsa)'),
            'history_search': re.compile(r'(cat|grep).*history.*password'),
            'memory_dump': re.compile(r'\b(gcore|/proc/.*mem)\b'),
        }
        
    def analyze(self, command: str) -> CommandAnalysis:
        """Analyze shell command for malicious patterns"""
        techniques = []
        indicators = []
        risk_score = 0

        # Check patterns by category
        for technique, pattern in self.recon_patterns.items():
            if pattern.search(command):
                techniques.append(f"reconnaissance.{technique}")
                indicators.append(f"Recon: {technique}")
                risk_score += 5

        for technique, pattern in self.persistence_patterns.items():
            if pattern.search(command):
                techniques.append(f"persistence.{technique}")
                indicators.append(f"Persistence: {technique}")
                risk_score += 25

        for technique, pattern in self.privesc_patterns.items():
            if pattern.search(command):
                techniques.append(f"privilege_escalation.{technique}")
                indicators.append(f"PrivEsc: {technique}")
                risk_score += 30

        for technique, pattern in self.lateral_patterns.items():
            if pattern.search(command):
                techniques.append(f"lateral_movement.{technique}")
                indicators.append(f"Lateral: {technique}")
                risk_score += 20

        for technique, pattern in self.exfil_patterns.items():
            if pattern.search(command):
                techniques.append(f"exfiltration.{technique}")
                indicators.append(f"Exfil: {technique}")
                risk_score += 25

        for technique, pattern in self.execution_patterns.items():
            if pattern.search(command):
                techniques.append(f"execution.{technique}")
                indicators.append(f"Exec: {technique}")
                risk_score += 35

        for technique, pattern in self.evasion_patterns.items():
            if pattern.search(command):
                techniques.append(f"defense_evasion.{technique}")
                indicators.append(f"Evasion: {technique}")
                risk_score += 20

        for technique, pattern in self.credential_patterns.items():
            if pattern.search(command):
                techniques.append(f"credential_access.{technique}")
                indicators.append(f"Creds: {technique}")
                risk_score += 30

        # Metadata
        metadata = {
            'has_pipe': '|' in command,
            'has_redirect': '>' in command or '<' in command,
            'has_background': '&' in command,
            'has_variables': '$' in command,
            'command_length': len(command)
        }

        # Adjust risk for complex commands
        if metadata['has_pipe'] and len(command) > 50:
            risk_score += 5
            indicators.append("Complex piped command")

        risk_level = calculate_risk_level(risk_score)

        if techniques:
            logger.info(f"Detected {len(techniques)} techniques (Risk: {risk_level})")

        return CommandAnalysis(
            command=command,
            techniques=techniques,
            risk_score=risk_score,
            risk_level=risk_level,
            indicators=indicators,
            metadata=metadata
        )

    def batch_analyze(self, commands: List[str]) -> List[CommandAnalysis]:
        """Analyze multiple commands"""
        return [self.analyze(cmd) for cmd in commands]

    def get_session_risk_profile(self, commands: List[str]) -> Dict[str, Any]:
        """Build risk profile from session commands"""
        analyses = self.batch_analyze(commands)

        all_techniques = []
        total_risk = 0
        technique_categories = set()

        for analysis in analyses:
            all_techniques.extend(analysis.techniques)
            total_risk += analysis.risk_score
            technique_categories.update([t.split('.')[0] for t in analysis.techniques])

        from collections import Counter
        technique_counts = Counter(all_techniques)

        return {
            "total_commands": len(commands),
            "malicious_commands": len([a for a in analyses if a.techniques]),
            "total_risk_score": total_risk,
            "average_risk": total_risk / len(commands) if commands else 0,
            "unique_techniques": len(set(all_techniques)),
            "technique_categories": list(technique_categories),
            "top_techniques": dict(technique_counts.most_common(10)),
            "overall_risk_level": calculate_risk_level(total_risk // len(commands) if commands else 0)
        }
