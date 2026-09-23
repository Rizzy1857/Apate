# Chronos Test Suite

This directory contains the validation, verification, and integration scripts for the Chronos framework.

## Structure

```text
tests/
├── validation/    Core system validation and attack simulation
├── verification/  Phase-by-phase implementation checks
└── integration/   End-to-end demos
```

## Running Tests

### Quick start

From the repository root:

```bash
make validate-core
make verify
```

### Validation tests

The validation scripts focus on core infrastructure and behavior under load.

```bash
cd tests/validation
python3 validate_core.py
python3 test_real_attack.py
python3 test_concurrency.py
python3 test_crash_recovery.py
python3 test_cowrie_comparison.py
python3 test_stability.py --duration-mins 60
```

### Verification tests

The verification scripts confirm that each major subsystem behaves as expected.

```bash
cd tests/verification
python3 verify_phase1.py
python3 verify_phase2.py
python3 verify_phase3.py
python3 verify_phase4.py
```

### Integration demos

The integration demos show the system in a more complete flow.

```bash
cd tests/integration
python3 demo_standalone.py
python3 demo_integration.py
```

## What Each Suite Checks

### Validation

- Redis and PostgreSQL connectivity
- State consistency and atomic operations
- Performance baselines
- Crash recovery behavior
- Comparison against Cowrie
- Long-running stability
- Real attack detection coverage

### Verification

- State hypervisor behavior
- FUSE filesystem behavior
- LLM and persona handling
- Gateway, watcher, and skills layers

### Integration

- Combined system behavior
- Full attack-session walkthroughs
- Realistic multi-component flows

## Requirements

### Infrastructure

- Docker and Docker Compose
- Redis via Docker
- PostgreSQL via Docker

Start the stack with:

```bash
make up
```

### Python packages

The scripts use the dependencies listed in `requirements.txt`, including:

- redis
- psycopg2-binary
- paramiko
- pydantic
- python-dateutil

## Validation Status

- Core validation: passed in the current baseline.
- Implementation verification: all four phases are represented.
- Attack simulation: provides a realistic detection benchmark.

See [docs/STATUS.md](../docs/STATUS.md) for the broader project state and [docs/ROADMAP.md](../docs/ROADMAP.md) for the next phase of work.

## Extending the Suite

When adding a new test, place it where the intent is clearest:

- `validation/` for infrastructure and behavior checks.
- `verification/` for component-level correctness.
- `integration/` for end-to-end demonstrations.

The categories are simple on purpose. A test should earn its filename.
