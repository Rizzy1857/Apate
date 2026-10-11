"""Executable fixtures for docs/COMMAND_CONTRACT_V1.md."""

from pathlib import Path

import pytest

from chronos.gateway.dispatcher import ASTDispatcher, SessionEnvironment
from chronos.gateway.shell_parser import ParserError, ShellParser


@pytest.fixture
def shell(tmp_path):
    home = tmp_path / "home" / "ubuntu"
    home.mkdir(parents=True)
    (home / "input").write_text("alpha\nbeta\n")
    dispatcher = ASTDispatcher(SessionEnvironment(honeypot_root=str(tmp_path)))

    def run(command):
        return dispatcher.execute_sequence(ShellParser().parse(command))

    run.dispatcher = dispatcher
    return run, home


@pytest.mark.parametrize(
    ("command", "status", "fragment"),
    [
        ("pwd", 0, "/home/ubuntu"),
        ("echo '$HOME' \"$USER\"", 0, "$HOME ubuntu"),
        ("id -un", 0, "ubuntu"),
        ("uname -a", 0, "Linux"),
        ("ps aux", 0, "COMMAND"),
        ("grep beta input", 0, "beta"),
        ("head -n 1 input", 0, "alpha"),
        ("printf-not-supported", 127, "command not found"),
        ("bash -c id", 127, "command not found"),
    ],
)
def test_reference_results(shell, command, status, fragment):
    run, _ = shell
    code, output = run(command)
    assert code == status
    assert fragment in output


def test_supported_composition_redirection_and_effects(shell):
    run, home = shell
    assert run("grep alpha input | head -n 1 > selected; cat selected") == (
        0,
        "alpha\n",
    )
    assert (home / "selected").read_text() == "alpha\n"
    assert run("missing 2> error || cat error") == (
        0,
        "bash: missing: command not found\n",
    )
    assert run("mkdir -p tree/child && cp -r tree copied && rm -fr copied") == (
        0,
        "",
    )
    assert (home / "tree" / "child").is_dir()
    assert not (home / "copied").exists()


def test_compound_and_pipeline_stages_preserve_failures(shell):
    run, _ = shell
    dispatcher = run.dispatcher
    sequence = ShellParser().parse("missing | echo recovered; false-missing && echo hidden")
    code, output, pipelines = dispatcher.execute_sequence_with_stages(sequence)
    assert code == 127
    assert "recovered\n" in output
    assert [stage["exit_status"] for stage in pipelines[0]["stages"]] == [127, 0]
    assert pipelines[1]["executed"] is True
    assert pipelines[1]["stages"][0]["exit_status"] == 127
    assert pipelines[2]["executed"] is False
    assert pipelines[2]["skip_reason"] == "previous_status_nonzero"


@pytest.mark.parametrize(
    "command",
    [
        "pwd extra",
        "uname -s",
        "ls -z",
        "ls input selected",
        "find . -name input",
        "cat -n input",
        "stat -c x input",
        "touch -c input",
        "mkdir -m 700 private",
        "rm -z input",
        "cp input copied extra",
        "mv input moved extra",
        "export INVALID-NAME=value",
        "unset INVALID-NAME",
    ],
)
def test_unsupported_options_and_arities_fail_explicitly(shell, command):
    run, _ = shell
    code, output = run(command)
    assert code != 0, (command, output)
    assert any(
        marker in output
        for marker in ("unsupported", "not supported", "invalid", "missing")
    )


@pytest.mark.parametrize(
    "command",
    ["echo $(id)", "echo `id`", "echo hi &", "echo hi 2>&1", "echo hi |"],
)
def test_unsupported_grammar_is_rejected(command):
    with pytest.raises(ParserError):
        ShellParser().parse(command)


def test_parser_resource_limits():
    with pytest.raises(ParserError, match="command length limit"):
        ShellParser().parse("x" * 65537)
    with pytest.raises(ParserError, match="token limit"):
        ShellParser().parse("echo " + " ".join("x" for _ in range(512)))


def test_path_traversal_stays_in_virtual_root(shell, tmp_path):
    run, home = shell
    outside = tmp_path.parent / "mirage-contract-outside"
    outside.write_text("host-only")
    try:
        code, output = run("cat ../../../../mirage-contract-outside")
        assert code != 0
        assert "host-only" not in output
        assert home.is_dir()
    finally:
        outside.unlink()
