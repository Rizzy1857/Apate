.PHONY: up down prod logs shell clean test verify

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
