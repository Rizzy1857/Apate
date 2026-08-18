.PHONY: help up down restart ps prod logs logs-core logs-world logs-db logs-redis shell clean test verify verify-all validate-core validate-full validate-attacks validate-concurrency validate-crash test-simulation ui dashboard run-ui build-ui check-ui ssh demo-standalone demo-integration

# Default target
.DEFAULT_GOAL := help

help:
	@echo "╔══════════════════════════════════════════════════════════════════════════╗"
	@echo "║                   MIRAGE (CHRONOS FRAMEWORK) — MAKEFILE                  ║"
	@echo "╚══════════════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "📊 OVERSEER DASHBOARD (UI):"
	@echo "  make ui               Run the Overseer native egui dashboard"
	@echo "  make build-ui         Build release binary for Overseer dashboard"
	@echo "  make check-ui         Verify dashboard cargo compilation"
	@echo ""
	@echo "🐳 DOCKER STACK MANAGEMENT:"
	@echo "  make up               Build and start full Docker stack in background"
	@echo "  make down             Stop all Docker containers"
	@echo "  make restart          Restart all Docker containers"
	@echo "  make ps               Show status of Docker containers"
	@echo "  make prod             Start production Docker compose stack"
	@echo "  make logs             Follow logs from core-engine container"
	@echo "  make logs-world       Follow logs from world simulation container"
	@echo "  make logs-db          Follow logs from PostgreSQL container"
	@echo "  make logs-redis       Follow logs from Redis container"
	@echo "  make shell            Open interactive bash shell inside chronos_core"
	@echo "  make clean            Stop stack and remove volumes + orphan containers"
	@echo ""
	@echo "🧪 TESTING & VERIFICATION:"
	@echo "  make verify           Run Phase 1 to Phase 4 component verification"
	@echo "  make verify-all       Run all verification scripts including evidence collector"
	@echo "  make test-simulation  Run simulation validation tests (entropy, circuit breaker, shell)"
	@echo "  make validate-core    Run core state and persistence integrity validation"
	@echo "  make validate-attacks Run simulated real attack detection test suite"
	@echo "  make validate-full    Run complete end-to-end validation suite"
	@echo ""
	@echo "🚀 INTERACTIVE & DEMO:"
	@echo "  make ssh              Connect to honeypot SSH gateway (localhost:2222)"
	@echo "  make demo-standalone  Run standalone integration demo script"
	@echo "  make demo-integration Run full integration demo script"
	@echo ""

# ── Overseer Dashboard (UI) ──────────────────────────────────────────────────
ui: run-ui
dashboard: run-ui

run-ui:
	@echo "🖥️  Launching Chronos Overseer Dashboard..."
	cargo run --manifest-path src/chronos/dashboard/Cargo.toml

build-ui:
	@echo "🔨 Building Chronos Overseer Dashboard (Release)..."
	cargo build --release --manifest-path src/chronos/dashboard/Cargo.toml

check-ui:
	@echo "🔍 Checking Chronos Overseer Dashboard compilation..."
	cargo check --manifest-path src/chronos/dashboard/Cargo.toml

# ── Docker Stack Management ──────────────────────────────────────────────────
up:
	docker compose up --build -d

down:
	docker compose down

restart:
	docker compose restart

ps:
	docker compose ps

prod:
	docker compose -f docker-compose.prod.yml up --build -d

logs:
	docker compose logs -f core-engine

logs-core:
	docker compose logs -f core-engine

logs-world:
	docker compose logs -f world-engine

logs-db:
	docker compose logs -f db-store

logs-redis:
	docker compose logs -f redis-store

shell:
	docker exec -it chronos_core /bin/bash

clean:
	docker compose down -v
	docker system prune -f

# ── Container-Internal Tests ─────────────────────────────────────────────────
test:
	docker exec chronos_core python3 tests/verification/verify_phase1.py
	docker exec chronos_core python3 tests/verification/verify_phase2.py
	docker exec chronos_core python3 tests/verification/verify_phase3.py

# ── Verification Suites ──────────────────────────────────────────────────────
verify:
	PYTHONPATH=src python3 tests/verification/verify_phase1.py
	PYTHONPATH=src python3 tests/verification/verify_phase2.py
	PYTHONPATH=src python3 tests/verification/verify_phase3.py
	PYTHONPATH=src python3 tests/verification/verify_phase4.py

verify-all: verify
	PYTHONPATH=src python3 tests/verification/verify_evidence_collector.py

test-simulation:
	@echo "🌐 Running World Simulation & Gateway validation..."
	PYTHONPATH=src python3 tests/validation/test_pseudo_shell.py
	PYTHONPATH=src python3 tests/validation/test_circuit_breaker.py
	PYTHONPATH=src python3 tests/validation/test_entropy.py
	PYTHONPATH=src python3 tests/validation/test_world_simulation.py

# ── Validation Suites ────────────────────────────────────────────────────────
validate-core:
	@echo "🧪 Running Phase 1 Core Validation..."
	@echo "This tests fundamental integrity, not features."
	PYTHONPATH=src python3 tests/validation/validate_core.py

validate-attacks:
	@echo "🔥 Running Real Attack Simulation..."
	@echo "Testing detection against realistic attack patterns."
	PYTHONPATH=src python3 tests/validation/test_real_attack.py

validate-concurrency:
	@echo "🧪 Running Multi-Process Concurrency Test..."
	@echo "Simulates 2-10 concurrent SSH sessions."
	PYTHONPATH=src python3 tests/validation/test_concurrency.py

validate-crash:
	@echo "💥 Running Crash Recovery Test..."
	@echo "This will stop and restart Docker containers."
	PYTHONPATH=src python3 tests/validation/test_crash_recovery.py

validate-full:
	@echo "🧪 Phase 1 Full Validation Suite"
	@echo "================================"
	@echo ""
	@echo "Step 1: Core Infrastructure"
	@make validate-core
	@echo ""
	@echo "Step 2: Attack Simulation"
	@make validate-attacks
	@echo ""
	@echo "Step 3: Implementation Tests"
	@make verify-all
	@echo ""
	@echo "Step 4: Simulation Tests"
	@make test-simulation
	@echo ""
	@echo "See docs/PHASE1_VALIDATION.md and docs/ROADMAP.md for details."

# ── Interactive & Demos ──────────────────────────────────────────────────────
ssh:
	@echo "🔑 Connecting to Honeypot SSH Gateway..."
	ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 2222 ubuntu@localhost

demo-standalone:
	PYTHONPATH=src python3 tests/integration/demo_standalone.py

demo-integration:
	PYTHONPATH=src python3 tests/integration/demo_integration.py

