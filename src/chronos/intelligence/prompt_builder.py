"""
prompt_builder.py
-----------------
Builds strictly constrained prompts for AI generation.

Key principles (from the design review):
- AI receives constraints, not creative latitude.
- AI must not invent world facts — it fills predefined gaps.
- Only the *relevant subgraph* of MachineState is injected (context budget).
- Filenames and paths are sanitized before interpolation (prompt-injection hardening).
- Refusal boilerplate ("As an AI...") is checked post-generation by the Validator.
"""

import json
import re
from typing import Any, Dict, Optional
from chronos.intelligence.artifact_policy import ArtifactPolicy


# Sanitize attacker-controlled path/filename before putting it in a prompt.
_DISALLOWED_PATTERN = re.compile(r"[^\w/\.\-]")


def _sanitize(value: str) -> str:
    """Strip characters that could break prompt structure."""
    return _DISALLOWED_PATTERN.sub("_", value)[:120]


# Which MachineState fields are relevant for each file class.
# Only these are injected — unused facts waste context tokens and add contradiction risk.
_RELEVANT_FIELDS: Dict[str, list] = {
    "config_file": ["ubuntu_version", "kernel_version", "hostname", "installed_packages",
                    "running_services", "open_ports", "ssh_config"],
    "credential_file": ["ubuntu_version", "users", "groups", "primary_user"],
    "log_file": ["ubuntu_version", "hostname", "running_services", "open_ports"],
    "history_file": ["ubuntu_version", "primary_user", "installed_packages", "running_services"],
    "script_file": ["ubuntu_version", "installed_packages", "running_services", "primary_user"],
    "notes_file": ["primary_user"],
    "temp_file": ["running_services", "open_ports"],
}
_DEFAULT_FIELDS = ["ubuntu_version", "hostname", "primary_user"]


# Category-specific generation instructions appended to every prompt.
_CATEGORY_INSTRUCTIONS: Dict[str, str] = {
    "valid":       "Produce a complete, functional file. Follow Ubuntu conventions exactly.",
    "deprecated":  "Produce a config with several commented-out directives and a comment noting it is from a previous deployment.",
    "broken":      "Produce a config with one subtle syntax error or a missing required directive.",
    "active":      "Produce realistic recent entries. Use plausible timestamps within the last 7 days.",
    "archived":    "Produce entries from several weeks ago. Sparse, lower volume than an active log.",
    "corrupted":   "Produce a file that appears partially written — truncated mid-line at the end, a few binary characters, or a missing closing brace.",
    "abandoned":   "Produce a file that was once used but is now stale. Add a comment like '# TODO: clean this up' or a date from over a year ago.",
    "empty":       "",  # Should never reach PromptBuilder — ArtifactPolicy.skip_generation is True
    "incomplete":  "Produce a draft file. Include TODO comments for unfinished sections.",
    "functional":  "Produce a working script. Keep it realistic for a sysadmin on Ubuntu 24.04.",
    "stale":       "Produce a file that looks like a leftover from a previous process — old PID, expired timestamp.",
    "notes":       "Produce 3–8 lines of informal personal notes. Casual language, no markdown.",
    "useful":      "Produce a short, realistic file containing plausible content for its type.",
}


class PromptBuilder:
    """
    Assembles the generation prompt from MachineState + ArtifactPolicy.
    AI receives explicit constraints — it never invents world facts.
    """

    def build(
        self,
        filename: str,
        path: str,
        machine_state: Dict[str, Any],
        policy: ArtifactPolicy,
    ) -> str:
        """
        Returns a complete prompt string ready for InferenceRuntime.generate().
        Raises ValueError if the policy indicates generation should be skipped.
        """
        if policy.skip_generation:
            raise ValueError(
                f"PromptBuilder.build() called for skip_generation=True policy: {policy}"
            )

        safe_filename = _sanitize(filename)
        safe_path = _sanitize(path)

        relevant_state = self._extract_relevant_state(machine_state, policy.file_class)
        category_instruction = _CATEGORY_INSTRUCTIONS.get(policy.category, "")
        max_lines_instruction = f"Maximum {policy.max_lines} lines." if policy.max_lines else ""

        prompt = (
            f"Generate the file '{safe_filename}' located at '{safe_path}'.\n\n"
            f"=== CONSTRAINTS ===\n"
            f"- Ubuntu {machine_state.get('ubuntu_version', '24.04')} "
            f"(kernel {machine_state.get('kernel_version', 'unknown')})\n"
            f"- {max_lines_instruction}\n"
            f"- Artifact category: {policy.category} — {category_instruction}\n"
            f"- Do NOT invent any facts that are not present in the Machine State block below.\n"
            f"- Output ONLY the raw file content. No markdown fences. No preamble. No explanation.\n\n"
            f"=== MACHINE STATE ===\n"
            f"{relevant_state}\n\n"
            f"=== OUTPUT ===\n"
            f"(Begin file content immediately below this line)"
        )
        return prompt

    def build_system_prompt(self, machine_state: Dict[str, Any]) -> str:
        """
        The system-level prompt scopes the model to Ubuntu only.
        Short and non-creative — it limits, it doesn't inspire.
        """
        hostname = machine_state.get("hostname", "ubuntu")
        version = machine_state.get("ubuntu_version", "24.04")
        user = machine_state.get("primary_user", "ubuntu")
        return (
            f"You are generating filesystem artifacts for a real Ubuntu {version} server "
            f"named '{hostname}'. The primary user is '{user}'. "
            f"You only generate content that would genuinely exist on Ubuntu {version}. "
            f"Never generate content for Windows, macOS, or other operating systems. "
            f"Never explain what you are doing. Output only file content."
        )

    def _extract_relevant_state(self, machine_state: Dict[str, Any], file_class: str) -> str:
        """
        Returns a compact, human-readable representation of only the MachineState
        fields relevant to the file class. Reduces context waste and contradiction risk.
        """
        fields = _RELEVANT_FIELDS.get(file_class, _DEFAULT_FIELDS)
        lines = []
        for field in fields:
            value = machine_state.get(field)
            if value is None:
                continue
            # Deserialize JSON strings stored in Redis
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    pass
            lines.append(f"{field}: {json.dumps(value, indent=2) if isinstance(value, (list, dict)) else value}")
        return "\n".join(lines) if lines else "(no machine state available)"
