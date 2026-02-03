.PHONY: help scrape scrape-update scrape-all status status-failures status-stats validate validate-all validate-live check-text-database

# Environment setup for module imports
export PYTHONPATH := .
export DATA_FOLDER_PATH := ../data/text

# Default target
help:
	@echo "Pacific Observatory - Text Module Scraping Commands"
	@echo ""
	@echo "Scraping:"
	@echo "  make scrape NEWSPAPER=fiji_sun    Scrape a newspaper"
	@echo "  make scrape-update NEWSPAPER=x    Scrape new articles only"
	@echo "  make scrape-all                   Scrape all newspapers"
	@echo ""
	@echo "Status:"
	@echo "  make status                       View scraper runs (last 24h)"
	@echo "  make status-failures              View failed runs"
	@echo "  make status-stats                 View aggregate statistics"
	@echo "  make check-text-database          View database overview (all sources)"
	@echo ""
	@echo "Validation:"
	@echo "  make validate CONFIG=path.yaml    Validate a config"
	@echo "  make validate-all                 Validate all configs"
	@echo "  make validate-live CONFIG=x       Validate with live request"

# =============================================================================
# Scraping
# =============================================================================

scrape:
ifndef NEWSPAPER
	$(error NEWSPAPER is not set. Usage: make scrape NEWSPAPER=fiji_sun)
endif
	poetry run python -m text.scrapers.orchestration.main $(NEWSPAPER)

scrape-update:
ifndef NEWSPAPER
	$(error NEWSPAPER is not set. Usage: make scrape-update NEWSPAPER=fiji_sun)
endif
	poetry run python -m text.scrapers.orchestration.main $(NEWSPAPER) --update

scrape-all:
	poetry run python -m text.scrapers.orchestration.main --run-all

# =============================================================================
# Status
# =============================================================================

status:
	poetry run python -m text.scrapers.orchestration.status --last-24h

status-failures:
	poetry run python -m text.scrapers.orchestration.status --failures

status-stats:
	poetry run python -m text.scrapers.orchestration.status --stats

check-text-database:
	poetry run python -m text.scrapers.orchestration.check_database

# =============================================================================
# Validation
# =============================================================================

validate:
ifndef CONFIG
	$(error CONFIG is not set. Usage: make validate CONFIG=path/to/config.yaml)
endif
	poetry run python -m text.scrapers.orchestration.validate $(CONFIG)

validate-all:
	poetry run python -m text.scrapers.orchestration.validate --all

validate-live:
ifndef CONFIG
	$(error CONFIG is not set. Usage: make validate-live CONFIG=path/to/config.yaml)
endif
	poetry run python -m text.scrapers.orchestration.validate $(CONFIG) --live
