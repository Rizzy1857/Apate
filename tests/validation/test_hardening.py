import errno
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from chronos.core.content import mutate_content, read_blob
from chronos.core.scoped_redis import ScopedRedis
from chronos.gateway.dispatcher import ASTDispatcher, SessionEnvironment
from chronos.gateway.shell_parser import ShellParser
from chronos.intelligence.orchestrator import GenerationOrchestrator
from chronos.intelligence.ubuntu_profile import UbuntuProfile
from chronos.intelligence.validator import SemanticValidator
from chronos.core.database import Database
from chronos.core.state import StateHypervisor

PATH = "/etc/nginx/nginx.conf"


def hypervisor(client):
    db = Database.__new__(Database)
    db.client = client
    db._load_scripts()
    hv = StateHypervisor.__new__(StateHypervisor)
    hv.db, hv.redis = db, client
    return hv


def test_manifest_lua_and_shared_blob_unlink(isolated_redis):
    r = ScopedRedis(isolated_redis, "session:test:")
    hv = hypervisor(r)
    hv.initialize_filesystem()
    tmp = hv._resolve_path_sync("/tmp")
    assert tmp is not None
    a, b = hv.create_file(tmp, "a"), hv.create_file(tmp, "b")
    mutate_content(r, a, buf=b"same")
    mutate_content(r, b, buf=b"same")
    hv.atomic_unlink(tmp, "a")
    assert read_blob(r, r.hget(f"fs:inode:{b}", "content_hash")) == b"same"
    with pytest.raises(OSError):
        hv.atomic_mkdir(b, "invalid")
    with pytest.raises(OSError):
        hv.atomic_unlink(tmp, "..")
    count = r.get("fs:next_inode")
    hv.initialize_filesystem()
    assert r.get("fs:next_inode") == count
    assert isolated_redis.get("fs:next_inode") is None


def test_storage_limits_preserve_last_committed_content(isolated_redis):
    from chronos.core.content import MAX_FILE_BYTES, MAX_SESSION_BLOB_BYTES
    r = ScopedRedis(isolated_redis, 'session:budget:')
    hv = hypervisor(r)
    hv.initialize_filesystem()
    inode = hv.create_file(hv._resolve_path_sync('/tmp'), 'budget')
    block = b'x' * MAX_FILE_BYTES
    for _ in range(MAX_SESSION_BLOB_BYTES // MAX_FILE_BYTES):
        mutate_content(r, inode, buf=block)
    before = r.hgetall(f'fs:inode:{inode}')
    with pytest.raises(OSError) as full:
        mutate_content(r, inode, buf=b'y')
    assert full.value.errno == errno.ENOSPC
    with pytest.raises(OSError) as large:
        mutate_content(r, inode, buf=block + b'x')
    assert large.value.errno == errno.EFBIG
    assert r.hgetall(f'fs:inode:{inode}') == before
    assert read_blob(r, before['content_hash']) == block


def test_fuse_session_boundary_and_no_listing_generation(isolated_redis, monkeypatch):
    import uuid
    import chronos.interface.fuse as module
    from chronos.simulation.event_bus import EventBus

    monkeypatch.setattr(
        module,
        "StateHypervisor",
        lambda prefix=None: hypervisor(
            ScopedRedis(isolated_redis, prefix) if prefix else isolated_redis
        ),
    )
    monkeypatch.setattr(module.world_simulation, "event_bus", EventBus())
    pid = [101]
    monkeypatch.setattr(module, "fuse_get_context", lambda: (0, 0, pid[0]))
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    isolated_redis.set("session_pid:101", first)
    isolated_redis.set("session_pid:102", second)
    fs = module.ChronosFUSE("/mnt/honeypot")
    try:
        assert "passwd" in fs.readdir("/etc", 0)
        assert not list(isolated_redis.scan_iter(match="*fs:generating:*"))
        fd = fs.create("/tmp/secret", 0o644)
        fs.write("/tmp/secret", b"first-session", 0, fd)
        assert fs.getattr("/tmp/secret")["st_size"] == 13
        fs.truncate("/tmp/secret", 5)
        assert fs.read("/tmp/secret", 100, 0, fd) == b"first"
        fs.chmod("/tmp/secret", 0o600)
        assert fs.getattr("/tmp/secret")["st_mode"] == 0o100600
        pid[0] = 102
        assert "secret" not in fs.readdir("/tmp", 0)
        with pytest.raises(OSError):
            fs.read("/tmp/secret", 100, 0, fd)
        pid[0] = 999
        with pytest.raises(OSError):
            fs.mkdir("/denied", 0o755)
        assert not isolated_redis.exists("fs:inode:1")
    finally:
        fs.destroy("/")
        for _, gen, _ in fs._sessions.values():
            gen.close()


def seed(r, inode=100, kind="ai_backed"):
    r.hset(
        f"fs:inode:{inode}",
        mapping={"mode": 33188, "size": 0, "manifest_class": kind, "revision": 0},
    )


def generator(r, runtime=None):
    g = GenerationOrchestrator(
        r,
        UbuntuProfile(),
        runtime or Mock(generate=Mock(return_value="worker_processes 1;")),
    )
    # A fixed valid category avoids random empty policy selection in race tests.
    resolve = g.policy_engine.resolve

    def policy(*args):
        result = resolve(*args)
        result.category = "valid"
        return result

    g.policy_engine.resolve = policy
    return g


def test_two_orchestrators_deduplicate(isolated_redis):
    r = isolated_redis
    seed(r)
    runtime = Mock()
    entered, release = threading.Event(), threading.Event()

    def generate(**kw):
        entered.set()
        assert release.wait(3)
        return "worker_processes 1; http { server { root /var/www/html; } }"

    runtime.generate.side_effect = generate
    a, b = generator(r, runtime), generator(r, runtime)
    try:
        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = [
                pool.submit((a if i % 2 else b).get_or_generate, 100, PATH, "s", {})
                for i in range(20)
            ]
            assert entered.wait(3)
            release.set()
            assert {f.result() for f in futures} == {b"worker_processes 1; http { server { root /var/www/html; } }"}
        assert runtime.generate.call_count == 1
    finally:
        a.close()
        b.close()


@pytest.mark.parametrize("action", ["write", "delete", "lease_replaced"])
def test_generation_cannot_overwrite_newer_state(isolated_redis, action):
    r = isolated_redis
    seed(r)
    entered, release = threading.Event(), threading.Event()

    def generate(**kw):
        entered.set()
        assert release.wait(3)
        return "worker_processes 1;"

    g = generator(r, Mock(generate=generate))
    try:
        future = g._submit(100, PATH, "s")
        assert entered.wait(3)
        if action == "write":
            mutate_content(r, 100, buf=b"owned\xff", offset=0)
        elif action == "delete":
            r.delete("fs:inode:100")
        else:
            r.set("fs:generating:100", "successor", ex=120)
        release.set()
        if action == "delete":
            with pytest.raises(FileNotFoundError):
                future.result()
            assert not r.exists("fs:inode:100")
        elif action == "write":
            assert future.result() == b"owned\xff"
        else:
            assert future.result() is None
            assert r.get("fs:generating:100") == "successor"
    finally:
        release.set()
        g.close()


def test_empty_fallback_is_cached(isolated_redis):
    r = isolated_redis
    seed(r)
    runtime = Mock(generate=Mock(side_effect=RuntimeError("offline")))
    g = generator(r, runtime)
    g.fallback_provider.get_degraded_content = Mock(return_value=b"")
    try:
        assert g.get_or_generate(100, PATH, "s", {}) == b""
        assert g.get_or_generate(100, PATH, "s", {}) == b""
        assert runtime.generate.call_count == 2
    finally:
        g.close()


def test_runtime_path_does_not_regenerate(isolated_redis):
    seed(isolated_redis, kind="runtime")
    g = generator(isolated_redis)
    try:
        assert g.get_or_generate(100, PATH, "s", {}) == b""
        g.runtime.generate.assert_not_called()
        with pytest.raises(FileNotFoundError):
            g.get_or_generate(999, PATH, "s", {})
    finally:
        g.close()


def test_binary_truncate_and_concurrent_writes(isolated_redis):
    r = isolated_redis
    seed(r, kind="runtime")
    mutate_content(r, 100, buf=b"abcdef\xff", offset=0)
    mutate_content(r, 100, length=3)
    mutate_content(r, 100, length=5)
    assert read_blob(r, r.hget("fs:inode:100", "content_hash")) == b"abc\0\0"
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: mutate_content(r, 100, buf=b"X", offset=i), range(8)))
    assert read_blob(r, r.hget("fs:inode:100", "content_hash")) == b"XXXXXXXX"
    with pytest.raises(OSError) as err:
        mutate_content(r, 100, length=2**30)
    assert err.value.errno == errno.EFBIG


def test_session_namespaces_include_lua_transactions_and_blobs(isolated_redis):
    a, b = (ScopedRedis(isolated_redis, f"session:{s}:") for s in ["a", "b"])
    for r in (a, b):
        seed(r, kind="runtime")
    mutate_content(a, 100, buf=b"A")
    mutate_content(b, 100, buf=b"B")
    assert read_blob(a, a.hget("fs:inode:100", "content_hash")) == b"A"
    assert read_blob(b, b.hget("fs:inode:100", "content_hash")) == b"B"
    a.eval("redis.call('SET', 'fs:test', 'x')", 0)
    assert a.get("fs:test") == "x"
    assert b.get("fs:test") is None
    assert isolated_redis.hgetall("fs:inode:100") == {}


def test_command_profile_consistency(tmp_path):
    root = tmp_path / 'root'
    home = root / 'home/ubuntu'
    home.mkdir(parents=True)
    sample = home / 'sample'
    sample.write_bytes(b'hello\n')
    sample.chmod(0o640)
    env = SessionEnvironment(honeypot_root=str(root))
    dispatcher = ASTDispatcher(env)

    def run(command):
        code, output = dispatcher.execute_sequence(ShellParser().parse(command))
        assert code == 0, output
        return output

    assert run('id -u') == '1000\n'
    assert run('id -un') == 'ubuntu\n'
    assert run('id -g root') == '0\n'
    assert run('id -gn root') == 'root\n'
    expected = {str(g['gid']) for g in env.profile.groups
                if 'ubuntu' in g.get('members', []) or int(g['gid']) == 1000}
    assert set(run('id -G').split()) == expected
    assert dispatcher.execute_sequence(ShellParser().parse('id -z'))[0] != 0
    listing = run('ls -l sample')
    metadata = run('stat sample')
    assert listing.startswith('-rw-r----- ')
    assert listing.split()[4] == str(len(run('cat sample').encode())) == '6'
    assert 'Size: 6' in metadata and '(0640/-rw-r-----)' in metadata
    top = run('top')
    ps = run('ps aux')
    top_rows = top.split('PID USER S COMMAND\n')[1].splitlines()
    ps_rows = ps.splitlines()[1:]
    assert f'Tasks: {len(top_rows)} total' in top
    assert len(top_rows) == len(ps_rows)
    for top_row, ps_row in zip(top_rows[:-1], ps_rows[:-1]):
        pid, user, state, command = top_row.split()
        assert ps_row.split() == [user, pid, state, command]
    for port in env.profile.open_ports:
        assert f"0.0.0.0:{port['port']} " in run('ss')


def test_paths_and_short_head(tmp_path):
    root = tmp_path / "root"
    (root / "home/ubuntu").mkdir(parents=True)
    (root / "home/ubuntu/small").write_text("one\ntwo\n")
    secret = tmp_path / "secret"
    secret.write_text("host secret")
    (root / "escape").symlink_to(secret)
    env = SessionEnvironment(honeypot_root=str(root))
    dispatcher = ASTDispatcher(env)

    def run(cmd):
        return dispatcher.execute_sequence(ShellParser().parse(cmd))

    assert run("head small") == (0, "one\ntwo\n")
    assert run("cat small > small") == (0, "")
    assert (root / "home/ubuntu/small").read_bytes() == b""
    assert run("cd / > /missing/output")[0] == 1
    assert env.cwd == "/home/ubuntu"
    assert run("cat /escape")[0] != 0
    assert "host secret" not in run("cat /escape")[1]
    assert run("export PWD=relative; pwd")[1].strip() == "/home/ubuntu"
    assert run("bash -c id")[0] == 127
    assert env.resolve_path("../../../../secret") == str(root / "secret")


@pytest.mark.parametrize(
    "value",
    [None, {}, "x" * 65537, "one\ntwo\nthree", "a\0b"],
    ids=["none", "object", "oversize", "line_limit", "nul"],
)
def test_model_output_hard_limits(isolated_redis, value):
    g = generator(isolated_redis)
    try:
        policy = g.policy_engine.resolve("x", PATH, {})
        policy.max_lines = 2
        policy.validation_strictness = "low"
        assert not SemanticValidator().validate(value, policy, {}).accepted
    finally:
        g.close()
