---
name: onboard-country-price-sources
description: "Discover, scaffold, and end-to-end-test new e-commerce price-scraper sources for ONE country of the Pacific Observatory `prices` pipeline. Use this skill whenever the user wants to expand price-source coverage for a single country — phrases like 'find new sources for Indonesia', 'add supermarkets in Brunei', 'expand price scraping in Vietnam', 'we have no sources for Korea', 'scout pharmacies in Myanmar', or references `src/prices/configs/` and a country slug. Performs web search → Tier 1 (HTML/CSS/API) vs Tier 2 (Playwright) classification → feasibility probing → spider scaffolding + YAML manifest under the region/subregion/country convention → automated test with `prices collect --max-items 5`. For region- or subregion-wide work, the user should re-invoke once per country."
---

# Onboard Country Price Sources

Discover and onboard new e-commerce / supermarket / pharmacy price-scraper sources for ONE country in the Pacific Observatory `prices` pipeline. The deliverable is one or more working spider files plus YAML manifests under `src/prices/configs/<region>/<subregion>/<country>/`, each verified by an end-to-end test run.

## When to use

- The user gives one country slug (or a country name you can resolve to a slug via `src/configs/regions.yaml` + `src/configs/countries.yaml`).
- They want to *add* sources, not modify existing ones — for a single named URL, prefer iterating on that source directly without this skill.
- For region- or subregion-wide expansion, run this skill once per country (the discovery and scoping work is country-specific). Don't try to bundle multiple countries in one invocation — selectors, anti-bot signatures, and start URLs are too country-specific to batch.

## Why this is a single-country skill

In practice every country has its own dominant retailers, its own CDN/WAF stack (e.g. MWG-owned `bachhoaxanh.com` + `nhathuocankhang.com` share the same CONNECTION_RESET bot block; Foodstuffs NZ runs Akamai on Woolworths/PAK'nSAVE/New World as a unit), its own language for product names and category slugs, and its own conventions for product URL patterns. Batching countries forces shallow guessing; one-country runs let you actually open each PDP and verify a selector before scaffolding.

## Repo entry points

- Country topology / slug validation: `src/configs/regions.yaml`, `src/configs/countries.yaml`
- Existing price-source manifests: `src/prices/configs/<region>/<subregion>/<country>/<source>.yaml`
- Spider code: `src/prices/price_scraping/spiders/`
- Centralized CSS selectors registry: `src/prices/price_scraping/selectors.py` (only HTML/CSS spiders read from this; API spiders and listing-card spiders bypass it)
- Scrapy + Playwright settings: `src/prices/price_scraping/settings.py` (do not edit unless explicitly asked)
- CLI: `python run.py prices collect --source <name> --max-items N`, `python run.py prices collect --list`
- Data output: `data/prices/<region>/<subregion>/<country>/<source>/raw_items/<source>_<ts>.jsonl`

## Workflow

Each phase has a clear deliverable. Don't skip phases — every shortcut we've taken in the past (inventing selectors without probing, batching countries, trusting WebFetch on SPAs) has produced spiders that emit zero records.

### Phase 1 — Resolve country and inventory existing coverage

1. Take the country input (slug or name) and resolve it to a canonical slug from `src/configs/regions.yaml`. Watch for non-obvious slugs:
   - `lao_pdr` not `laos`
   - `taiwan_china` not `taiwan`
   - `hong_kong_sar_china` not `hong_kong`
   - `korea_dem_peoples_rep` (North) vs `south_korea` (South) — confirm which one if ambiguous
   - `brunei_darussalam` not `brunei`
   - `papua_new_guinea`, not `png` or `papua`
2. Determine the country's subregion from `regions.yaml` — this is the path component you'll use later (e.g. `eap/southeast_asia/vietnam`).
3. Read `src/prices/configs/<region>/<subregion>/<country>/` to list **already-covered sources**. Pass these to the discovery web search as exclusions so the candidate list isn't 80% duplicates.
4. Read `src/configs/countries.yaml` to learn the country's `languages:` and `currency:` — these inform spider defaults (currency code, language tag in the YAML manifest).

### Phase 2 — Discover candidates via web search

Delegate to a sub-agent (or run inline if the country has few existing retailers). Brief the agent with:
- The target country and its WB region/subregion
- The list of already-covered sources to exclude
- The 6 categories to probe: **supermarket online, pharmacy online, general e-commerce, hypermarket, fresh-grocery / delivery, specialty / convenience**
- Return: a candidate table with site name, URL, category, breadth signal (small / medium / large), and a sample listing URL

Aim for 8–20 candidates. Cast wide — feasibility filtering happens in Phase 3.

The web research is the most expensive phase if done sloppily. Tell the sub-agent to prefer English-translated landing pages where they exist (e.g. `global.oliveyoung.com` instead of `oliveyoung.co.kr`) — they're usually easier to scrape and have the same catalogue.

### Phase 3 — Tier classification + feasibility probing

For each candidate, classify into one of four buckets. **Don't write selectors before classifying** — most "obvious" selectors are wrong on SPA sites because the body hasn't hydrated yet.

```
                        ┌───────────────────────────────────────┐
                        │ Tier 1A — HTML/CSS, server-rendered    │
                        │ Example: rbpatel.com.fj, ghl.com.bn   │
                        │ Build: CrawlSpider, no Playwright     │
                        └───────────────────────────────────────┘
                                       ↑ yes
curl with browser UA → does the response have h1, og: meta, AND a price visible in raw HTML?
                                       ↓ no
                                       ↓
                        ┌───────────────────────────────────────┐
                        │ Tier 1B — JSON API, no auth           │
                        │ Example: api-crownx.winmart.vn        │
                        │ Build: scrapy.Spider hitting the API  │
                        └───────────────────────────────────────┘
                                       ↑ yes (after API sniff)
sniff with Playwright network-capture → is there a /api/, /v1/, /v2/, /graphql endpoint
that returns ≥5KB JSON with product fields AND works with curl when only Origin/Referer
headers are set?
                                       ↓ no
                                       ↓
                        ┌───────────────────────────────────────┐
                        │ Tier 2 — Playwright-rendered HTML     │
                        │ Example: carrefour_tw, citymall_mm    │
                        │ Build: scrapy.Spider with Playwright  │
                        │        meta + PageMethod waits        │
                        └───────────────────────────────────────┘
                                       ↑ yes
Playwright dump with 6-8s wait + scroll → are product cards present with name + price
text in the rendered HTML?
                                       ↓ no
                                       ↓
                        ┌───────────────────────────────────────┐
                        │ SKIP — document the reason            │
                        │ • Cloudflare/Akamai/PerimeterX 403    │
                        │ • ERR_CONNECTION_RESET (CDN bot block)│
                        │ • Empty PDP / login wall              │
                        │ • App-only (no web catalogue)         │
                        │ • Aggregator with no per-product URLs │
                        │ • Heavy JS that doesn't hydrate at 8s │
                        └───────────────────────────────────────┘
```

Concrete probe commands and scripts live in `references/probe_patterns.md`. Pre-known blockers we already classified (so you don't waste cycles re-probing) live in `references/known_blockers.md` — **check this first** before probing.

For Tier 2 sites, the Playwright probe should also dump the HTML to `/tmp/probe_<key>_listing.html` and `/tmp/probe_<key>_pdp.html` so the selector-extraction phase has files to grep instead of re-fetching.

**When both curl and Playwright return 403 on the same site, stop.** Headless Chromium without a residential proxy and a captcha solver will not break a real Cloudflare/Akamai/Incapsula challenge. Don't iterate on it — add the site to `references/known_blockers.md` (Cloudflare / AWS WAF / Akamai section) and move on. Past attempts to push through with longer waits or stealth flags have not paid off.

### Phase 4 — Extract real selectors

For each non-skipped candidate, open the dumped HTML (Tier 2) or the live page (Tier 1) and identify:

- **product_name**: prefer a stable attribute like `[data-test="product_name"]` (Long Chau) or `<img>` alt text on a product card (City Mall MM). Avoid `<a>::attr(title)` as a high-priority fallback — overlay badges (e.g. "sale") frequently steal that selector. Always try `meta[property='og:title']::attr(content)` as a fallback for PDPs.
- **price**: look for a specific class like `att-product-detail-latest-price` (Co.opmart) or `data-price` attribute (Carrefour TW). On atomic-CSS sites (Sayurbox-style Twitter/RN-Web classes), there is no clean selector — extract via text regex (`Rp\s?[0-9.,]+`) instead.
- **product_id**: SKU / barcode / canonical-URL-trailing-id. Often a `meta[property='product:retailer_item_id']`, an `<input name='id'>`, or parsable from the URL.
- **category**: breadcrumb. Many sites have no inline breadcrumb on PDP — leave it null rather than invent one.

Verification rule: **before scaffolding, every selector must have been observed matching the right text in a real dumped HTML file.** This is the single biggest determinant of whether the spider works on first run.

The three spider templates (CrawlSpider HTML, Playwright listing-card, JSON API) with full code skeletons are in `references/spider_templates.md`. Pick the one that matches the candidate's tier.

### Phase 5 — Scaffold spider + manifest

For each viable candidate, create three things:

1. **Spider file**: `src/prices/price_scraping/spiders/<source>.py`
   - File name and class name must be valid Python identifiers (`street11_kr.py` / `Street11KrSpider`, not `11street_kr.py`)
   - The spider's `name = "<source>"` attribute can be anything; this becomes the `--source` CLI value
   - Currency: 3-letter ISO 4217 (VND, IDR, KRW, MMK, ...) from `countries.yaml`
2. **Selectors entry** in `src/prices/price_scraping/selectors.py` — only for Tier 1A HTML spiders that use the shared `SelectorExtractor` pattern. Tier 1B API spiders and Tier 2 listing-card spiders bypass the registry and put selectors directly in the spider.
3. **YAML manifest**: `src/prices/configs/<region>/<subregion>/<country>/<source>.yaml`
   - Required body fields: `spider: <name>` and `language: <code>`
   - Do NOT put region/subregion/country/source in the YAML body — they are derived from the file path by `core.config.parse_config_path()`. Duplicating them breaks the loader.
   - Add `notes:` if there's something a future maintainer should know (e.g. "Uses internal JSON API — no Playwright needed", "Skeleton selector requires re-probing if site updates")
   - Add `active: false` only if the spider is intentionally disabled

After writing all three for each candidate, run `python run.py prices collect --list` and grep for each new spider name to confirm the discovery layer picks them up. If a manifest doesn't appear, the most common cause is a wrong country slug — the loader silently drops files under unknown country directories.

### Phase 6 — Automated end-to-end test

Run each new spider with `--max-items 5`. The CLOSESPIDER_ITEMCOUNT setting only stops the spider *after* a fetch returns more than 5 items, so a successful spider typically writes 5–40 records. Anything less means selectors or URL filters are off.

**macOS has no `timeout` builtin.** Use this pattern to cap each run:

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

Batch in groups of 3–4. Running too many spiders in parallel exhausts Playwright's chromium pool and they fail silently.

After the run, find the output files with `find data/prices -name "*.jsonl" | xargs ls -lt | head` and inspect the first record per spider. A successful record has:
- non-null `product_name` (matching what's on the site)
- non-null `price` (a numeric or properly-formatted string)
- correct `currency`
- a working `url`
- a real `product_id` (or `null` if the site doesn't expose one — fine)

### Phase 7 — Iterate on failures

Common failure modes and fixes (each one we've actually hit in prior runs):

| Symptom in log / data | Cause | Fix |
|---|---|---|
| `item_scraped_count: 0`, many "Could not extract" warnings | URL filter too broad — spider is fetching non-product pages (blog, disease info, articles) | Tighten the `deny=` regex with the site's non-product path prefixes (e.g. `/bai-viet/`, `/benh/`) and/or narrow `allow=` to a 2-segment path |
| `product_name` is "sale" or other overlay-badge text | `a::attr(title)` matched a discount badge before the real product anchor | Reorder selectors: `img.product::attr(alt)` / `img::attr(alt)` before any anchor title |
| `product_name` looks like a brand/short slug instead of the full title | Card has two `<a>` elements pointing at the same PDP — image-wrap anchor came first, product-name anchor came second. `card.css("a::attr(href)").get()` returns the image anchor's URL but the visible name lives in the *other* anchor | Pick the anchor by selector class (e.g. `a.product-name::attr(href)`) or iterate `card.css("a")` and choose the one whose text is longer than the badge text |
| Spider takes >120s and yields zero items | Listing page hasn't hydrated within Playwright's wait window | Increase `wait_for_timeout` to 8000ms, add a second scroll pass, OR switch to API sniff (Phase 3 Tier 1B) |
| `ERR_CONNECTION_RESET` during `goto` | CDN-level bot block (MWG/Akamai/Cloudflare on origin). Real browser would also need a residential IP | **Skip this site**, document in `references/known_blockers.md` |
| HTTP 429 on API with cookie warmup | API has a dynamic security header (e.g. `x-security-key`) generated by client-side JS | Skip — reverse-engineering the key is rarely worth it |

After fixing, re-run only the failing spider(s), not the whole batch.

### Phase 8 — Report and document

Output a final summary with:

- **Working spiders**: name, country, item count from the test run, one sample record (raw JSON line)
- **Skipped sites**: name, URL, reason (use the bucket names from Phase 3 so they're consistent and searchable)
- Append new blockers to `references/known_blockers.md` so the next run skips them faster

Then save an engram memory observation (type: `discovery`) titled something like "Onboarded N price sources for <country>" with the working list and the new blockers.

## Quick reference

- **Spider templates** (3 patterns): `references/spider_templates.md`
- **Probe scripts** (curl, Playwright dump, API sniffer): `references/probe_patterns.md`
- **Known blockers** (skip-on-sight list): `references/known_blockers.md`

## Anti-patterns to avoid

- Don't invent selectors. If the probe HTML is empty or hydration didn't complete, either fix the probe or skip the site — guessed selectors waste an entire iteration cycle.
- Don't put `region:`, `subregion:`, `country:`, or `source:` in YAML manifest bodies. Path-derived; redundant; breaks the loader.
- Don't add a spider's currency by parsing the price symbol — set it at the spider class level (`currency = "VND"`). Sites that display "$" for Brunei dollars (BND) will be miscoded otherwise.
- Don't batch multiple countries in one run. Each country has its own retailers, CDNs, and product URL conventions — the discovery work is what costs time, not the scaffolding.
- Don't trust scout sub-agents that say "selectors_unknown: true" — that's a signal to do a real Playwright probe, not to invent selectors anyway. Pre-Tier-A probing caught 9/16 sites that would have shipped broken if we'd trusted the WebFetch-only scout.
