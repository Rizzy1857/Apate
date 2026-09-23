"""Versioned prepared baselines, copied into fresh session namespaces only."""
import base64
import hashlib
import json
from chronos.intelligence.artifact_policy import ArtifactPolicyEngine


def bundle_key(profile):
    state = profile.build_machine_state()
    state.pop('created_at', None)
    policy = ArtifactPolicyEngine()
    document = {'version': 1, 'state': state, 'policy': policy._artifact_policy,
                'routing': policy._model_routing}
    digest = hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()
    return f'chronos:prepared:{digest}'


def install(client, inode, entry):
    """Initialization lock is held; never replace an existing content version."""
    key = f'fs:inode:{inode}'
    if client.hget(key, 'content_hash'):
        return
    content = base64.b64decode(entry['base64'], validate=True)
    if len(content) > 65536:
        raise ValueError('Prepared artifact exceeds limit')
    digest = hashlib.sha256(content).hexdigest()
    if digest != entry['sha256']:
        raise ValueError('Prepared artifact integrity failure')
    with client.pipeline() as pipe:
        pipe.set(f'fs:blob:{digest}', content)
        pipe.hset(f'fs:blob_meta:{digest}', mapping=entry['provenance'])
        pipe.hset(key, mapping={'content_hash': digest, 'size': len(content),
                               'content_state': 'prepared'})
        pipe.execute()


def main():
    import time
    import uuid
    from chronos.core.state import StateHypervisor
    from chronos.core.content import read_blob
    from chronos.intelligence.orchestrator import GenerationOrchestrator
    from chronos.intelligence.ubuntu_profile import UbuntuProfile
    profile = UbuntuProfile()
    session = str(uuid.uuid4())
    # Preparation is not an SSH session and must not be reclaimed by its reaper.
    prefix = f'preparation:{session}:'
    state = StateHypervisor(prefix=prefix)
    state.initialize_filesystem(use_prepared=False)
    generator = GenerationOrchestrator(state.redis, profile, max_workers=1)
    artifacts = {}
    try:
        for entry in profile.filesystem_manifest['entries']:
            if entry.get('class') != 'ai_backed':
                continue
            path = entry['path']
            inode = state._resolve_path_sync(path)
            deadline = time.monotonic() + 65
            data = None
            while data is None and time.monotonic() < deadline:
                data = generator.get_or_generate(inode, path, session, {})
            if data is None:
                raise RuntimeError(f'Preparation deadline: {path}')
            digest = state.redis.hget(f'fs:inode:{inode}', 'content_hash')
            provenance = state.redis.hgetall(f'fs:blob_meta:{digest}')
            if provenance.get('generation_source') == 'fallback':
                raise RuntimeError(f'Preparation requires accepted content: {path}')
            artifacts[path] = {'base64': base64.b64encode(read_blob(state.redis, digest)).decode(),
                               'sha256': digest, 'provenance': provenance}
        state.redis.set(bundle_key(profile), json.dumps(artifacts))
        print(f'Prepared {len(artifacts)} artifacts for new sessions. Existing sessions unchanged.')
    finally:
        generator.close()
        for key in state.redis.client.scan_iter(match=prefix + '*', count=100):
            state.redis.client.unlink(key)


if __name__ == '__main__':
    main()
