ENV_FILE=.env

.PHONY: ensure-env check-docker up format lint docs docs-generate test test-local test-staging

ensure-env:
	@if [ ! -f $(ENV_FILE) ]; then cp .env.example $(ENV_FILE); fi

check-docker:
	@docker version > /dev/null || (echo "Docker is not running. Please ensure Docker is installed and running." && exit 1)

up: check-docker ensure-env
	docker compose up


upd: check-docker ensure-env
	docker compose up -d
	@echo "Waiting for Moodle to be ready..."
	@for i in $$(seq 1 60); do \
	  if curl -s --head http://localhost | grep "200 OK" > /dev/null; then \
	    echo "Moodle is up!"; \
	    break; \
	  fi; \
	  sleep 5; \
	done

format:
	black .
	isort .

lint:
	black --check .
	isort --check-only .
	flake8

docs:
	python -m typer py_moodle.cli.app utils docs --output docs/cli.md --name py-moodle
	mkdocs build --strict

test-local: ensure-env
	pytest --moodle-env local -n auto

test-staging: ensure-env
	pytest --moodle-env staging -n auto

test: upd test-local

help:
	@echo "Available commands:"
	@echo ""
	@echo "Environment:"
	@echo "  ensure-env         - Create .env file from .env.example if it does not exist"
	@echo "  check-docker       - Check if Docker is running"
	@echo ""
	@echo "Startup:"
	@echo "  up                 - Run Docker containers in foreground mode"
	@echo "  upd                - Run Docker containers in detached mode and wait for Moodle to be ready"
	@echo ""
	@echo "Code Quality:"
	@echo "  format             - Format code with black and isort"
	@echo "  lint               - Lint code with black, isort, and flake8"
	@echo ""
	@echo "Documentation:"
	@echo "  docs               - Build documentation with mkdocs"
	@echo ""
	@echo "Testing:"
	@echo "  test-local         - Run local tests (in parallel) using pytest with moodle-env=local"
	@echo "  test-staging       - Run tests using (in parallel) moodle-env=staging"
	@echo "  test               - Start containers (detached) and run local tests"
	@echo ""
	@echo "  help               - Show this help message"

.DEFAULT_GOAL := help
