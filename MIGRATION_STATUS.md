# Migration Status

Last updated: 2026-03-11

This file tracks the current state of CPI migration work, with emphasis on the Fuel migration Step 1 baseline.

## Branch State

- `cpi-migration`: working branch for migration baselines.
- `cpi-migration-fuel`: currently aligned with `cpi-migration` (no divergence at last check); fuel work is being committed to `cpi-migration` and then fast-forwarded.

## Fuel Step 1 (CPI-M-FUEL-STEP1.md)

Goal: preserve `src/cpi/fuel_prices/` as an imported baseline on `cpi-migration` and document boundaries for later extraction into shared `price-atlas` interfaces.

Status against Step 1 Outcome:

- Imported baseline present: `src/cpi/fuel_prices/` is in the worktree and being committed as a preserved baseline.
- Inventory / decomposition: documented in `CPI-M-FUEL-STEP1.md` (collect/reconstruct, normalize, publish).
- Temp/runtime artifacts: identified in `CPI-M-FUEL-STEP1.md`; no deletion performed.
- Boundary between reusable patterns and fuel-specific logic: partially documented (registry + loader/normalization are good candidates; fetchers remain topic-local).
- Follow-up plan for Step 2: captured as candidates in `CPI-M-FUEL-STEP1.md`; still needs a concrete task list with owners/timebox.

## What’s Working (Fuel)

- Incremental execution model: `FETCHER_REGISTRY` + fetch-state persistence + dedupe via `observation_hash`.
- Mixed extraction modes in one pipeline: API + HTML + PDF + OCR.
- Track A evidence pattern exists (Thailand/Korea) and can be extended if needed.

Recent additions verified locally:

- Cambodia: MoC fuel notices enabled (scans `/en-US/news/<id>` and `/kh/news/<id>`).
- Indonesia: Pertamina announcements under `https://www.pertamina.com/pengumuman` include per-wilayah price tables; a Playwright scraper now extracts the latest monthly table.

## Pending Scrapers / Enhancements

These are the main collection gaps or hardening tasks still pending development:

- Indonesia (Pertamina):
  - Backfill: iterate and ingest historical announcement pages (not only the latest).
  - Variants: handle multiple December 2025 variants (Zona I/Zona II/All zone) deterministically.
  - Robustness: improve link discovery if `/pengumuman` layout changes.

- Cambodia (MoC fuel notices):
  - Efficiency: persist and reuse the last-seen notice ID (avoid scanning a large fixed range each run).
  - Discovery: optionally use the site GraphQL index if it becomes accessible again.

- Lao PDR:
  - Lao State Fuel appears stale in recent checks; validate freshness and consider de-emphasizing in favor of KPL notices.

- Samoa:
  - Regulator page is descriptive and links “Price Control Order” PDFs; evaluate if fuel is covered and whether OCR/PDF parsing is worth adding as an additional source.

- China:
  - Runtime tmp paths include repo-root `_cn_ndrc_tmp/`; quarantine/normalize temp directory handling (module-local runtime temp preferred).

## Temporary / Runtime Folders (No Cleanup Yet)

Known candidates (from `CPI-M-FUEL-STEP1.md`):

- `src/cpi/fuel_prices/fetchers/_to_mted_tmp/` (tracked legacy temp artifact)
- `src/cpi/fuel_prices/fetchers/_ws_mof_tmp/` (runtime temp dir)
- `src/cpi/fuel_prices/fetchers/_vn_plx_tmp/` (runtime temp dir)
- `_cn_ndrc_tmp/` (runtime temp dir, repo-root)
- `_cn_ndrc_tmp_test/` (local debug/test temp dir)

Policy: do not delete/clean OCR tmp artifacts without an explicit confirmation.

## Operational Dependencies

- OCR: `tesseract` for Samoa (and any image-table sources).
- Playwright: required for JS-rendered sources and Pertamina announcement tables.
- PDF parsing: `pdfplumber` (used by some fetchers).

## Next Checkpoint

- Commit the Fuel Step 1 baseline (including `src/cpi/fuel_prices/` and this status file) onto `cpi-migration`.
- Fast-forward `cpi-migration-fuel` to match.
- Create a Step 2 task list that focuses on extraction boundaries and temp-dir hygiene (no behavior changes).
