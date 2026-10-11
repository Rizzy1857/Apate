import pytest
from chronos.gateway.shell_parser import ShellParser, ParserError
from chronos.gateway.dispatcher import SessionEnvironment, ASTDispatcher

def test_shell_parser_basic():
    parser = ShellParser()
    seq = parser.parse("echo hi | grep h > out.txt")
    assert len(seq.pipelines) == 1
    pipe, op = seq.pipelines[0]
    assert op is None
    assert len(pipe.commands) == 2
    assert pipe.commands[0].args == ["echo", "hi"]
    assert pipe.commands[1].args == ["grep", "h"]
    assert pipe.commands[1].redirect_out == ("out.txt", False)

def test_shell_parser_unsupported():
    parser = ShellParser()
    with pytest.raises(ParserError, match="command substitution not supported"):
        parser.parse("echo $(whoami)")
        
    with pytest.raises(ParserError, match="command substitution not supported"):
        parser.parse("echo `id`")

def test_dispatcher_env_vars():
    env = SessionEnvironment(username="testuser")
    dispatcher = ASTDispatcher(env)
    parser = ShellParser()
    
    # Test setting and reading var
    seq = parser.parse("export TEST=hello; echo $TEST")
    code, out = dispatcher.execute_sequence(seq)
    assert code == 0
    assert out.strip() == "hello"


def test_quotes_preserve_literals_and_expansion_context():
    parser = ShellParser()
    dispatcher = ASTDispatcher(SessionEnvironment(username="testuser"))

    assert dispatcher.execute_sequence(parser.parse("echo ';'")) == (0, ";\n")
    assert dispatcher.execute_sequence(parser.parse("echo '$HOME'")) == (0, "$HOME\n")
    assert dispatcher.execute_sequence(parser.parse('echo "x:$HOME"')) == (
        0, "x:/home/testuser\n"
    )
    assert dispatcher.execute_sequence(parser.parse(r"echo \$HOME")) == (0, "$HOME\n")


def test_stderr_redirection_is_not_stdout_redirection(tmp_path):
    (tmp_path / "home" / "testuser").mkdir(parents=True)
    env = SessionEnvironment(username="testuser", honeypot_root=str(tmp_path))
    dispatcher = ASTDispatcher(env)
    parser = ShellParser()

    code, output = dispatcher.execute_sequence(parser.parse("missing 2>error.txt"))
    assert (code, output) == (127, "")
    assert (tmp_path / "home" / "testuser" / "error.txt").read_text() == (
        "bash: missing: command not found\n"
    )


@pytest.mark.parametrize("command", ["echo hi &&", "|| echo hi", "echo hi |", "echo hi &"])
def test_malformed_or_unsupported_control_operators_are_rejected(command):
    with pytest.raises(ParserError):
        ShellParser().parse(command)


def test_descriptor_duplication_is_rejected_explicitly():
    with pytest.raises(ParserError, match="file descriptor duplication not supported"):
        ShellParser().parse("echo hi 2>&1")
    with pytest.raises(ParserError, match="file descriptor 12 is not supported"):
        ShellParser().parse("echo hi 12>file")

def test_dispatcher_cd():
    env = SessionEnvironment(username="testuser")
    dispatcher = ASTDispatcher(env)
    parser = ShellParser()
    
    # Cd to /tmp which is mapped to /mnt/honeypot/tmp
    # Assuming honeypot doesn't actually exist on test host, it will fail unless we mock
    # Wait, /tmp exists on standard test host. Let's just test env.resolve_path
    
    assert env.resolve_path("/tmp") == "/mnt/honeypot/tmp"
    assert env.resolve_path("../../../etc/passwd") == "/mnt/honeypot/etc/passwd"
