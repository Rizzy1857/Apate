"""
verify_phase3.py
----------------
Intelligence layer verification for Phase 2 Ubuntu-only architecture.

Tests:
  1. UbuntuProfile loads config/ubuntu.yaml correctly
  2. ArtifactPolicyEngine resolves Ubuntu file classes correctly
  3. PromptBuilder produces constraint-first Ubuntu prompts
  4. SemanticValidator correctly accepts/rejects content vs. MachineState
  5. Non-Ubuntu content (Windows, macOS, Debian) is always rejected

Replaces the old verify_phase3.py that tested the deleted MockProvider / PersonaEngine.
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from chronos.intelligence.ubuntu_profile import UbuntuProfile
from chronos.intelligence.artifact_policy import ArtifactPolicyEngine, ArtifactPolicy, infer_file_class
from chronos.intelligence.prompt_builder import PromptBuilder
from chronos.intelligence.validator import SemanticValidator

PASS = 0
FAIL = 0

def check(label: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))


def test_ubuntu_profile():
    print("\n[1] UbuntuProfile")
    p = UbuntuProfile()
    check("ubuntu_version is 24.04", p.ubuntu_version == "24.04", p.ubuntu_version)
    check("hostname present", bool(p.hostname))
    check("nginx installed", p.package_version("nginx") is not None)
    check("mysql not installed", p.package_version("mysql-server") is None)
    check("nginx service running", p.is_service_running("nginx"))
    check("mysql service NOT running", not p.is_service_running("mysql"))
    ms = p.build_machine_state()
    check("MachineState has ubuntu_version", ms.get("ubuntu_version") == "24.04")
    pkgs = json.loads(ms["installed_packages"])
    check("MachineState installed_packages is list", isinstance(pkgs, list))
    check("MachineState contains nginx", any(pkg["name"] == "nginx" for pkg in pkgs))


def test_artifact_policy():
    print("\n[2] ArtifactPolicyEngine — Ubuntu file class inference")
    # Credential files
    check("shadow → credential_file", infer_file_class("shadow", "/etc/shadow") == "credential_file")
    check(".env → credential_file",   infer_file_class(".env", "/home/ubuntu/.env") == "credential_file")
    check("authorized_keys → credential_file", infer_file_class("authorized_keys", "/home/ubuntu/.ssh/authorized_keys") == "credential_file")
    # Config files
    check("nginx.conf → config_file", infer_file_class("nginx.conf", "/etc/nginx/nginx.conf") == "config_file")
    check("sshd_config → config_file", infer_file_class("sshd_config", "/etc/ssh/sshd_config") == "config_file")
    # Log files
    check("access.log → log_file", infer_file_class("access.log", "/var/log/nginx/access.log") == "log_file")
    check("auth.log → log_file",   infer_file_class("auth.log", "/var/log/auth.log") == "log_file")
    # History
    check(".bash_history → history_file", infer_file_class(".bash_history", "/home/ubuntu/.bash_history") == "history_file")
    # Scripts
    check("deploy.sh → script_file", infer_file_class("deploy.sh", "/home/ubuntu/deploy.sh") == "script_file")
    # Notes
    check("todo.txt → notes_file", infer_file_class("todo.txt", "/home/ubuntu/todo.txt") == "notes_file")

    # Policy resolution
    engine = ArtifactPolicyEngine()
    policy = engine.resolve("nginx.conf", "/etc/nginx/nginx.conf")
    check("config_file max_lines=80", policy.max_lines == 80)
    check("config_file model=llama3:8b", policy.model == "llama3:8b")
    check("config_file validation=high", policy.validation_strictness == "high")
    check("empty category → skip_generation", ArtifactPolicy("config_file","empty",80,None,None,"high","static","llama3:8b").skip_generation)
    check("valid category → NOT skip_generation", not ArtifactPolicy("config_file","valid",80,None,None,"high","static","llama3:8b").skip_generation)


def test_prompt_builder():
    print("\n[3] PromptBuilder — constraint-first Ubuntu prompts")
    p = UbuntuProfile()
    pb = PromptBuilder()
    ms = p.build_machine_state()
    policy = ArtifactPolicy("config_file", "valid", 80, None, None, "high", "static", "llama3:8b")

    prompt = pb.build("nginx.conf", "/etc/nginx/nginx.conf", ms, policy)
    check("Prompt contains CONSTRAINTS block", "CONSTRAINTS" in prompt)
    check("Prompt contains MACHINE STATE block", "MACHINE STATE" in prompt)
    check("Prompt contains ubuntu_version", "24.04" in prompt)
    check("Prompt contains max_lines constraint", "80" in prompt)
    check("Prompt contains category instruction", "valid" in prompt.lower() or "functional" in prompt.lower())
    check("Prompt does NOT mention Debian",  "debian" not in prompt.lower())
    check("Prompt does NOT mention Windows", "windows" not in prompt.lower())
    check("Prompt does NOT mention IoT",     "iot" not in prompt.lower())

    system_prompt = pb.build_system_prompt(ms)
    check("System prompt scopes to Ubuntu 24.04", "24.04" in system_prompt)
    check("System prompt excludes Windows",   "Windows" in system_prompt)  # mentioned to exclude it
    check("System prompt is concise (<600 chars)", len(system_prompt) < 600)

    # Verify skip_generation raises ValueError
    empty_policy = ArtifactPolicy("credential_file","empty",20,None,None,"high","static","llama3:8b")
    try:
        pb.build("password.txt", "/home/ubuntu/password.txt", ms, empty_policy)
        check("PromptBuilder raises for empty category", False, "should have raised ValueError")
    except ValueError:
        check("PromptBuilder raises for empty category", True)


def test_semantic_validator():
    print("\n[4] SemanticValidator — Ubuntu constraint enforcement")
    p = UbuntuProfile()
    v = SemanticValidator()
    ms = p.build_machine_state()
    policy = ArtifactPolicy("config_file", "valid", 80, None, None, "high", "static", "llama3:8b")

    # Refusal boilerplate — must always reject
    for phrase in [
        "As an AI, I cannot generate this file.",
        "I am not able to help with that.",
        "I cannot create configuration files.",
        "```nginx\nserver {}```",  # markdown fences leaked
        "Here is the configuration file you requested:",
    ]:
        result = v.validate(phrase, policy, ms)
        check(f"REJECT refusal: '{phrase[:40]}...'", not result.accepted, result.reason)

    # Non-Ubuntu contamination — must reject
    for content, desc in [
        ("C:\\\\Windows\\\\System32", "Windows path"),
        ("powershell -Command Get-Process nginx", "PowerShell command"),
        ("yum install nginx", "yum package manager"),
        ("dnf install nginx", "dnf package manager"),
    ]:
        result = v.validate(content, policy, ms)
        check(f"REJECT non-Ubuntu: {desc}", not result.accepted, result.reason)

    # Contradiction against MachineState — must reject
    mysql_content = "server { include /etc/mysql/mysql.conf; }"
    result = v.validate(mysql_content, policy, ms)
    check("REJECT mysql contradiction (not installed)", not result.accepted, result.reason)

    apache_content = "Listen 80\nServerName web01\nInclude /etc/apache2/conf.d"
    result = v.validate(apache_content, policy, ms)
    check("REJECT apache2 contradiction (not installed)", not result.accepted, result.reason)

    # Density check — must reject if over max_lines
    long_content = "\n".join(["server_name web01;"] * 100)  # 100 lines > max 80
    result = v.validate(long_content, policy, ms)
    check("REJECT over-dense content (100 lines > max 80)", not result.accepted, result.reason)

    # Valid Ubuntu nginx config — must accept
    valid_nginx = (
        "server {\n"
        "    listen 80;\n"
        "    server_name web01;\n"
        "    root /var/www/html;\n"
        "    index index.html;\n"
        "}"
    )
    result = v.validate(valid_nginx, policy, ms)
    check("ACCEPT valid nginx config", result.accepted, result.reason)

    # Valid with installed package (nginx is installed)
    nginx_content = "upstream backend { server 127.0.0.1:8000; }"
    result = v.validate(nginx_content, policy, ms)
    check("ACCEPT nginx reference (nginx is installed)", result.accepted, result.reason)


def main():
    print("=" * 60)
    print("Phase 3 — Intelligence Layer Verification")
    print("Ubuntu-Only Architecture")
    print("=" * 60)

    test_ubuntu_profile()
    test_artifact_policy()
    test_prompt_builder()
    test_semantic_validator()

    print("\n" + "=" * 60)
    print(f"Results: {PASS} passed, {FAIL} failed")
    print("=" * 60)

    if FAIL == 0:
        print("\n[SUCCESS] Phase 3 Intelligence Verified")
        sys.exit(0)
    else:
        print(f"\n[FAILURE] {FAIL} check(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
