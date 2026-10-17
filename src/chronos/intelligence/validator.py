"""
validator.py
------------
Semantic output validation / Anti-Slop Gate.

Runs after generation, before persistence.
Checks generated content against the Ubuntu MachineState and the artifact policy.

Validation is structured in three tiers:
  1. Refusal boilerplate detection  (always checked)
  2. Ubuntu convention checks        (always checked)
  3. Contradiction checks            (checked when validation_strictness is 'high' or 'medium')
  4. Information density checks      (checked when validation_strictness is 'high')

Flow:
  ACCEPT → persist
  REJECT → retry once → on second failure, fall back to static template

All rejections are logged with reason, inode, and file class for policy tuning.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Dict

from chronos.intelligence.artifact_policy import ArtifactPolicy


# Refusal boilerplate patterns — common LLM refusal phrases
_REFUSAL_PATTERNS = [
    re.compile(r"as an ai", re.I),
    re.compile(r"i('m| am) (not able|unable)", re.I),
    re.compile(r"i cannot (generate|create|produce|provide)", re.I),
    re.compile(r"(this|that) (is|would be) (inappropriate|unethical|harmful)", re.I),
    re.compile(r"i('d| would) (not|never) (recommend|suggest|advise)", re.I),
    re.compile(r"i (must|need to) (warn|caution|advise)", re.I),
    re.compile(r"```", re.I),       # Markdown code fences leaked into output
    re.compile(r"^here (is|are) (the|a|an)", re.I | re.MULTILINE),
]

# Ubuntu version → expected kernel major version ranges
_UBUNTU_KERNEL_MAP = {
    "24.04": (6, 8),
    "22.04": (5, 15),
    "20.04": (5, 4),
    "18.04": (4, 15),
}


@dataclass
class ValidationResult:
    accepted: bool
    reason: str = ""


class SemanticValidator:
    """
    Validates generated content against the Ubuntu MachineState and artifact policy.
    A rejection means the content must be retried or replaced with a static template.
    """

    def validate(
        self,
        content: str,
        policy: "ArtifactPolicy",
        machine_state: Dict[str, Any],
    ) -> ValidationResult:
        """Run all applicable validation checks and return a ValidationResult."""

        if not isinstance(content, str):
            return ValidationResult(accepted=False, reason="invalid_content_type")
        if len(content.encode('utf-8')) > 65536 or '\x00' in content:
            return ValidationResult(accepted=False, reason="invalid_content_size_or_nul")
        if not content.strip() and not policy.skip_generation:
            return ValidationResult(
                accepted=False, reason="empty_content_for_nonempty_category"
            )
        # Bash history stores commands, not an interactive terminal transcript.
        # Reject prompts regardless of strictness: they can contradict the
        # owning user's persona and reveal generated rather than native data.
        if policy.file_class == 'history_file':
            if re.search(r'(?m)^\s*(?:[\w.-]+@[\w.-]+:[^\n]*[#$]|[#$])\s+', content):
                return ValidationResult(False, 'history: shell prompt is not a stored command')
        if policy.file_class == 'log_file' and content.strip() and machine_state.get('created_at'):
            from datetime import datetime, timezone, timedelta
            reference = datetime.fromtimestamp(float(machine_state['created_at']), timezone.utc)
            dates = re.findall(r'(?m)^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})', content)
            for stamp in dates:
                try:
                    candidates = [datetime.strptime(f'{year} {stamp}', '%Y %b %d %H:%M:%S').replace(tzinfo=timezone.utc)
                                  for year in (reference.year - 1, reference.year, reference.year + 1)]
                except ValueError:
                    return ValidationResult(False, 'log: invalid timestamp')
                if not any(reference - timedelta(days=7) <= date <= reference for date in candidates):
                    return ValidationResult(False, 'log: timestamp outside simulation window')
        if machine_state.get('artifact_path') == '/etc/nginx/nginx.conf':
            if not re.search(r'\bevents\s*\{', content) or not re.search(r'\bhttp\s*\{', content):
                return ValidationResult(False, 'nginx: complete events and http contexts required')
            if content.count('{') != content.count('}'):
                return ValidationResult(False, 'nginx: unbalanced contexts')
            for required in (r'\blisten\s+80\s*;', r'\blisten\s+443\s+ssl\s*;',
                             r'\bssl_certificate\s+/etc/ssl/certs/ssl-cert-snakeoil.pem\s*;',
                             r'\bssl_certificate_key\s+/etc/ssl/private/ssl-cert-snakeoil.key\s*;'):
                if not re.search(required, content):
                    return ValidationResult(False, 'nginx: advertised HTTP/TLS configuration missing')
            # The profile describes a static web root, not an invented backend.
            if re.search(r'\b(proxy_pass|upstream|fastcgi_pass|include)\b', content):
                return ValidationResult(False, 'nginx: backend is not defined in the profile')
            manifest = json.loads(machine_state.get('filesystem_manifest', '{}'))
            paths = {entry['path'] for entry in manifest.get('entries', [])}
            for referenced in re.findall(r'\b(?:include|ssl_certificate|ssl_certificate_key)\s+([^;\s]+)', content):
                if referenced not in paths:
                    return ValidationResult(False, 'nginx: referenced file absent from manifest')
            if not re.search(r'\broot\s+/var/www/html\s*;', content):
                return ValidationResult(False, 'nginx: static web root missing')
        if machine_state.get('artifact_path') == '/var/www/html/index.html':
            if '<html' not in content.lower() or '</html>' not in content.lower():
                return ValidationResult(False, 'html: incomplete document')

        # Tier 1: Refusal boilerplate (always)
        result = self._check_refusal(content)
        if not result.accepted:
            return result

        # Tier 2: Ubuntu conventions (always)
        result = self._check_ubuntu_conventions(content, machine_state)
        if not result.accepted:
            return result

        # Tier 3: Contradiction checks (medium and high)
        if policy.validation_strictness in ("medium", "high"):
            result = self._check_contradictions(content, policy, machine_state)
            if not result.accepted:
                return result

        # Tier 4: Information density (high only)
        result = self._check_density(content, policy)
        if not result.accepted:
            return result

        return ValidationResult(accepted=True)

    # ------------------------------------------------------------------
    # Tier 1 — Refusal boilerplate
    # ------------------------------------------------------------------

    def _check_refusal(self, content: str) -> ValidationResult:
        for pattern in _REFUSAL_PATTERNS:
            if pattern.search(content):
                return ValidationResult(
                    accepted=False,
                    reason=f"refusal_boilerplate: matched pattern '{pattern.pattern}'",
                )
        return ValidationResult(accepted=True)

    # ------------------------------------------------------------------
    # Tier 2 — Ubuntu convention checks
    # ------------------------------------------------------------------

    def _check_ubuntu_conventions(
        self, content: str, machine_state: Dict[str, Any]
    ) -> ValidationResult:
        ubuntu_version = machine_state.get("ubuntu_version", "24.04")

        # Detect obvious cross-OS contamination
        non_ubuntu_markers = [
            (r"windows", "windows reference in Ubuntu file"),
            (r"powershell", "powershell reference in Ubuntu file"),
            (r"C:\\\\", "Windows path separator in Ubuntu file"),
            (r"\byum\b", "yum package manager (RHEL) in Ubuntu file"),
            (r"\bdnf\b", "dnf package manager (Fedora) in Ubuntu file"),
            (r"\bzypper\b", "zypper package manager (SUSE) in Ubuntu file"),
        ]
        for pattern, reason in non_ubuntu_markers:
            if re.search(pattern, content, re.I):
                return ValidationResult(accepted=False, reason=f"ubuntu_convention: {reason}")

        return ValidationResult(accepted=True)

    # ------------------------------------------------------------------
    # Tier 3 — Contradiction checks
    # ------------------------------------------------------------------

    def _check_contradictions(
        self, content: str, policy: "ArtifactPolicy", machine_state: Dict[str, Any]
    ) -> ValidationResult:
        # Deserialize package list if stored as JSON string
        raw_packages = machine_state.get("installed_packages", "[]")
        if isinstance(raw_packages, str):
            try:
                packages = json.loads(raw_packages)
            except json.JSONDecodeError:
                packages = []
        else:
            packages = raw_packages

        installed_names = {pkg.get("name", "").lower() for pkg in packages if isinstance(pkg, dict)}

        # Deserialize running services
        raw_services = machine_state.get("running_services", "[]")
        if isinstance(raw_services, str):
            try:
                services = json.loads(raw_services)
            except json.JSONDecodeError:
                services = []
        else:
            services = raw_services

        # Check for references to packages that are not installed
        # (Only for config files — too noisy for logs/history)
        if policy.file_class == "config_file":
            # Common daemons that should only appear if installed
            daemon_package_map = {
                "apache2": "apache2",
                "mysql": "mysql-server",
                "postgresql": "postgresql",
                "docker": "docker",
                "php": "php",
                "redis": "redis-server",
            }
            for daemon, package in daemon_package_map.items():
                if re.search(rf"\b{daemon}\b", content, re.I) and package not in installed_names:
                    return ValidationResult(
                        accepted=False,
                        reason=f"contradiction: references '{daemon}' but package '{package}' is not installed",
                    )

        return ValidationResult(accepted=True)

    # ------------------------------------------------------------------
    # Tier 4 — Information density
    # ------------------------------------------------------------------

    def _check_density(self, content: str, policy: "ArtifactPolicy") -> ValidationResult:
        """Reject content that exceeds the max_lines constraint."""
        if policy.max_entries and len(content.splitlines()) > policy.max_entries:
            return ValidationResult(accepted=False, reason='max_entries_exceeded')
        if policy.max_lines:
            line_count = len(content.splitlines())
            if line_count > policy.max_lines:
                return ValidationResult(
                    accepted=False,
                    reason=f"density: {line_count} lines exceeds max_lines={policy.max_lines}",
                )
        return ValidationResult(accepted=True)
