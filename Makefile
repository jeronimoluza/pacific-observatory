.PHONY: help dev install lint fmt check ci test test-unit test-integration test-cov eval docs docs-open

export PYTHONPATH := src

# Detect python command (python3 on Unix/macOS, python on Windows/Git Bash)
PYTHON := $(shell python3 --version >/dev/null 2>&1 && echo python3 || echo python)

# Cross-platform browser open
OPEN := $(shell command -v open 2>/dev/null || command -v xdg-open 2>/dev/null || echo $(PYTHON) -m webbrowser)

# Auto-generated help from ## comments
help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# Installation
# =============================================================================

dev: ## Set up full development environment (installs Poetry if missing)
	@echo "→ Checking Python ($(PYTHON))..."
	@$(PYTHON) --version
	@echo "→ Checking Poetry..."
	@command -v poetry >/dev/null 2>&1 || \
		(echo "Poetry not found — installing via official installer..." && \
		 curl -sSL https://install.python-poetry.org | $(PYTHON) - && \
		 echo "" && \
		 echo "  Poetry installed to ~/.local/bin (Unix) or %APPDATA%\\Python\\Scripts (Windows)." && \
		 echo "  If the next step fails, restart your shell and re-run 'make dev'." && \
		 echo "")
	@poetry install --with dev
	@poetry run pre-commit install
	@echo ""
	@echo "  Dev environment ready. Run 'make help' to see all commands."
	@echo ""

install: ## Install production dependencies only
	@poetry install

# =============================================================================
# Code quality
# =============================================================================

lint: ## Check code with ruff (read-only)
	@poetry run ruff check src/

fmt: ## Format and auto-fix code with ruff
	@poetry run ruff format src/
	@poetry run ruff check --fix src/

check: ## Static analysis: mypy + bandit
	@poetry run mypy src/ || true
	@poetry run bandit -r src/text/ -q

ci: lint test ## Full CI gate: lint + all tests

# =============================================================================
# Testing
# =============================================================================

test: ## Run all tests
	@poetry run pytest tests/ -v

test-unit: ## Run unit tests only
	@poetry run pytest tests/unit -v

test-integration: ## Run integration tests only
	@poetry run pytest tests/integration -v --tb=short

test-cov: ## Run tests with HTML coverage report (htmlcov/index.html)
	@poetry run pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

eval: ## Run enrich pipeline against eval_set.csv and append to eval_history.csv (requires GOOGLE_API_KEY)
	@poetry run python scripts/run_eval.py

# =============================================================================
# Documentation
# =============================================================================

docs: ## Build documentation
	@poetry run jupyter-book clean docs
	@poetry run jupyter-book build docs
	@echo "Built: docs/_build/html/index.html"

docs-open: docs ## Build and open documentation in browser
	@$(OPEN) docs/_build/html/index.html
