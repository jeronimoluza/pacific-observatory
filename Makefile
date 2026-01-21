.PHONY: help test test-unit test-integration lint format docs clean

# Environment setup for module imports
export PYTHONPATH := src

# Default target
help:
	@echo "Pacific Observatory - Development Commands"
	@echo ""
	@echo "Testing:"
	@echo "  make test              Run all tests"
	@echo "  make test-unit         Run unit tests only"
	@echo "  make test-integration  Run integration tests only"
	@echo "  make test-cov          Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint              Run linters (flake8, mypy)"
	@echo "  make format            Format code (black, isort)"
	@echo "  make check             Run all checks (lint + test)"
	@echo ""
	@echo "Documentation:"
	@echo "  make docs              Build documentation"
	@echo "  make docs-open         Open documentation in browser"
	@echo "  make docs-clean        Clean documentation build"
	@echo ""
	@echo "Other:"
	@echo "  make clean             Clean all generated files"
	@echo "  make install           Install dependencies"
	@echo "  make install-dev       Install dev dependencies"
	@echo ""
	@echo "Note: Text scraping commands are in src/Makefile"

# =============================================================================
# Testing
# =============================================================================

test:
	poetry run pytest tests/ -v

test-unit:
	poetry run pytest tests/unit -v

test-integration:
	poetry run pytest tests/integration -v --tb=short

test-cov:
	poetry run pytest tests/ --cov=src/text --cov-report=html --cov-report=term-missing
	@echo "Coverage report: htmlcov/index.html"

# =============================================================================
# Code Quality
# =============================================================================

lint:
	@echo "Running flake8..."
	-poetry run flake8 src/text --max-line-length=100 --ignore=E501,W503
	@echo ""
	@echo "Running mypy..."
	-poetry run mypy src/text --ignore-missing-imports

format:
	@echo "Running black..."
	poetry run black src/text tests --line-length=100
	@echo ""
	@echo "Running isort..."
	poetry run isort src/text tests --profile=black --line-length=100

check: lint test

# =============================================================================
# Documentation
# =============================================================================

docs:
	poetry run jupyter-book clean docs
	poetry run jupyter-book build docs
	@echo "Documentation built: docs/_build/html/index.html"

docs-open: docs
	open docs/_build/html/index.html

docs-clean:
	poetry run jupyter-book clean docs

# =============================================================================
# Installation
# =============================================================================

install:
	poetry install

install-dev:
	poetry install --with dev
	poetry run pre-commit install

# =============================================================================
# Cleanup
# =============================================================================

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

clean-data:
	@echo "This will delete all scraped data. Are you sure? [y/N]"
	@read -r response && [ "$$response" = "y" ] && rm -rf data/text/*/ || echo "Aborted."

# =============================================================================
# Pre-commit
# =============================================================================

pre-commit-install:
	poetry run pre-commit install

pre-commit-run:
	poetry run pre-commit run --all-files
