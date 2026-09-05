.PHONY: help test test-all test-unit test-integration docs clean

# Environment setup for mixed import styles in tests and scripts
export PYTHONPATH := .:src

# Default target
help:
	@echo "Pacific Observatory - Development Commands"
	@echo ""
	@echo "Testing:"
	@echo "  make test              Run the default unit suite"
	@echo "  make test-all          Run the full test suite"
	@echo "  make test-unit         Run unit tests only"
	@echo "  make test-integration  Run non-unit tests"
	@echo "  make test-cov          Run tests with coverage report"
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
	poetry run pytest tests/unit -v

test-all:
	poetry run pytest tests/ -v

test-unit:
	poetry run pytest tests/unit -v

test-integration:
	poetry run pytest tests/ --ignore=tests/unit -v --tb=short

test-cov:
	poetry run pytest tests/ --cov=src/text --cov-report=html --cov-report=term-missing
	@echo "Coverage report: htmlcov/index.html"

# =============================================================================
# Documentation
# =============================================================================

docs:
	poetry run jupyter-book clean docs
	poetry run jupyter-book build docs
	@echo "Documentation built: docs/_build/html/index.html"
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

# =============================================================================
# Pre-commit
# =============================================================================

pre-commit-install:
	poetry run pre-commit install

pre-commit-run:
	poetry run pre-commit run --all-files
