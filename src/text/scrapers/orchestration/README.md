# src/text/scrapers/orchestration/

Internal scraper orchestration modules. The pre-`po` CLI that lived here
has been superseded by the unified CLI.

## Usage

```bash
po text collect --country ukraine          # Scrape one country
po text collect --region eca --dry-run     # Preview a region
po text collect --source kyiv_independent  # Scrape one newspaper
```

See [src/text/README.md](../../README.md) for full flag reference.
