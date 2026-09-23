"""Run the supported resource-world subset; legacy file-mutating plugins stay disabled."""
import os
import signal
import threading
import uuid
from chronos.core.state import StateHypervisor
from chronos.core.persistence import PersistenceLayer
from chronos.core.metrics import start_metrics_server
from chronos.simulation.world_state import publish_tick


def main():
    stopped = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    client = StateHypervisor().redis
    persistence = PersistenceLayer()
    persistence.connect()
    seed = os.environ.get('APATE_WORLD_SEED', 'research-v1')
    world_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'apate:world:' + seed))
    start_metrics_server()
    try:
        while not stopped.is_set():
            state = publish_tick(client, seed, 60)
            persistence.log_operation(world_id, 'world_tick', '', 0, {
                'origin': 'synthetic', 'schema_version': 1, 'world_snapshot': state,
            })
            stopped.wait(60)
    finally:
        persistence.close()


if __name__ == '__main__':
    main()
