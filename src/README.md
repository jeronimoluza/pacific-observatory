# Source Tree

`src/` is the working home for Pacific Observatory pipelines. The shared mental model is simple: collect source material, normalize it into stable tables, enrich it with classifications and derived signals, analyze it into indicators, and publish outputs people can inspect or ship.

This README is a human entry point. Start here to understand what lives in `src/`, what the main workflows are, and where to go next.

## What Lives Here

- `text/` - newspaper collection, article storage, text features, EPU analysis, and text-facing plots. Start with `src/text/README.md` and `src/text/docs/`.
- `cpi/` - retailer prices, fuel prices, COICOP enrichment, CPI construction, and price outputs. This is the implementation base behind the public `price_atlas` surface. Start with `src/cpi/README.md`.
- `tourism/` - tourism collection, parsing, analysis, and plotting.
- `docs/` - shared human docs for the cross-cutting pipeline, public CLI shape, and working conventions.
- `Makefile` - text-only convenience commands; useful for local text work, not a repo-wide CLI.

## Project Goals

- Turn alternative data into usable indicators for Pacific Observatory work.
- Keep raw collection, cleaned data, derived enrichment, analysis, and publication linked but not tangled.
- Make the production-facing surface human and stable even when internal module boundaries keep evolving.

## Pipeline At A Glance

1. `collect` - pull raw source material and preserve source evidence.
2. `normalize` - turn source-specific outputs into stable schemas, ids, dates, and folder conventions.
3. `enrich` - add classifications, quality signals, unit extraction, metadata, or derived text features.
4. `analyze` - build indices, reports, and analytical tables.
5. `publish` - generate dashboards, HTML, CSVs, and other shareable outputs.

See `src/docs/PIPELINE.md` for the shared pipeline model.

## Main Interactions

The production-facing shared CLI should center on `po`:

- `po text health`
- `po text collect <newspaper>`
- `po text analyze`
- `po price_atlas update`
- `po price_atlas enrich`
- `po price_atlas analyze`
- `po price_atlas publish`

See `src/docs/CLI.md` for the shared command map. Use local docs near the code for deeper implementation details.

## How We Work

- Treat `jeronimoluza/main` as the production-facing worktree we keep closest to ready.
- Use separate git worktrees for focused changes, experiments, or pipeline branches instead of mixing everything into one checkout.
- Update the nearest README or local doc when a workflow, command, or output changes.
- Keep shared docs human and cross-cutting; push detailed operational specifics down into local docs.
- Prefer the smallest stage-specific check that proves the change.

## Read Next

- `src/docs/README.md`
- `src/docs/PIPELINE.md`
- `src/docs/CLI.md`
- `src/cpi/README.md`
- `src/text/README.md`
- `src/text/docs/architecture.md`
- `src/cpi/fuel_prices/README.md`
