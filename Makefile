.PHONY: up down prod logs shell clean test verify validate-core validate-full validate-attacks validate-concurrency validate-crash

up:
	docker compose up --build -d

down:
	docker compose down

prod:
	docker compose -f docker-compose.prod.yml up --build -d

logs:
	docker compose logs -f core-engine

shell:
	docker exec -it chronos_core /bin/bash

clean:
	docker compose down -v
	docker system prune -f

test:
	docker exec chronos_core python3 tests/verification/verify_phase1.py
	docker exec chronos_core python3 tests/verification/verify_phase2.py
	docker exec chronos_core python3 tests/verification/verify_phase3.py

verify:
	python3 tests/verification/verify_phase1.py
	python3 tests/verification/verify_phase2.py
	python3 tests/verification/verify_phase3.py
	python3 tests/verification/verify_phase4.py

# Phase 1 brutal validation (no hype, just proof)
validate-core:
	@echo "🧪 Running Phase 1 Core Validation..."
	@echo "This tests fundamental integrity, not features."
	python3 tests/validation/validate_core.py

validate-attacks:
	@echo "🔥 Running Real Attack Simulation..."
	@echo "Testing detection against realistic attack patterns."
	python3 tests/validation/test_real_attack.py

validate-concurrency:
	@echo "🧪 Running Multi-Process Concurrency Test..."
	@echo "Simulates 2-10 concurrent SSH sessions."
	python3 tests/validation/test_concurrency.py

validate-crash:
	@echo "💥 Running Crash Recovery Test..."
	@echo "This will stop and restart Docker containers."
	python3 tests/validation/test_crash_recovery.py

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
	@make verify
	@echo ""
	@echo "⚠️  REMAINING VALIDATION ITEMS:"
	@echo "   - Multi-process concurrency (run: make validate-concurrency)"
	@echo "   - Crash recovery testing (run: make validate-crash)"
	@echo "   - SSH Gateway deployment (not yet implemented)"
	@echo "   - Long-term stability testing (requires SSH Gateway)"
	@echo ""
	@echo "See docs/PHASE1_VALIDATION.md for complete checklist"

# Demo scripts
demo-standalone:
	python3 tests/integration/demo_standalone.py

demo-integration:
	python3 tests/integration/demo_integration.py
