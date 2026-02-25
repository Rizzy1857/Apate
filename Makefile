.PHONY: up down prod logs shell clean test verify validate-core validate-full

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
	docker exec chronos_core python3 verify_phase1.py
	docker exec chronos_core python3 verify_phase2.py
	docker exec chronos_core python3 verify_phase3.py

verify:
	python3 verify_phase1.py
	python3 verify_phase2.py
	python3 verify_phase3.py
	python3 verify_phase4.py

# Phase 1 brutal validation (no hype, just proof)
validate-core:
	@echo "🧪 Running Phase 1 Core Validation..."
	@echo "This tests fundamental integrity, not features."
	python3 validate_core.py

validate-full:
	@echo "🧪 Phase 1 Full Validation Suite"
	@echo "================================"
	@echo ""
	@echo "Step 1: Core Infrastructure"
	@make validate-core
	@echo ""
	@echo "Step 2: Implementation Tests"
	@make verify
	@echo ""
	@echo "⚠️  REMAINING VALIDATION REQUIRED:"
	@echo "   - Real attack simulations (0/10 completed)"
	@echo "   - Performance benchmarking (not measured)"
	@echo "   - Cowrie comparison (not performed)"
	@echo "   - Crash resistance testing (not tested)"
	@echo ""
	@echo "See docs/PHASE1_VALIDATION.md for complete checklist"
