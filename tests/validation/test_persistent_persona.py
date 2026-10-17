from concurrent.futures import ThreadPoolExecutor
import uuid

from chronos.intelligence.ubuntu_profile import UbuntuProfile
from chronos.intelligence.prompt_builder import PromptBuilder
from chronos.core.session_cleanup import delete_namespace


def test_device_survives_session_cleanup(isolated_redis):
    profile = UbuntuProfile()
    session = str(uuid.uuid4())
    first = profile.get_or_create_machine_state(isolated_redis, session)
    delete_namespace(isolated_redis, session)
    second = UbuntuProfile().get_or_create_machine_state(isolated_redis, "second")
    assert first == second
    assert second["device_purpose"]
    assert isolated_redis.exists(f"chronos:device:v1:{first['device_id']}")


def test_concurrent_persona_initialization(isolated_redis):
    with ThreadPoolExecutor(max_workers=8) as pool:
        states = list(pool.map(lambda _: UbuntuProfile().get_or_create_machine_state(
            isolated_redis, "same-session"), range(24)))
    assert all(state == states[0] for state in states)


def test_profile_change_creates_new_device_not_session_rewrite(isolated_redis):
    profile = UbuntuProfile()
    old = profile.get_or_create_machine_state(isolated_redis, "old")
    profile._raw["device_purpose"] = "Different experiment"
    assert profile.get_or_create_machine_state(isolated_redis, "old") == old
    new = profile.get_or_create_machine_state(isolated_redis, "new")
    assert new["device_id"] != old["device_id"]
    assert new["device_purpose"] == "Different experiment"


def test_notes_receive_device_and_role_grounding():
    context = PromptBuilder()._extract_relevant_state(
        UbuntuProfile().build_machine_state(), "notes_file")
    for fact in ("hostname:", "primary_user:", "device_purpose:", "user_roles:"):
        assert fact in context


def test_live_context_is_separate_and_removed_with_session(isolated_redis):
    from chronos.core.session_context import publish_context
    from chronos.gateway.dispatcher import SessionEnvironment
    sid = str(uuid.uuid4())
    env = SessionEnvironment()
    device = UbuntuProfile().get_or_create_machine_state(isolated_redis, sid)
    publish_context(isolated_redis, sid, env)
    env.cwd = "/tmp"
    env.env["USER"] = "untrusted-label"
    snapshot = publish_context(isolated_redis, sid, env, str(uuid.uuid4()))
    assert snapshot["effective_username"] == "ubuntu"
    assert snapshot["cwd"] == "/tmp"
    assert isolated_redis.hgetall(f"chronos:machine_state:{sid}") == device
    delete_namespace(isolated_redis, sid)
    assert not isolated_redis.exists(f"session:{sid}:context")
