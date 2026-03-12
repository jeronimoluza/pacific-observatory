# Source Tree

`src/` holds the working code for the repository. Keep navigation simple, start from the nearest runnable entry point, and prefer shipping code over growing planning docs.

## Main Areas

- `text/` - newspaper scraping, storage, text analysis, and plotting.
- `cpi/` - retailer price scraping, COICOP cleanup, CPI work, and fuel prices.
- `tourism/` - tourism scraping, parsing, analysis, and plotting.
- `docs/` - lightweight shared notes for how we work inside `src/`.
- `Makefile` - text-oriented shortcuts such as `make help`, `make scrape`, and `make status`.

## Working Rules

- Start with the nearest README or active entry point, not a speculative plan.
- Treat code, tests, scripts, and real outputs as the source of truth.
- If a doc stops helping, trim it or delete it.
- Avoid introducing new top-level structures until code actually moves.
- Keep verification close to the area you changed.

## Where To Start

- Text work: `src/text/README.md`
- Price scraping: `src/cpi/price_scraping/`
- COICOP and supermarket-price processing: `src/cpi/coicopping/`
- CPI construction: `src/cpi/price_index/`
- Fuel prices: `src/cpi/fuel_prices/`
- Shared guidance: `src/docs/*.md`

## Verification

- Run the smallest relevant `--help`, test, or pipeline step for the code you touched.
- After changing documented commands, update the nearest README or shared note in the same change.
- Use `cd src && make help` only for the text-oriented Makefile surface.
