# Phases 5B + 7-fetcher — scaffold a fetcher, then iterate on failures

*(scaffolding = fetcher only — a spider candidate belongs in `scaffold_spider.md`)*

The fetcher module's contract, helpers and worked examples (REST API, PDF+OCR, XLS,
HTML tariff, CPI) are in `../fetcher_pattern.md` § 1. Manifest field table and six
worked examples: `../yaml_schema.md`.

## Phase 5B — Decide the location bucket first

**Bucket 1 — Country-bound** (Pertamina ID, FCCC fuel FJ, SP Group SG). ~80% of fetchers.
- Module: `src/prices/fetchers/<region>/<subregion>/<country>/<source>.py`
- Function: `def fetch_<source_key>(cutoff: date) -> pd.DataFrame | None`
- YAML: `src/prices/configs/<region>/<subregion>/<country>/<source>.yaml`

**Bucket 2 — Regional aggregator** (Shopee SEA shares API shape across SG/MY/ID/PH/TH/VN;
Watsons across HK/SG/MY/TW). One shared module, per-country wrappers, per-country YAMLs.
- Shared module: `src/prices/fetchers/_shared/<region>/<source>.py`
- Wrapper per country: `src/prices/fetchers/<region>/<subregion>/<country>/<source>.py` — re-exports the per-country callable
- YAML per country, with `module:` pointing at the wrapper

**Bucket 3 — Global aggregate series** (rare; WTI/Brent, IMF FX, WB Pink Sheet). One
module emits rows tagged with aggregate region labels (`country: "Global"`, `"EAP"`).
- Module: `src/prices/fetchers/_global/<source>.py`
- YAML: **one only**, at `src/prices/configs/_global/<source>.yaml` — not per-country,
  because the rows are global by definition

> **Bucket 3 has never been built.** Neither `src/prices/configs/_global/` nor
> `src/prices/fetchers/_global/` exists in the tree (verified 2026-09-17; the config
> regions are `_examples`, `eap`, `eca`, `lac`, `menaap`, `nca`, `sar`, `ssa`). The
> first source that genuinely needs it creates both directories. Until then, treat a
> "global" candidate with suspicion — most turn out to be Bucket 2, and the
> cost-of-living survey publishers that look global are not sources at all.

A multi-country source emitting *per-country* rows (WB ICP publishing one row per country
per basket item) is **Bucket 2, not 3** — the analyst side needs a YAML under each covered
country.

Do not write a country-bound fetcher when a `_shared/<region>/` aggregator already covers
the country. Add a thin wrapper and a per-country YAML instead.

## The contract, in short

One public `fetch_<source_key>(cutoff)` function. Emit `PriceObservation` or
`IndexObservation` rows per `analytical_role`. Idempotent skip on
`observation_date <= cutoff`. `observation_hash` set **last**. Drop unmappable COICOP
rows. Return `None` for no-new-data.

- **One file = one fetcher function = one source.** No `SOURCE_META = [...]`. All
  metadata lives in the YAML manifest; private module-level constants like `_BASE_URL`,
  `_CURRENCY` are recommended but not required.
- **Never mix PriceObservation and IndexObservation rows in one fetcher.** A source
  publishing both averaged prices and CPI indexes gets two fetchers and two manifests.
- **Never emit rows with null `coicop_code`** when `coicop_classification ∈
  {source_curated, publisher_labeled}`. Log a warning and drop — a null where the schema
  expects a value is pollution masquerading as coverage.
- **Do not force a fetcher-shaped source into a Scrapy spider.** PDFs, Excel files,
  regulator tariff tables and CPI publications belong here. Crawling a static
  stats-office page with Scrapy produces a fragile spider that does what
  `pd.read_html()` does in three lines.

## Manifest rules that break things

- Path-derived fields (`region`, `subregion`, `country`, `source`) must **not** appear in
  the body.
- `channel:` must be **present**, `null` included. A missing key or an out-of-enum value
  breaks the *global* `collect --list`.
- `fallback_date` is the first-run cutoff. Set it too recent and run 1 returns nothing.

## Then confirm discovery

```bash
python run.py prices collect --list | grep <new source_key>
```

The listing shows `fetcher=<module>:<function>`. If a manifest does not appear, the usual
causes are a wrong country slug or a missing `channel:` key.

There is **no separate `prices fetch` command** — earlier drafts of this skill said one
was planned. Fetchers are collected, listed and tested through `prices collect` like any
other source.

---

## Phase 7-fetcher — Iterate on failures

| Symptom | Cause | Fix |
|---|---|---|
| 0 rows, log shows "No new rows" | Cutoff is today and the source publishes monthly | Re-run backdated (`--cutoff 2020-01-01`) once during onboarding to verify against historical data |
| `pdfplumber` returns empty text | PDF is image-only (scanned) | Add the `_ocr_pdf()` helper from `../fetcher_pattern.md`; expect ~5–10× slower |
| Extracted price 10× or 100× off | Currency-display shorthand (`12,90` meaning IDR 12,900) | `_parse_<currency>_price()` helper that detects magnitude and normalizes |
| Bulk/drum prices leaking into a retail parse | Default search picks the *first* "SCHEDULE 1"; corrigenda leave a stale earlier table | Anchor on the **last** occurrence, slice until the next "Drum Sale" / "Bulk" marker |
| API returns 200 but rows lack a date | Rolling-window endpoint with no timestamps | Use the request date as `observation_date`, fall back to `Last-Modified`, or pair with a "yearly" endpoint that carries dates |
| Many "No COICOP mapping for X — dropping row" | `_COICOP_MAP` doesn't cover an item the source emits | Add it if it maps cleanly; accept the drop if it's an outlier you don't want in the basket |
| Duplicate rows on re-run | `observation_hash` computed before all key fields populated | Move `make_hash(row, _IDENT)` to the very end, after every `subnational_area` / `city` / `address` / `price_local` is set |

Re-run only the failing source key(s). **Log the outcome to the probe log either way.**

---

**STOP. Read `report.md` before continuing.**
