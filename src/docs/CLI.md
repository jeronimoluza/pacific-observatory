# Source Tree CLI

There is no single `src/` CLI. Start from the nearest working entry point and use `--help` before running a bigger job.

## Shared Entry Points

| Use case | Start here |
| --- | --- |
| choose an area | `src/README.md` |
| text work | `src/text/README.md` or `cd src && make help` |
| price scraping | `poetry run python src/cpi/price_scraping/run_spider.py --help` |
| COICOP workflow | `poetry run python src/cpi/coicopping/main.py --help` |
| CPI construction | `poetry run python -m src.cpi.price_index.pipeline --help` |
| fuel prices | `poetry run python -m src.cpi.fuel_prices --help` |

## Working Rules

- Run commands from the repository root unless a local doc says otherwise.
- Use the current Poetry environment for Python entry points.
- Prefer the smallest relevant command or smoke check.
- Do not invent a new shared CLI surface unless multiple working areas genuinely need it.

## Common Traps

- `src/Makefile` is useful, but it is text-specific.
- Some paths work best as scripts and others as `python -m`; follow the local command that already works.
- If a documented command is stale, fix the doc after verifying the code path.
