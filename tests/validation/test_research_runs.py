import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from redis.exceptions import ResponseError

from chronos.core.research_runs import (attach_session, arm_resume, namespace_prefix,
                                       pause_session, update_run_context, NEXT)
from chronos.core.session_cleanup import delete_namespace, orphan_sessions
from chronos.intelligence.ubuntu_profile import UbuntuProfile


def sid():
    return str(uuid.uuid4())


def persona(client):
    return UbuntuProfile().get_or_create_machine_state(client, sid())


def test_explicit_resume_preserves_files_and_directory(isolated_redis):
    r = isolated_redis
    old, new = sid(), sid()
    facts = persona(r)
    run = attach_session(r, old, facts)
    prefix = namespace_prefix(r, old)
    r.set(prefix + "fs:test-marker", "retained")
    update_run_context(r, old, "/tmp")
    assert old in orphan_sessions(r)
    delete_namespace(r, old)
    assert r.hget(f"chronos:run:{run['run_id']}", "status") == "paused"
    arm_resume(r, run["run_id"])
    resumed = attach_session(r, new, facts)
    assert namespace_prefix(r, new) == prefix
    assert resumed["cwd"] == "/tmp"
    assert r.get(prefix + "fs:test-marker") == "retained"
    assert not r.exists(NEXT)


def test_fresh_connections_and_active_resume_are_isolated(isolated_redis):
    r = isolated_redis
    first, second = sid(), sid()
    facts = persona(r)
    attach_session(r, first, facts)
    attach_session(r, second, facts)
    assert namespace_prefix(r, first) != namespace_prefix(r, second)
    with pytest.raises(ResponseError, match="paused"):
        arm_resume(r, first)
    r.hset(f"chronos:run:{first}", "session_id", second)
    with pytest.raises(PermissionError):
        namespace_prefix(r, first)
    with pytest.raises(ResponseError, match="ownership"):
        update_run_context(r, first, "/tmp")
    assert pause_session(r, first) == 0


def test_resume_selection_is_consumed_by_only_one_connection(isolated_redis):
    r = isolated_redis
    facts = persona(r)
    original = sid()
    attach_session(r, original, facts)
    delete_namespace(r, original)
    arm_resume(r, original)
    with ThreadPoolExecutor(max_workers=8) as pool:
        runs = list(pool.map(lambda _: attach_session(r, sid(), facts), range(8)))
    assert sum(run["run_id"] == original for run in runs) == 1
    assert len({run["run_id"] for run in runs}) == 8


def test_resume_refuses_profile_mismatch_and_fresh_reset_retains_old_run(isolated_redis):
    r = isolated_redis
    facts = persona(r)
    original = sid()
    attach_session(r, original, facts)
    delete_namespace(r, original)
    arm_resume(r, original)
    with pytest.raises(ResponseError, match="profile"):
        attach_session(r, sid(), {**facts, "device_id": "changed"})
    r.delete(NEXT)  # Operator chooses a fresh run instead.
    fresh = attach_session(r, sid(), facts)
    assert fresh["run_id"] != original
    assert r.exists(f"chronos:run:{original}")


def test_lua_journal_replay_retains_originating_session(isolated_redis):
    from chronos.core.database import Database
    from chronos.core.state import StateHypervisor
    from chronos.core.scoped_redis import ScopedRedis
    from chronos.core.mutation_journal import journal_mapping
    from chronos.interface.fuse import ChronosFUSE

    original, resumed = sid(), sid()
    database = Database.__new__(Database)
    database.client = ScopedRedis(isolated_redis, f"run:{original}:")
    database._load_scripts()
    hv = StateHypervisor.__new__(StateHypervisor)
    hv.db, hv.redis = database, database.client
    hv.initialize_filesystem()
    journal = journal_mapping(str(uuid.uuid4()), "create", "/probe", sid(), "scripted_test")
    journal["session_id"] = original
    hv.create_file(1, "probe", journal=journal)
    receiver = ChronosFUSE.__new__(ChronosFUSE)
    receiver.db_layer = object()
    attributed = []
    receiver._audit = lambda session, *args: attributed.append(session)
    receiver._reconcile_mutations(resumed, hv)
    assert attributed == [original]
