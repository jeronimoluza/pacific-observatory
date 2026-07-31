# 2026-07-31 — Systemic variant-drop fix + re-scrape + stale-run prune

## Goal

Follow-on to the batch-3 onboarding (`2026-07-31-eap-retail-candidate-onboarding.md`).
While verifying variant/store capture, we found a **systemic data-loss bug**: the
Shopify/Vendure "exploder" spiders emit one row per size-variant but stamped the
shared parent product url, so `DuplicationPipeline` silently dropped every variant
after the first. Fix it repo-wide, re-materialize the recovered rows, and prune the
now-stale pre-fix scrape runs.

## Root cause

`price_scraping/pipelines.py:29` — `DuplicationPipeline` dedups on
`hashlib.md5(item["url"])` (`url_hash`) and drops on collision (line 32). ~26
spiders `yield` inside `for v in product["variants"]` but built
`url = f"{BASE}/products/{handle}"` — the **parent url, identical across every
variant**. So the variant explosion was undone at the pipeline for exactly the
multi-size products it existed to capture. This also *corrected an earlier wrong
read*: the "distinct url_hash == rows" we'd measured was because the same-url
variant losers were already dropped before we counted, not because variants were
safe.

## Fix (commit `93367aab`)

One line per spider: append `?variant={variant_id}` to the row url (the variant
id — `v.get('id')` / `variant.get('id')` / `variant['id']` — was already in scope
everywhere). This makes `url_hash` distinct (survives `DuplicationPipeline`) **and**
gives a distinct downstream identity `(product_name_original, product_url)` in
`enrich/stages/prepare.py`. The id is source-derived (Shopify/Vendure JSON), never
regex-derived — so there is **no** risk of a regex false-negative merging genuinely
different variants (the identity is never computed from extracted fields).

26 exploders fixed. 24 tracked + committed in `93367aab`; `organica_vn` and
`hikiotonga` were pre-existing **untracked** spiders (committed YAMLs, spider files
never `git add`-ed — same as `capelle_nr`/`emart_mn`/`halodili`/`kurly_kr`), so
their fix is on-disk but not in that commit. `carrefour_tw` is NOT affected
("variants" there = zh/en url variants, one row per product via `productUrl`).
`ampm_pharmacy` was fixed separately (`fdeb5403`, WooCommerce, uses a distinct
`?attribute_packaging=` variation permalink).

### Verification

Bounded 400-item `alpro_pharmacy` scrape → **424 rows / 81 multi-variant products
survived** (was ~250), differing-price variants preserved (Love Earth Honey 75.60
vs 52.70; Medela 157.90 vs 166.90). Control `lemon_farm` = 500/500 single-variant
products, zero fabricated rows — the fix is a harmless no-op where a store genuinely
has one SKU per product.

## Full re-scrape (materialize the recovery)

`prices collect` has **no `--rebuild` flag** (that exists only on `fuel`/`text`);
each run is already a full re-scrape writing a new timestamped `raw_items/*.jsonl`.
Re-ran all 26 exploders in parallel — ~13.5 min, all exit 0, **133,008 rows @ 100%
price-fill, 0 failures.** Recovery is visible as inflated counts vs pre-fix
product-level baselines (pharmacies with deep size ladders exploded the most):

| source | rows | source | rows | source | rows |
|---|--:|---|--:|---|--:|
| life_pharmacy_nz | 25,000 | nz_online_chemist | 7,736 | goodzay | 4,395 |
| alpro_pharmacy | 17,153 | unichem_nz | 6,935 | niront | 3,433 |
| bargain_chemist | 14,664 | sherza | 5,523 | lemon_farm | 1,756 |
| new_world_fiji | 12,809 | chemist_plus | 4,817 | frankie_samoa | 1,242 |
| citysuper_hk | 11,783 | harris_farm_markets | 4,612 | druksell_bt | 910 |
| mustafa_online | 7,783 | … | | (rest 57–578) | |

`life_pharmacy_nz = 25,000` is genuine (`finish_reason: finished`, no item cap in
spider — deep cosmetic/vitamin size explosion). `harris_farm_markets` and
`lemon_farm` are unchanged from pre-fix (single-variant catalogs → no-op).

## Stale-run prune

`concatenate.py:143` unions **all** `raw_items/*.jsonl` per source, and
`prepare.py:195` groups by `input_hash` keeping `observation_date=max`. So enrich is
an **identity-latest snapshot, not a per-date time series** — the pre-fix runs
contribute nothing but (a) discontinued-product identities and (b) the pre-fix
parent-url **doppelgangers** of `variant[0]` (a *distinct* identity from the
`?variant=` row, so dedup can never collapse it — file removal is the only lever).

Pruned newest-only per source via `prune_stale_raw_items.sh` (dry-run default;
`--apply` quarantines by `mv`, `--hard` deletes). Ran `--apply`: **264 → 26 files
kept, 238 stale files quarantined** to `_stale_raw_items_quarantine_20260731T193149Z/`
(reversible; `rm -rf` to finalize once the pipeline is confirmed clean). Scoped to
the 26 exploders only — other ~270 sources' multi-run files are not lossy.

## Backlog

- **Untracked spiders** — `organica_vn`, `hikiotonga`, `capelle_nr`, `emart_mn`,
  `halodili`, `kurly_kr` have committed YAMLs but their spider files were never
  `git add`-ed. Hygiene gap; git-add them in a dedicated commit.
- **`new_world_fiji` variant names** — its GraphQL selection is `variants{id sku
  priceWithTax currencyCode}` (no per-variant `name`), so Fiji size ladders now
  disambiguate by url only, not by `product_name`. Add `name` to the variants
  selection so the extractor can read size from the name.
- Downstream: run `enrich → classify → build` against the pruned corpus (separate
  session) to fold the recovered variants into the F&B basket.

Related: [[eap_retail_batch3_20260731]], prior session
`2026-07-31-eap-retail-candidate-onboarding.md`.
