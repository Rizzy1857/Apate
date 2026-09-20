"""Tests use a disposable Redis over a Unix socket, never the operator's database."""

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pytest
import redis


def pytest_addoption(parser):
    parser.addoption(
        "--legacy-infrastructure",
        action="store_true",
        help="Allow legacy tests that mutate localhost Redis or stop Docker containers",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--legacy-infrastructure"):
        return
    for item in items:
        if item.path.name in {"test_concurrency.py", "test_crash_recovery.py"}:
            item.add_marker(
                pytest.mark.skip(
                    reason="Requires explicit --legacy-infrastructure; mutates external services"
                )
            )


@pytest.fixture
def isolated_redis():
    executable = shutil.which("redis-server")
    if not executable:
        pytest.fail("redis-server is required for state regression tests")
    with tempfile.TemporaryDirectory(prefix="apate-test-", dir="/tmp") as directory:
        socket = str(Path(directory) / "r.sock")
        process = subprocess.Popen(
            [
                executable,
                "--port",
                "0",
                "--unixsocket",
                socket,
                "--save",
                "",
                "--appendonly",
                "no",
                "--dir",
                directory,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        client = redis.Redis(unix_socket_path=socket, decode_responses=True)
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError(process.stderr.read().decode())
                try:
                    if client.ping():
                        break
                except redis.ConnectionError:
                    time.sleep(0.02)
            else:
                raise RuntimeError("Isolated Redis failed to start")
            yield client
        finally:
            client.close()
            process.terminate()
            process.wait(timeout=5)
            process.stderr.close()
