"""Evidence-linked session pattern summaries without expertise inference."""

from collections import Counter
import logging
import os
import shlex
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class PatternSummarizer:
    """Build an observable-pattern summary.

    The former implementation assigned attacker skill tiers from command text.
    Those tiers were not validated measurements. This class deliberately emits
    observations only; the stored database column retains its legacy name until
    a schema migration is justified.
    """

    TOOL_NAMES = frozenset({
        "curl", "empire", "linpeas", "metasploit", "nc", "netcat", "nmap",
        "pspy", "scp", "ssh", "wget",
    })
    CONTROL_OPERATORS = frozenset({"|", "||", "&&", ";"})

    def __init__(self):
        self.session_data: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def _invoked_commands(cls, command: str) -> List[str]:
        """Return command-position words; quoted argument mentions do not count."""
        try:
            lexer = shlex.shlex(command, posix=True, punctuation_chars="|;&")
            lexer.whitespace_split = True
            tokens = list(lexer)
        except ValueError:
            return []

        invoked = []
        expect_command = True
        for token in tokens:
            if token in cls.CONTROL_OPERATORS:
                expect_command = True
            elif expect_command:
                # Assignments can precede a command. Redirection-only fragments
                # are intentionally not interpreted here.
                if "=" in token and not token.startswith(("/", "./")):
                    continue
                invoked.append(os.path.basename(token))
                expect_command = False
        return invoked

    def analyze_session(self, session_id: str, command_analyses: List[Any]) -> Dict[str, Any]:
        """Summarize directly observable patterns from the supplied snapshot."""
        commands = [str(item.command) for item in command_analyses]
        technique_evidence: Dict[str, List[int]] = {}
        phases: Dict[str, List[int]] = {}
        invoked_tools: Dict[str, List[int]] = {}
        compound_indexes = []
        redirect_indexes = []

        for index, analysis in enumerate(command_analyses, start=1):
            for technique in sorted(set(analysis.techniques)):
                technique_evidence.setdefault(technique, []).append(index)
                phase = technique.split(".", 1)[0]
                phases.setdefault(phase, []).append(index)
            for tool in self._invoked_commands(str(analysis.command)):
                if tool in self.TOOL_NAMES:
                    invoked_tools.setdefault(tool, []).append(index)
            metadata = getattr(analysis, "metadata", {}) or {}
            if metadata.get("has_pipe") or any(op in analysis.command for op in ("&&", ";")):
                compound_indexes.append(index)
            if metadata.get("has_redirect"):
                redirect_indexes.append(index)

        counts = Counter(commands)
        repeated = [
            {"command": command, "count": count}
            for command, count in sorted(counts.items()) if count > 1
        ]
        labels = []
        if technique_evidence:
            labels.append("rule_matches_observed")
        if invoked_tools:
            labels.append("named_tools_invoked")
        if compound_indexes:
            labels.append("compound_shell_syntax_observed")
        if redirect_indexes:
            labels.append("redirection_observed")
        if repeated:
            labels.append("repeated_commands_observed")

        assessment = {
            "schema_version": 2,
            "assessment_type": "observable_session_patterns",
            "session_id": session_id,
            "pattern_labels": labels,
            "observations": {
                "technique_rule_matches": [
                    {"technique": name, "command_indexes": indexes}
                    for name, indexes in sorted(technique_evidence.items())
                ],
                "phase_rule_matches": [
                    {"phase": name, "command_indexes": sorted(set(indexes))}
                    for name, indexes in sorted(phases.items())
                ],
                "invoked_tools": [
                    {"tool": name, "command_indexes": indexes}
                    for name, indexes in sorted(invoked_tools.items())
                ],
                "compound_syntax_command_indexes": compound_indexes,
                "redirection_command_indexes": redirect_indexes,
                "repeated_commands": repeated,
            },
            "statistics": {
                "total_commands": len(commands),
                "unique_command_texts": len(counts),
                "unique_technique_rule_matches": len(technique_evidence),
                "phase_categories_observed": sorted(phases),
            },
            "limitations": [
                "Labels describe recorded command text and deterministic rule matches only.",
                "Rule matches do not establish intent, success, identity, or expertise.",
                "Phase categories are an unordered set; no attack progression is inferred.",
                "No timing or manual-versus-automated behavior is inferred without timestamps.",
            ],
        }
        self.session_data[session_id] = assessment
        logger.info("[PatternSummary] Session %s: %d labels", session_id, len(labels))
        return assessment
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        assessment = self.session_data.get(session_id)
        if assessment is None:
            return {"error": "Session not found"}
        return assessment


# Backward-compatible import for older scripts. New code must use PatternSummarizer.
SkillDetector = PatternSummarizer
