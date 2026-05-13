# Diagnose + Fix Loop

How to take a stuck source from "0 successfully scraped" → fixed config + seeded ledger → green smoke test, autonomously.

## Step 1: Snapshot pending state

```python
import csv
from pathlib import Path

SRC = Path("data/text/<region>/<subregion>/<country>/<source>")
news = set()
with (SRC/"news.csv").open() as f:
    for row in csv.DictReader(f):
        if row.get("url"):
            news.add(row["url"])

pending = []
with (SRC/"urls.csv").open() as f:
    for row in csv.DictReader(f):
        u = row.get("url","")
        if u and u not in news:
            pending.append((row.get("date",""), u))

print(f"news.csv: {len(news)}")
print(f"pending : {len(pending)}")
```

If `pending == 0`, the source isn't actually stuck — it's caught up. Bail out of the loop, mark source as `current`.

If `pending > 0`, distribution by year tells you whether the issue is recent or universal:

```python
buckets = {}
for d, u in pending:
    yr = d[:4] if d else "?"
    buckets.setdefault(yr, []).append((d, u))
print({k: len(v) for k, v in sorted(buckets.items())})
```

## Step 2: Stratified probe

Sample 1 URL per year. For each URL, probe three layers:

```python
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import random
random.seed(42)

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0"
BASE = "https://<source-base-url>"  # from YAML's base_url
CONFIGURED_BODY = ".configured-selector p"  # from YAML's selectors.article.body

for yr, lst in sorted(buckets.items()):
    if not lst: continue
    d, u = random.choice(lst)
    slug = urlparse(u).path.strip("/").rstrip("/")

    # Layer 1: WP API content.rendered
    api = requests.get(f"{BASE}/wp-json/wp/v2/posts?slug={slug}", timeout=20, headers={"User-Agent": UA})
    api_len = -1
    if api.status_code == 200:
        data = api.json()
        if data:
            api_len = len(data[0].get("content",{}).get("rendered",""))

    # Layer 2: HTML against configured selector + fallbacks
    html = requests.get(u, timeout=20, headers={"User-Agent": UA})
    soup = BeautifulSoup(html.text, "html.parser")
    results = {}
    for sel in [CONFIGURED_BODY, ".entry-content p", "article p", ".td-post-content p",
                "div.elementor-widget-theme-post-content p", ".tdb_single_content p",
                ".post-content p", ".single-post-content p"]:
        ps = soup.select(sel)
        text = " ".join(p.get_text(" ", strip=True) for p in ps)
        results[sel] = (len(ps), len(text))

    # Layer 3: meta date selector
    meta = soup.select_one('meta[property="article:published_time"]')
    meta_date = meta and meta.get("content")

    print(f"  {yr} | API={api_len:5d} | HTML status={html.status_code}")
    for sel, (n, l) in results.items():
        if l > 50:
            print(f"    SELECTOR WORKS: {sel}: {n} paragraphs, {l} chars")
    print(f"    meta date: {meta_date}")
```

## Step 3: Classify outcome

Match the probe results to one of the four patterns in `known_stuck_patterns.md`:

| Probe outcome | Pattern | Action |
|---|---|---|
| All sample URLs return API=0 + all HTML selectors=0 + only `<div.textwidget>` (footer) text | **Empty-body posts** | Keep selector good for new articles; pre-seed ledger with all pending URLs |
| API=0 but ONE of the fallback selectors returns >100 chars across all samples | **Wrong selector** | Update YAML article.body to the working selector |
| HTML status 4xx, body contains "challenge" / "captcha" / "Cloudflare" | **Cloudflare** | Mark DEFERRED, escalate to human |
| pending == 0 after probe (e.g. listing API found new URLs and they all scraped fine) | **Genuinely silent** | No fix needed |

Edge cases:
- **Mixed**: some URLs work with a fallback selector, others are body-empty. Pick the working selector AND pre-seed the body-empty subset. The probe already separates these (samples with `len(text) > 50` use the new selector; samples with all selectors at 0 chars go to ledger).
- **Date selector missing**: if the YAML has `article.body` but no `article.date`, add `date: "meta[property='article:published_time']::attr(content)"` regardless. The Yoast meta tag works on >90% of WP sites and is harmless when present elsewhere (selector simply doesn't match).

## Step 4: Apply the fix

### 4a. Config edit (YAML)

Read the source's YAML, then `Edit` the `article` block. Common shape:

```yaml
selectors:
  thumbnail:
    container: "filler"     # API mode — fine to leave
    title: "filler"
    url: "filler"
  article:
    body: "<discovered-working-selector>"
    date: "meta[property='article:published_time']::attr(content)"
```

### 4b. Ledger pre-seed (when pattern = empty-body posts)

Write a per-source seed script under `/tmp/seed_<source>_ledger.py` based on `scripts/seed_ledger_template.py`. Key properties:
- Preserves any existing ledger entries (don't clobber operator-curated rows).
- Adds pending URLs with `last_status=NO_BODY` and a descriptive `last_error`.
- Idempotent — re-running won't double-seed.

Then invoke: `poetry run python /tmp/seed_<source>_ledger.py`. Print the script path so the user can review before the next run.

The ledger schema (from `src/text/scrapers/pipelines/storage/urls.py`):

```
url,first_failed_at,last_failed_at,attempts,last_status,last_error
```

## Step 5: Smoke-test the fix

```bash
poetry run po text collect --country <country> --source <source> --max-articles 5 2>&1 | tail -15
```

Read the per-source counter block at the end:

```
--- <source> (<country>) ---
Discovering thumbnails...
Thumbnails Discovered:           100
Articles Scraped:                 18
Skipped (ledger):               6836
```

The fix is **green** when ANY of:
- `Articles Scraped > 0` (selectors work, fresh articles found)
- `Skipped (ledger): N` matches the count we seeded AND `Thumbnails Discovered: 0` (the source is caught up; the seed just confirms it)

The fix is **red** when:
- `Articles Scraped: 0` AND `Thumbnails Discovered > 0` AND `Skipped (ledger): 0` — the discovered articles failed for a reason we didn't fix. Re-probe; you missed something.

When red, do not mark the source FIXED in the report. Mark FAILED with the smoke-test counter values quoted, so the human can pick up the diagnostic.

## Step 6: Re-launch the source

If the source was killed mid-orchestration, re-fire it as a detached single-source job so it can complete alongside the rest of the queue:

```bash
nohup bash -c '
  echo "[REFIRE-START] <country>/<source>"
  poetry run po text collect --country <country> --source <source> > /tmp/refresh_<country>__<source>.log 2>&1
  ST=$?
  if [ $ST -eq 0 ]; then echo "[REFIRE-DONE ] <country>/<source>"; else echo "[REFIRE-FAIL ] <country>/<source> (exit $ST)"; fi
' > /tmp/refresh_refire_<source>.log 2>&1 &
disown
```

Or, if it's the last/only source in single-source mode, just let the smoke-test cover it.
