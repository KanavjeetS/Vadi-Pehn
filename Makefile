# ==============================================================================
# Vadi-Pehn Platform Makefile
# ==============================================================================

.PHONY: dev docker-up docker-down test lint

dev:
	py start_desktop.py

docker-up:
	docker compose up -d

docker-down:
	docker compose down

test:
	py -3 -m pytest services/

lint:
	py -3 -m ruff check services/ start_desktop.py
