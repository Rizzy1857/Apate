"""Execute the versioned machine-readable command contract."""

import json
from pathlib import Path

import pytest

from chronos.gateway.dispatcher import ASTDispatcher, SessionEnvironment
from chronos.gateway.shell_parser import ShellParser


MATRIX_PATH = Path(__file__).parents[1] / "fixtures" / "command_contract_v1.json"
MATRIX = json.loads(MATRIX_PATH.read_text())


@pytest.mark.parametrize("case", MATRIX["cases"], ids=lambda case: case["id"])
def test_command_contract_case(case, tmp_path):
    root = tmp_path / "root"
    home = root / "home" / "ubuntu"
    home.mkdir(parents=True)
    (root / "tmp").mkdir()
    for relative in case.get("setup_dirs", []):
        (home / relative).mkdir(parents=True)
    for relative, content in case.get("setup_files", {}).items():
        target = home / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    dispatcher = ASTDispatcher(SessionEnvironment(honeypot_root=str(root)))
    status, output = dispatcher.execute_sequence(ShellParser().parse(case["command"]))

    assert status == case["status"], (case["id"], output)
    if "exact" in case:
        assert output == case["exact"]
    for fragment in case.get("contains", []):
        assert fragment in output
    for fragment in case.get("not_contains", []):
        assert fragment not in output
    for relative in case.get("exists", []):
        assert (home / relative).exists()
    for relative in case.get("absent", []):
        assert not (home / relative).exists()
    for relative, content in case.get("file_contents", {}).items():
        assert (home / relative).read_text() == content


def test_matrix_identity_and_handler_coverage():
    assert MATRIX["schema_version"] == 1
    identifiers = [case["id"] for case in MATRIX["cases"]]
    assert len(identifiers) == len(set(identifiers))
    covered = {case["command"].split()[0] for case in MATRIX["cases"]}
    assert {
        "cd", "pwd", "export", "env", "printenv", "unset", "echo",
        "whoami", "id", "hostname", "uname", "free", "top", "ps",
        "ss", "df", "ls", "cat", "find", "grep", "head", "tail",
        "stat", "touch", "mkdir", "rm", "rmdir", "cp", "mv",
    } <= covered
