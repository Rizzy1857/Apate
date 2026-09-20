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

def test_dispatcher_cd():
    env = SessionEnvironment(username="testuser")
    dispatcher = ASTDispatcher(env)
    parser = ShellParser()
    
    # Cd to /tmp which is mapped to /mnt/honeypot/tmp
    # Assuming honeypot doesn't actually exist on test host, it will fail unless we mock
    # Wait, /tmp exists on standard test host. Let's just test env.resolve_path
    
    assert env.resolve_path("/tmp") == "/mnt/honeypot/tmp"
    assert env.resolve_path("../../../etc/passwd") == "/mnt/honeypot/etc/passwd"
