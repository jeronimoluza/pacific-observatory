# Prices — Architecture

The map of the whole pipeline. For the deep design of the enrich stage (where all
the complexity lives) see `ENRICH.md`. For terminology see `GLOSSARY.md`.

## What it produces

Raw scraped retail product rows (spiders + fetchers, six WB regions, currently
**EAP food-&-beverage PoC scope**) → COICOP-classified, trust-graded unit-value
price observations for PPP / real-exchange-rate analysis. Precision over coverage
everywhere: both audit layers **quarantine, never fabricate**; only rows with
`trust_level=="high" AND trust_uv=="high"` ship.

## Stages

Like every pipeline in this repo, prices follows `collect → build → publish` on
top of `src/core/`, with an enrich step (`process`) between collect and build.

```
collect → outputs/prices/raw/raw_prices.csv            (per-source spiders + fetchers)
    │
    ▼  prices process        (STAGE_ORDER in enrich/cli.py)
  concatenate → outputs/prices/raw/raw_prices.csv       (unify raw_items/wayback/CC → one CSV)
  prepare     → data/prices/enrich/products_input.parquet   (dedup to one row / input_hash)
  classify    → data/prices/enrich/cache/classified.parquet (extract + embedding→head + vetoes)
  merge       → outputs/prices/enriched/enriched_prices.csv  (raw × enrichment, per observation)
    │
    ▼  prices build          (build/aggregate.py)
  eap_fnb_snapshot.parquet        (from products_input, dated today)
  eap_fnb_observations.parquet    (from raw CSV, monthly history)
    │
    ▼  prices publish → outputs/prices/eap_fnb_dashboard.html
```

### collect (`price_scraping/` spiders + `fetchers/`)
Scrapy spiders and standalone per-source fetchers, unified under `prices collect`.
Spiders write `raw_items/*.jsonl`; the resumable Wayback runner (`backfill/`) and
the Common-Crawl WARC ingest (`common-crawl`) write their own shapes. Sources are
declared as per-region/subregion/country YAML under `configs/`.

### process (`enrich/`) — the four sub-stages
- **concatenate** — unifies the scraped shapes (`raw_items/`, `wayback_items/`,
  `common_crawl_data/`) into one `raw_prices.csv`. Fetcher `price_observations.csv`
  is **intentionally not wired in** — those carry non-grocery lines (services,
  rentals) deferred until the messy-product classifier is solid. Deliberate scope
  boundary, not a gap.
- **prepare** — dedups to one row per `input_hash` → `products_input.parquet`.
- **classify** — runs the two independent enrichers on each unique RAW name
  (structural extraction + the embedding→head classifier + vetoes) →
  `classified.parquet`, keyed by `input_hash`. **See `ENRICH.md`.**
- **merge** — joins raw × enrichment back to per-observation grain →
  `enriched_prices.csv`.

### build (`build/aggregate.py`)
Joins `classified.parquet` to the price side on **`input_hash`** (exact — classify
inherits `products_input`'s hash unchanged). Keeps F&B-prefix ×
`state∈{narrow_source,classified}` × `trust_level=="high"`, then canonicalizes the
unit per leaf → computes unit_value → applies the Layer-2 flag → attaches FX/USD.
Scoped to the EAP food-&-beverage PoC basket; region/subregion/country flags are
accepted but ignored until the basket widens.

### publish (`build/publish.py`)
Renders `outputs/prices/eap_fnb_dashboard.html` with vendored/inlined Chart.js
(WB intranet blocks CDNs).

## Directory map (`src/prices/`)

| Path | Role |
|---|---|
| `price_scraping/` | Scrapy project + spiders (collect) |
| `fetchers/` | Standalone per-source fetchers (collect) |
| `backfill/` | Resumable Wayback runner |
| `configs/` | Per-region/subregion/country source YAML (+ `_examples/template.yaml`) |
| `enrich/` | The process stage: extract, embedding→head classify, vetoes, audit, merge |
| `build/` | Aggregate + unit-value audit + publish (EAP F&B PoC scope) |
| `tools/` | Offline maintenance scripts (importers, comparators) |
| `docs/` | This documentation set |

## CLI

Entry point `python run.py prices <verb>` (installed alias `po prices <verb>`).
Live verbs: `collect, backfill, common-crawl, process, eval, match-record,
census, train-classifier, label, build, publish`. There is **no** `prices classify`
verb — classification is a sub-stage of `process` (see `GLOSSARY.md` Retired).
