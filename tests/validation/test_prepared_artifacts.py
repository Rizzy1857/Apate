import base64
import hashlib
from unittest.mock import MagicMock
import pytest
from chronos.intelligence.prepared_artifacts import install, bundle_key
from chronos.intelligence.ubuntu_profile import UbuntuProfile


def test_bundle_fingerprint_ignores_creation_time():
    assert bundle_key(UbuntuProfile()) == bundle_key(UbuntuProfile())


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
