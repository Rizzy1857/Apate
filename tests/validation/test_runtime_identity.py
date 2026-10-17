from types import SimpleNamespace

from chronos.core.runtime_identity import fingerprint_runtime
from chronos.watcher.export_report import _metadata_from_environment


def test_runtime_identity_ignores_build_cache_and_secrets_but_tracks_inputs(tmp_path):
    source = tmp_path / "src"
    config = tmp_path / "config"
    source.mkdir()
    config.mkdir()
    (source / "app.py").write_text("version = 1")
    (config / "ubuntu.yaml").write_text("hostname: web01")
    initial = fingerprint_runtime(tmp_path)
    (source / "target").mkdir()
    (source / "target" / "binary").write_bytes(b"build output")
    (tmp_path / ".env").write_text("PRIVATE_CONFIGURATION=synthetic-test")
    assert fingerprint_runtime(tmp_path) == initial
    (source / "app.py").write_text("version = 2")
    assert fingerprint_runtime(tmp_path)["APATE_SOURCE_REVISION"] != initial["APATE_SOURCE_REVISION"]
    (config / "ubuntu.yaml").write_text("hostname: other")
    assert fingerprint_runtime(tmp_path)["APATE_PROFILE_DIGEST"] != initial["APATE_PROFILE_DIGEST"]


def test_export_uses_admitted_session_provenance_after_core_update(monkeypatch):
    monkeypatch.setenv("APATE_SOURCE_REVISION", "new-core")
    args = SimpleNamespace(run_id=None, session_id="session")
    metadata = {"run_id": "original-run", "source_revision": "admitted-source",
                "configuration_digest": "admitted-config", "profile_digest": "admitted-profile"}
    events = [{"operation": "research_run_attached", "metadata": metadata}]
    result = _metadata_from_environment(args, "snapshot", events)
    assert all(result[key] == value for key, value in metadata.items())
    conflicting = _metadata_from_environment(args, "snapshot", events + events)
    assert conflicting["source_revision"] is None
