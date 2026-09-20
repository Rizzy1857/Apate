"""Compatibility entry point for isolated manifest/state regression checks."""
from pathlib import Path


def run_tests():
    import pytest
    suite = Path(__file__).resolve().parents[1] / "validation" / "test_hardening.py"
    return pytest.main([str(suite), "-q"])


if __name__ == "__main__":
    raise SystemExit(run_tests())
