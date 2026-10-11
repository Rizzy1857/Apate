import base64
import hashlib
import json
from unittest.mock import MagicMock
import pytest
from chronos.intelligence.prepared_artifacts import (
    BUNDLE_VERSION,
    bundle_key,
    install,
    load_bundle,
    model_identities,
)
from chronos.intelligence.ubuntu_profile import UbuntuProfile


def test_bundle_fingerprint_ignores_creation_time():
    assert bundle_key(UbuntuProfile()) == bundle_key(UbuntuProfile())


def test_bundle_loader_rejects_legacy_or_malformed_documents():
    artifacts = {"/example": {"sha256": "abc"}}
    assert load_bundle(json.dumps({"version": BUNDLE_VERSION, "artifacts": artifacts})) == artifacts
    assert load_bundle(json.dumps(artifacts)) == {}
    assert load_bundle(json.dumps({"version": BUNDLE_VERSION, "artifacts": []})) == {}


def test_model_tags_are_resolved_to_digests(monkeypatch):
    response = MagicMock()
    response.json.return_value = {
        "models": [{"name": "model:tag", "digest": "sha256:immutable"}]
    }
    monkeypatch.setattr("requests.get", MagicMock(return_value=response))
    runtime = MagicMock(host="localhost", port=11434)
    assert model_identities(runtime, ["model:tag"]) == {
        "model:tag": "sha256:immutable"
    }
    with pytest.raises(RuntimeError, match="Missing configured model identities"):
        model_identities(runtime, ["missing:tag"])


def test_prepared_artifact_integrity_and_preservation():
    client = MagicMock()
    client.hget.return_value = 'existing'
    install(client, 2, {})
    client.pipeline.assert_not_called()
    client.hget.return_value = None
    entry = {'base64': base64.b64encode(b'valid').decode(),
             'sha256': hashlib.sha256(b'valid').hexdigest(),
             'provenance': {'generation_source': 'llm'}}
    install(client, 2, entry)
    pipe = client.pipeline.return_value.__enter__.return_value
    pipe.execute.assert_called_once()
    assert pipe.hset.call_args.kwargs['mapping']['content_state'] == 'prepared'
    entry['sha256'] = 'wrong'
    with pytest.raises(ValueError, match='integrity'):
        install(client, 3, entry)
