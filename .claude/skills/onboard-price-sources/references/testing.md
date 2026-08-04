# Phase 6 — end-to-end test harness

## The shipping gate

A source is **viable** (ships as a manifest) if and only if the probe passed *and* the test run returns ≥ 5 valid rows. "Valid" means non-null `observation_date`, a `price_local` or `index_value`, correct currency, and a real `item_name` (or `null` where the site doesn't expose one and the schema doesn't require it).

Sources that probe-pass but produce 0–4 rows **fail** and do not ship — record them in the Phase 8 skipped list with the row count and a one-line hypothesis.

## Spiders

Run each new spider with `--max-items 5`. `CLOSESPIDER_ITEMCOUNT` only stops the spider *after* a fetch returns more than 5 items, so a healthy spider typically writes 5–40 records. Fewer means selectors or URL filters are off.

**macOS has no `timeout` builtin.** Cap each run like this:

```bash
cd /Users/jeronimoluza/wb/pacificobservatory/repo/template-repo
for src in <name1> <name2> <name3> <name4>; do
  poetry run python run.py prices collect --source $src --max-items 5 > /tmp/$src.log 2>&1 &
done
echo "Waiting up to 120s..."
sleep 120
pkill -TERM -f "run.py prices collect" 2>/dev/null
pkill -TERM -f "scrapy" 2>/dev/null
sleep 3
pkill -KILL -f "run.py prices collect" 2>/dev/null
pkill -KILL -f "chrome-headless" 2>/dev/null
wait 2>/dev/null

for src in <name1> <name2> <name3> <name4>; do
  echo "--- $src ---"
  grep -E "item_scraped_count|finish_reason|Could not extract" /tmp/$src.log | tail -5
done
```

Batch in groups of 3–4. Too many spiders in parallel exhausts Playwright's chromium pool and they fail silently.

Then find the output with `find data/prices -name "*.jsonl" | xargs ls -lt | head` and inspect the first record per spider. A successful record has:

- non-null `product_name`, matching what's on the site
- non-null `price` — **eyeball the magnitude against the rendered page**; minor-unit platforms (WooCommerce, Vendure) silently produce 100×/1000× errors
- correct `currency`
- a working `url`
- a real `product_id` (or `null` if the site doesn't expose one — fine)
- non-null `category` (the audit trail for downstream classification; null isn't fatal but makes the row much harder to adjudicate later)

## Fetchers

Fetchers run through the same `collect` command as spiders — there is no separate `prices fetch`. The cutoff comes from the manifest's `fallback_date` on the first run, since there's no CSV yet to read one from.

```bash
cd /Users/jeronimoluza/wb/pacificobservatory/repo/template-repo
for src in <source1> <source2>; do
  poetry run python run.py prices collect --source $src > /tmp/$src.fetch.log 2>&1 &
done
sleep 120
pkill -TERM -f "run.py prices collect" 2>/dev/null

for src in <source1> <source2>; do
  echo "--- $src ---"; tail -5 /tmp/$src.fetch.log
done
```

For a tighter loop during development, import and call the fetcher directly — same contract, no persistence:

```python
import sys; sys.path.insert(0, "src")
from datetime import date
from prices.fetchers.<region>.<subregion>.<country>.<source> import fetch_<source_key>

df = fetch_<source_key>(date(2020, 1, 1))
assert df is not None and len(df) >= 5, f"only {0 if df is None else len(df)} rows"
print(f"OK: {len(df)} rows, span {df['observation_date'].min()} → {df['observation_date'].max()}")
```

The shipping gate is still the `collect` run — only `collect` exercises the cutoff layer and the writer.

A successful fetcher writes `data/prices/<region>/<subregion>/<country>/<source>/price_observations.csv` (or `index_observations.csv` for `cpi_benchmark`), whose first row should have:

- non-null `observation_date` (ISO YYYY-MM-DD)
- non-null `period_kind` (one of the enum values)
- non-null `price_local` for PriceObservation, or `index_value` for IndexObservation
- correct `currency` (PriceObservation only)
- the right `source_key`, matching the manifest
- `coicop_code` populated when `coicop_classification ∈ {source_curated, publisher_labeled}`; absent for `deferred_gemini`
- `subnational_area` set for sources that break down sub-nationally, `null` otherwise
