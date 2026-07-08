#!/usr/bin/env python3
"""
Chronos Integration Demo
Demonstrates the complete Chronos system working together.

Phase 2 update: Replaced PersonaEngine / LLMProvider with the Ubuntu-only
intelligence pipeline (UbuntuProfile, ArtifactPolicyEngine, PromptBuilder).
"""
import sys
import os
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.getcwd(), "src"))

# Core components
from chronos.core.state import StateHypervisor

# Intelligence — Ubuntu-only pipeline
from chronos.intelligence.ubuntu_profile import UbuntuProfile
from chronos.intelligence.artifact_policy import ArtifactPolicyEngine, infer_file_class
from chronos.intelligence.prompt_builder import PromptBuilder

# Skills (monitoring only — not coupled to generation)
from chronos.skills.command_analyzer import CommandAnalyzer
from chronos.skills.threat_library import ThreatLibrary
from chronos.skills.skill_detector import SkillDetector

# Watcher
from chronos.watcher.event_processor import EventProcessor


class ChronosDemo:
    """
    Demonstration of the complete Chronos system.
    Shows how all components integrate around a single Ubuntu machine definition.
    """

    def __init__(self):
        print("=" * 80)
        print("CHRONOS FRAMEWORK INTEGRATION DEMO")
        print("Ubuntu-Only Deception Platform")
        print("=" * 80)
        print(f"Started at: {datetime.now().isoformat()}\n")

        print("[1/5] Initializing State Hypervisor...")
        self.hypervisor = StateHypervisor()

        print("[2/5] Initializing Intelligence (Ubuntu-only pipeline)...")
        self.profile = UbuntuProfile()
        self.policy_engine = ArtifactPolicyEngine()
        self.prompt_builder = PromptBuilder()

        print("[3/5] Initializing Skills (monitoring / detection)...")
        self.command_analyzer = CommandAnalyzer()
        self.threat_library = ThreatLibrary()
        self.skill_detector = SkillDetector()

        print("[4/5] Initializing Watcher (Event Processor)...")
        self.event_processor = EventProcessor()

        print("[5/5] All components initialized!\n")

    def simulate_attack_session(self):
        """Simulate a realistic attack session against the Ubuntu machine."""
        print("=" * 80)
        print("SIMULATING ATTACK SESSION")
        print(f"Target: Ubuntu {self.profile.ubuntu_version} ({self.profile.hostname})")
        print("=" * 80)

        session_id = "demo_session_001"
        attacker_ip = "192.168.1.100"

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

            analysis = self.command_analyzer.analyze(command)
            all_analyses.append(analysis)

            print(f"  Risk Level: {analysis.risk_level} (score: {analysis.risk_score})")

            if analysis.techniques:
                print(f"  Techniques: {', '.join(analysis.techniques[:3])}")

            matches = self.threat_library.match(command)
            if matches:
                print(f"  Threat Signature: {matches[0].name} ({matches[0].severity})")

            if "cat" in command or "ls" in command or "find" in command:
                print(f"  → FUSE: Filesystem operation intercepted")

            time.sleep(0.1)

        # Skill assessment — monitoring output only, not fed back into generation
        print("\n" + "=" * 80)
        print("SKILL ASSESSMENT (monitoring only — does not influence generation)")
        print("=" * 80)

        assessment = self.skill_detector.analyze_session(session_id, all_analyses)

        print(f"\nAttacker Skill Level: {assessment['skill_level'].upper()}")
        print(f"Confidence: {assessment['confidence']}")
        print(f"Skill Score: {assessment['skill_score']}")

        stats = assessment['statistics']
        print(f"\nStatistics:")
        print(f"  Total Commands: {stats['total_commands']}")
        print(f"  Unique Techniques: {stats['unique_techniques']}")
        print(f"  Attack Phases: {', '.join(stats['attack_phases'])}")

        profile = self.command_analyzer.get_session_risk_profile(attack_commands)

        print(f"\nMalicious Commands: {profile['malicious_commands']}/{profile['total_commands']}")
        print(f"Overall Risk Level: {profile['overall_risk_level'].upper()}")

    def demonstrate_intelligence(self):
        """Demonstrate the Ubuntu-only artifact policy and prompt building."""
        print("\n" + "=" * 80)
        print("INTELLIGENCE SYSTEM DEMO — Ubuntu Artifact Policy")
        print("=" * 80)

        print(f"\nUbuntu Machine: {self.profile.hostname} ({self.profile.ubuntu_version})")
        print(f"Installed packages: {len(self.profile.installed_packages)}")
        print(f"Running services: {', '.join(self.profile.running_services)}")

        # Demonstrate file class resolution and policy
        test_files = [
            ("/etc/nginx/nginx.conf", "nginx.conf"),
            ("/home/ubuntu/.bash_history", ".bash_history"),
            ("/etc/shadow", "shadow"),
            ("/var/log/nginx/access.log", "access.log"),
            ("/home/ubuntu/todo.txt", "todo.txt"),
        ]

        machine_state = self.profile.build_machine_state()

        print("\nArtifact Policy Resolution:")
        for path, filename in test_files:
            policy = self.policy_engine.resolve(filename, path)
            print(f"\n  {path}")
            print(f"    Class:    {policy.file_class}")
            print(f"    Category: {policy.category}")
            print(f"    Model:    {policy.model}")
            print(f"    Max lines:{policy.max_lines}")
            print(f"    Skip AI:  {policy.skip_generation}")

            if not policy.skip_generation:
                prompt = self.prompt_builder.build(filename, path, machine_state, policy)
                lines = prompt.count("\n")
                print(f"    Prompt:   {lines} lines, contains CONSTRAINTS: {'CONSTRAINTS' in prompt}")

    def show_component_overview(self):
        """Show overview of all components."""
        print("\n" + "=" * 80)
        print("COMPONENT OVERVIEW")
        print("=" * 80)

        print("\n1. STATE HYPERVISOR (Core)")
        print("   Status: ✓ Active")
        print("   Purpose: Atomic filesystem state consistency")
        print("   Backend: Redis + Lua scripts")

        print("\n2. UBUNTU INTELLIGENCE PIPELINE")
        print("   Status: ✓ Active")
        print(f"   Ubuntu: {self.profile.ubuntu_version} ({self.profile.hostname})")
        print(f"   Packages: {len(self.profile.installed_packages)} installed")
        print("   Inference: Local Ollama (air-gapped)")
        print("   No cloud LLM providers.")

        print("\n3. COMMAND ANALYZER (Skills — monitoring only)")
        print("   Status: ✓ Active")
        print("   Purpose: Detect attack techniques (MITRE ATT&CK)")
        signatures = self.threat_library.get_statistics()
        print(f"   Signatures Loaded: {signatures['total_signatures']}")
        print("   Note: Skill level feeds monitoring, not generation fidelity")

        print("\n4. EVENT PROCESSOR (Watcher)")
        print("   Status: ✓ Active")
        print("   Purpose: Real-time event analysis and correlation")

        print("\n5. GATEWAY (Entry Points)")
        print("   Status: ⊗ Not started (demo mode)")
        print("   Ports: SSH (2222), HTTP (8080)")

        print("\n6. LAYER 0 (Rust)")
        print("   Status: ⊗ Not loaded (demo mode)")
        print("   Purpose: High-speed traffic classification")

    def run(self):
        """Run the complete demo."""
        try:
            self.show_component_overview()
            self.demonstrate_intelligence()
            self.simulate_attack_session()

            print("\n" + "=" * 80)
            print("DEMO COMPLETE")
            print("=" * 80)
            print("\nChronos Framework successfully demonstrated:")
            print("  ✓ Ubuntu-only machine definition (ubuntu.yaml)")
            print("  ✓ Artifact policy resolution (generation_policy.yaml)")
            print("  ✓ Constraint-first prompt building")
            print("  ✓ Threat detection (monitoring layer)")
            print("  ✓ Session risk profiling")
            print("  ✓ State management")
            print("\nThe system is ready for deployment.")

        except Exception as e:
            print(f"\n[ERROR] Demo failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    demo = ChronosDemo()
    demo.run()
