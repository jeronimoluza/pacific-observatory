# src/text/scrapers/orchestration/

Internal scraper orchestration modules. The pre-unified CLI that lived here
has been superseded by the unified CLI.

## Usage

```bash
python run.py text collect --country ukraine          # Scrape one country
python run.py text collect --region eca --dry-run     # Preview a region
python run.py text collect --source kyiv_independent  # Scrape one configured newspaper key
```

See [src/text/README.md](../../README.md) for full flag reference.
