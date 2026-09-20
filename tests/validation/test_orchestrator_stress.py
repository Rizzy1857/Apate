"""Stress real Redis state transitions instead of a test-only dictionary protocol."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from chronos.intelligence.orchestrator import GenerationOrchestrator
from chronos.intelligence.ubuntu_profile import UbuntuProfile


def test_orchestrator_thundering_herd(isolated_redis):
    r = isolated_redis
    r.hset(
        "fs:inode:100",
        mapping={"mode": 33188, "size": 0, "manifest_class": "deterministic"},
    )
    runtime = Mock()
    g = GenerationOrchestrator(r, UbuntuProfile(), runtime)
    try:
        with ThreadPoolExecutor(max_workers=32) as pool:
            results = list(
                pool.map(
                    lambda _: g.get_or_generate(100, "/etc/passwd", "s", {}), range(500)
                )
            )
        assert len(results) == 500
        assert len(set(results)) == 1
        assert b"ubuntu:x:1000:" in results[0]
        runtime.generate.assert_not_called()
    finally:
        g.close()
