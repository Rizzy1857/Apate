# Chronos Test Suite

This directory contains all testing, verification, and validation scripts for the Chronos Framework.

## Directory Structure

```
tests/
├── validation/          Phase 1 core validation tests
│   ├── validate_core.py           Core infrastructure validation
│   └── test_real_attack.py        Real attack simulation testing
│   ├── test_concurrency.py         Multi-process session concurrency
│   ├── test_crash_recovery.py      Redis/Postgres/core crash recovery
│   ├── test_cowrie_comparison.py   Chronos vs Cowrie comparison
│   ├── test_stability.py           24-hour stability run
│   └── setup_cowrie_comparison.sh  Cowrie install + comparison helper
│
├── verification/        Implementation verification tests
│   ├── verify_phase1.py           State Hypervisor & Database
│   ├── verify_phase2.py           FUSE Interface
│   ├── verify_phase3.py           Intelligence & Persona
│   └── verify_phase4.py           Gateway, Watcher, Skills
│
└── integration/         End-to-end integration demos
    ├── demo_standalone.py         Skills showcase (no infrastructure)
    └── demo_integration.py        Full system integration demo
```

## Running Tests

### Quick Start

```bash
# From project root
make validate-core      # Run core validation
make verify             # Run all verification tests
```

### Individual Test Suites

#### 1. Core Validation (Phase 1)

Tests fundamental system integrity without hype:

```bash
cd tests/validation
python3 validate_core.py
```

**Tests:**
- Redis connectivity and atomic operations
- PostgreSQL connectivity
- State persistence and consistency
- Lua script execution
- Directory simulation
- Performance baselines

**Expected Output:** 8/8 tests passed

---

#### 2. Real Attack Simulation

Tests detection capabilities with realistic attack sequences:

```bash
cd tests/validation
python3 test_real_attack.py
```

**Tests:**
- Reconnaissance (10 commands)
- Privilege Escalation (5 commands)
- Persistence (4 commands)
- Exfiltration (4 commands)
- Defense Evasion (5 commands)

**Expected Output:** 78.6% detection rate, <0.1ms latency

---

#### 3. Multi-Process Concurrency

Tests concurrent SSH sessions, race conditions, and session isolation:

```bash
cd tests/validation
python3 test_concurrency.py
```

**Output:** JSON report in `/tmp/chronos_concurrency_test_<timestamp>.json`

---

#### 4. Crash Recovery

Simulates Redis, PostgreSQL, and core-engine crashes:

```bash
cd tests/validation
python3 test_crash_recovery.py
```

**Warning:** This stops and restarts Docker containers.

---

#### 5. Cowrie Comparison

Run identical commands against Chronos and Cowrie:

```bash
cd tests/validation
python3 test_cowrie_comparison.py
```

**Prerequisite:** Cowrie running on port 2223.
Use the helper script to install/start Cowrie:

```bash
cd tests/validation
bash setup_cowrie_comparison.sh
```

---

#### 6. 24-Hour Stability Run

Default run is 24 hours (1,440 minutes). Use shorter durations for dev:

```bash
cd tests/validation
python3 test_stability.py --duration-mins 60
```

**Output:** Summary JSON in `/tmp/chronos_stability_test_<timestamp>.json`

---

#### 7. Implementation Verification

Verifies all major components function correctly:

```bash
cd tests/verification

# Run individually
python3 verify_phase1.py    # State management
python3 verify_phase2.py    # FUSE interface
python3 verify_phase3.py    # Intelligence layer
python3 verify_phase4.py    # Gateway/Watcher/Skills

# Or run all from project root
make verify
```

**Expected Output:** All phases pass

---

#### 8. Integration Demos

End-to-end demonstrations:

```bash
cd tests/integration

# Standalone demo (no infrastructure needed)
python3 demo_standalone.py

# Full integration demo (requires Docker services)
python3 demo_integration.py
```

---

## Test Requirements

### Infrastructure Requirements

**Core Validation & Verification:**
- Docker & Docker Compose
- Redis (via Docker)
- PostgreSQL (via Docker)

Start services:
```bash
make up    # From project root
```

**Cowrie Comparison:**
- Cowrie (install via `tests/validation/setup_cowrie_comparison.sh`)

### Python Dependencies

All tests use dependencies from `requirements.txt`:
- redis==5.0.1
- psycopg2-binary==2.9.9
- paramiko==3.4.0
- pydantic==2.5.3
- python-dateutil==2.8.2

---

## Validation Status

### Phase 1 Core Validation

| Test Category | Status | Score |
|--------------|--------|-------|
| Core Infrastructure | ✅ PASS | 8/8 (100%) |
| Implementation Tests | ✅ PASS | 4/4 (100%) |
| Attack Simulation | ✅ PASS | 22/28 (78.6%) |
| Performance | ✅ EXCELLENT | 0.04ms avg |

**Overall Phase 1 Score:** 4.5/7 (64%)

See `docs/PHASE1_RESULTS.md` for detailed analysis.

---

## Adding New Tests

### Validation Tests (tests/validation/)

For testing core system integrity:
- Infrastructure connectivity
- State consistency
- Performance benchmarks
- Crash recovery

### Verification Tests (tests/verification/)

For testing component functionality:
- Individual modules work correctly
- Integration between layers
- Expected behavior validation

### Integration Tests (tests/integration/)

For end-to-end demonstrations:
- Full attack scenarios
- Multi-component workflows
- Real-world use cases

---

## CI/CD Integration

Tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run Core Validation
  run: |
    make up
    python3 tests/validation/validate_core.py

- name: Run Verification Tests
  run: make verify
```

---

## Troubleshooting

### Tests Fail with Connection Errors

Ensure Docker services are running:
```bash
docker-compose ps
# Should show redis and postgres as healthy
```

Restart if needed:
```bash
make down
make up
```

### Import Errors

Ensure you're running from the correct directory:
```bash
# For validation/verification tests
cd /path/to/Apate
export PYTHONPATH=$PWD
python3 tests/validation/validate_core.py
```

### Performance Issues

Check system resources:
```bash
docker stats
# Monitor Redis and PostgreSQL resource usage
```

---

## Documentation

- **Validation Criteria:** `docs/PHASE1_VALIDATION.md`
- **Test Results:** `docs/PHASE1_RESULTS.md`
- **Action Checklist:** `docs/PHASE1_ACTION_CHECKLIST.md`

---

*Last Updated: February 25, 2026*
