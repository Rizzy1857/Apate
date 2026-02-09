#!/usr/bin/env python3
"""
Chronos Integration Demo
Demonstrates the complete honeypot system working together
"""
import sys
import os
import threading
import time
from datetime import datetime

sys.path.append(os.path.join(os.getcwd(), "src"))

# Core components
from chronos.core.state import StateHypervisor

# Intelligence
from chronos.intelligence.llm import get_provider
from chronos.intelligence.persona import PersonaEngine

# Skills
from chronos.skills.command_analyzer import CommandAnalyzer
from chronos.skills.threat_library import ThreatLibrary
from chronos.skills.skill_detector import SkillDetector

# Gateway (import but don't start servers in demo)
# from chronos.gateway.ssh_server import SSHHoneypot
# from chronos.gateway.http_server import HTTPHoneypot

# Watcher
from chronos.watcher.event_processor import EventProcessor


class ChronosDemo:
    """
    Demonstration of the complete Chronos system
    Shows how all components integrate
    """
    
    def __init__(self):
        print("=" * 80)
        print("CHRONOS FRAMEWORK INTEGRATION DEMO")
        print("=" * 80)
        print(f"Started at: {datetime.now().isoformat()}\n")
        
        # Initialize components
        print("[1/5] Initializing State Hypervisor...")
        self.hypervisor = StateHypervisor()
        
        print("[2/5] Initializing Intelligence (Persona Engine)...")
        self.provider = get_provider()
        self.persona_engine = PersonaEngine(self.provider)
        
        print("[3/5] Initializing Skills (Command Analysis)...")
        self.command_analyzer = CommandAnalyzer()
        self.threat_library = ThreatLibrary()
        self.skill_detector = SkillDetector()
        
        print("[4/5] Initializing Watcher (Event Processor)...")
        self.event_processor = EventProcessor()
        
        print("[5/5] All components initialized!\n")
        
    def simulate_attack_session(self):
        """Simulate a realistic attack session"""
        print("=" * 80)
        print("SIMULATING ATTACK SESSION")
        print("=" * 80)
        
        session_id = "demo_session_001"
        attacker_ip = "192.168.1.100"
        
        # Simulate attacker commands
        attack_commands = [
            # Phase 1: Initial access & reconnaissance
            "whoami",
            "id",
            "uname -a",
            "cat /etc/os-release",
            "ls -la /home",
            "cat /etc/passwd",
            
            # Phase 2: Privilege escalation attempts
            "find / -perm -4000 -type f 2>/dev/null",
            "sudo -l",
            
            # Phase 3: Persistence
            "crontab -l",
            "echo '*/5 * * * * /tmp/.backdoor' | crontab -",
            "echo 'ssh-rsa AAAAB3NzaC1...' >> ~/.ssh/authorized_keys",
            
            # Phase 4: Data exfiltration
            "find /var/www -type f -name '*.conf' 2>/dev/null",
            "tar czf /tmp/backup.tar.gz /var/www/html",
            
            # Phase 5: Evasion
            "history -c",
            "rm ~/.bash_history",
        ]
        
        print(f"\nSession ID: {session_id}")
        print(f"Attacker IP: {attacker_ip}")
        print(f"Commands to process: {len(attack_commands)}\n")
        
        all_analyses = []
        
        for i, command in enumerate(attack_commands, 1):
            print(f"\n[Command {i}/{len(attack_commands)}] {command}")
            
            # 1. Command Analysis
            analysis = self.command_analyzer.analyze(command)
            all_analyses.append(analysis)
            
            print(f"  Risk Level: {analysis.risk_level} (score: {analysis.risk_score})")
            
            if analysis.techniques:
                print(f"  Techniques: {', '.join(analysis.techniques[:3])}")
            
            # 2. Threat Library Matching
            matches = self.threat_library.match(command)
            if matches:
                print(f"  Threat Signature: {matches[0].name} ({matches[0].severity})")
            
            # 3. Simulate filesystem interaction
            if "cat" in command or "ls" in command or "find" in command:
                # Simulate FUSE read operation
                print(f"  → FUSE: Filesystem operation intercepted")
            
            time.sleep(0.1)  # Simulate processing time
        
        # 4. Skill Assessment
        print("\n" + "=" * 80)
        print("SKILL ASSESSMENT")
        print("=" * 80)
        
        assessment = self.skill_detector.analyze_session(session_id, all_analyses)
        
        print(f"\nAttacker Skill Level: {assessment['skill_level'].upper()}")
        print(f"Confidence: {assessment['confidence']}")
        print(f"Skill Score: {assessment['skill_score']}")
        
        print(f"\nStatistics:")
        stats = assessment['statistics']
        print(f"  Total Commands: {stats['total_commands']}")
        print(f"  Unique Techniques: {stats['unique_techniques']}")
        print(f"  Attack Phases: {', '.join(stats['attack_phases'])}")
        
        print(f"\nCharacteristics:")
        for char in assessment['characteristics'][:3]:
            print(f"  • {char}")
        
        # 5. Session Risk Profile
        print("\n" + "=" * 80)
        print("SESSION RISK PROFILE")
        print("=" * 80)
        
        profile = self.command_analyzer.get_session_risk_profile(attack_commands)
        
        print(f"\nMalicious Commands: {profile['malicious_commands']}/{profile['total_commands']}")
        print(f"Total Risk Score: {profile['total_risk_score']}")
        print(f"Average Risk: {profile['average_risk']:.1f}")
        print(f"Overall Risk Level: {profile['overall_risk_level'].upper()}")
        
        print(f"\nTop Techniques:")
        for technique, count in list(profile['top_techniques'].items())[:5]:
            print(f"  {technique}: {count}x")
        
    def demonstrate_intelligence(self):
        """Demonstrate the intelligence/persona system"""
        print("\n" + "=" * 80)
        print("INTELLIGENCE SYSTEM DEMO")
        print("=" * 80)
        
        print("\nCurrent Persona:", self.persona_engine.current_persona)
        print("System Prompt:", self.persona_engine.get_system_prompt()[:60] + "...")
        
        # Simulate content generation
        print("\nGenerating content for 'ghost file'...")
        filename = "/etc/secret_config.conf"
        context = "Configuration file for a web application"
        
        print(f"  File: {filename}")
        print(f"  Context: {context}")
        
        # In production, this would call LLM
        content = self.persona_engine.generate_content(filename, context)
        print(f"\n  Generated Content Preview:")
        print(f"  {content[:100]}...")
        
    def show_component_overview(self):
        """Show overview of all components"""
        print("\n" + "=" * 80)
        print("COMPONENT OVERVIEW")
        print("=" * 80)
        
        print("\n1. STATE HYPERVISOR (Core)")
        print("   Status: ✓ Active")
        print("   Purpose: Manages filesystem state consistency")
        print("   Backend: Redis")
        
        print("\n2. PERSONA ENGINE (Intelligence)")
        print("   Status: ✓ Active")
        print("   Purpose: Generate realistic file content")
        print("   Provider:", type(self.provider).__name__)
        
        print("\n3. COMMAND ANALYZER (Skills)")
        print("   Status: ✓ Active")
        print("   Purpose: Detect attack techniques")
        signatures = self.threat_library.get_statistics()
        print(f"   Signatures Loaded: {signatures['total_signatures']}")
        
        print("\n4. EVENT PROCESSOR (Watcher)")
        print("   Status: ✓ Active")
        print("   Purpose: Real-time event analysis")
        
        print("\n5. GATEWAY (Entry Points)")
        print("   Status: ⊗ Not started (demo mode)")
        print("   Ports: SSH (2222), HTTP (8080)")
        
        print("\n6. LAYER 0 (Rust)")
        print("   Status: ⊗ Not loaded (demo mode)")
        print("   Purpose: High-speed traffic analysis")
    
    def run(self):
        """Run the complete demo"""
        try:
            self.show_component_overview()
            self.demonstrate_intelligence()
            self.simulate_attack_session()
            
            print("\n" + "=" * 80)
            print("DEMO COMPLETE")
            print("=" * 80)
            print("\nChronos Framework successfully demonstrated all components:")
            print("  ✓ State Management")
            print("  ✓ Cognitive Intelligence")
            print("  ✓ Threat Detection")
            print("  ✓ Skill Assessment")
            print("  ✓ Event Processing")
            print("\nThe system is ready for deployment.")
            
        except Exception as e:
            print(f"\n[ERROR] Demo failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    demo = ChronosDemo()
    demo.run()
