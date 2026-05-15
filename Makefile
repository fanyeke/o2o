.PHONY: build up down logs api-logs worker-logs psql shell test migrate makemigrations import-data restart

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

api-logs:
	docker compose logs -f api

worker-logs:
	docker compose logs -f worker

psql:
	docker compose exec postgres psql -U coupon_user -d coupon_agent

shell:
	docker compose exec api /bin/bash

test:
	docker compose exec api python -m pytest -v

migrate:
	docker compose exec api alembic upgrade head

makemigrations:
	docker compose exec api alembic revision --autogenerate -m "$(message)"

import-data:
	docker compose exec api python -m scripts.import_dataset

restart:
	docker compose restart

build-prod:
	docker compose build --target prod
