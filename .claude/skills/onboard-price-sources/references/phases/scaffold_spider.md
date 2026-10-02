# Phases 5A + 7 — scaffold a spider, then iterate on failures

*(scaffolding = spider only — a fetcher candidate belongs in `scaffold_fetcher.md`)*

Templates with full code skeletons — CrawlSpider HTML, Playwright listing-card, JSON
API — are in `../spider_templates.md`. Pick the one matching the candidate's tier.
Manifest field table and worked examples: `../yaml_schema.md`.

## Phase 5A — Spider + manifest

Three things per viable candidate.

### 1. Spider file — `src/prices/price_scraping/spiders/<source>.py`

- File and class names must be valid Python identifiers: `street11_kr.py` /
  `Street11KrSpider`, not `11street_kr.py`.
- The `name = "<source>"` attribute becomes the `--source` CLI value.
- **Currency: 3-letter ISO 4217, set at the spider class level.** Never derive it from
  the displayed symbol — "$" is BND in Brunei, USD in Cambodia, NZD in several Pacific
  markets. `countries.yaml` is the *default*, not the override: when the site returns an
  explicit machine-readable currency code (`prices.currency_code` on
  Shopify/WooCommerce, a `currency` field in a JSON API), use **what the site returns**.
  `tongamarket` prices in NZD and `niront` (KH) in USD, both against a different
  `countries.yaml` default.
- **Minor-unit traps.** Some platform APIs return integer minor units: WooCommerce Store
  API returns minor units alongside a `currency_minor_unit` exponent (divide by
  `10**currency_minor_unit`); Vendure `shop-api` returns **thousandths** (divide by
  1000). A 100× or 1000× price error reaching the corpus is far more damaging than a
  missing source — eyeball the first extracted price against the rendered page.
- **Never stamp one URL on several products.** `pipelines.py`'s `DuplicationPipeline`
  hashes `item["url"]` and drops repeats, so a spider that parses ten products off a
  listing page and emits the listing URL for all ten keeps **one**. `willys_se`'s first
  draft lost ~80% of its rows this way; `talabat_eg` hit it on multi-item pages. Build a
  per-product URL from the id or slug when the payload has none — and never substitute
  `None` (the pipeline's `item.get("url", "")` default only fires when the key is
  *absent*, so `None` raises) or a constant (which collapses the catalog to one row).
- **Do not set the User-Agent through `custom_settings["USER_AGENT"]`.** It is a
  dead-letter setting repo-wide: Scrapy's `UserAgentMiddleware` is disabled and
  `CustomUserAgentMiddleware` overwrites the UA on every request anyway. Disable that
  middleware per-spider and set the header on each `Request` (as `plus_nl` does for
  Googlebot SEO rendering). Scrapy's `USER_AGENT` does not reach a Playwright context
  either — that needs `PLAYWRIGHT_CONTEXTS`.
- **Do not set `IMPERSONATE_PROFILE` without disabling `RandomBrowserMiddleware`.** It
  clobbers the spider's profile unconditionally from `IMPERSONATE_BROWSERS`, pinned
  repo-wide to `chrome120`, so a correctly-chosen TLS profile silently does nothing.
  Narrow `IMPERSONATE_BROWSERS` in that spider's own `custom_settings`. `kalico_gd`
  needed both halves; `cassandraonlinemarket_ht` established the pattern.

### 2. Selectors entry — `src/prices/price_scraping/selectors.py`

Only for `extraction_pattern: scrapy_html` spiders using the shared `SelectorExtractor`.
`scrapy_api` and `scrapy_playwright` (listing-card) spiders bypass the registry and put
selectors inline.

### 3. YAML manifest — `src/prices/configs/<region>/<subregion>/<country>/<source>.yaml`

Three rules worth repeating, because each has broken discovery in practice:

- Path-derived fields (`region`, `subregion`, `country`, `source`) must **not** appear in
  the body — the loader reads them from the path.
- `channel:` must be **present on every manifest**, `null` included. A missing key or an
  out-of-enum value breaks the *global* `collect --list`, not just that source.
- `fallback_date` is the first-run cutoff for fetchers. Set it too recent and run 1
  returns nothing.

### 4. Record which page family the spider parses

One line in the manifest's `notes`: `listing`, `PDP`, `both`, or `API` (a spider reading
a JSON endpoint that never fetches a page). Write it even when it seems obvious.

This is the single fact the Common Crawl side cannot read off a config, and it determines
the archive regex shape. It is a *hint*, not the answer — the regex must accept every
price-bearing family the archive holds, which may be one the spider never touches.
Without it the archive side is guessing.

Say **which page family you characterised any markup spec from**, too. A spec that is
correct about a page the archive barely holds passes review and then returns zero — this
happened on `ckgreaves_vc`, where a correct department-page spec was written against an
archive holding PDPs under a different card class.

Note the `API` case specially: such a spider emits collected URLs that are permalinks it
never fetched (`boutiqueacm_mc`) or bare API routes that are not browsable at all
(`comoresenligne_km`). Neither can validate an archive regex locally.

### Then confirm discovery

```bash
python run.py prices collect --list | grep <new spider name>
```

If a manifest does not appear, the most common cause is a wrong country slug — the
loader silently drops files under unknown country directories.

---

## Phase 7 — Iterate on failures

| Symptom | Cause | Fix |
|---|---|---|
| `item_scraped_count: 0`, many "Could not extract" warnings | URL filter too broad — fetching blog / article / disease pages | Tighten `deny=` with the site's non-product path prefixes (`/bai-viet/`, `/benh/`) and/or narrow `allow=` to a 2-segment path |
| `product_name` is "sale" or other badge text | `a::attr(title)` matched a discount badge first | Reorder: `img.product::attr(alt)` / `img::attr(alt)` before any anchor title |
| `product_name` is a brand/short slug, not the title | Card has two `<a>` to the same PDP; the image-wrap anchor came first | Pick by selector class (`a.product-name::attr(href)`) or iterate `card.css("a")` and take the one whose text is longer |
| >120 s and zero items | Listing has not hydrated within Playwright's wait window | `wait_for_timeout` to 8000 ms, add a second scroll pass, OR switch to API sniff (Tier 1B) |
| `ERR_CONNECTION_RESET` during `goto` | CDN-level bot block on origin; a real browser would also need a residential IP | Skip; log the verdict with lever and tell |
| HTTP 429 on API with cookie warmup | Dynamic security header (`x-security-key`) generated by client-side JS | Skip — reverse-engineering the key is rarely worth it |
| Probe passed, spider 403s every request | `RandomBrowserMiddleware` clobbering the profile, or a JS PoW stub `curl_cffi` clears and Scrapy does not | Suspect the middleware before the site |
| Flat row count across structurally different sources | Platform-level truncation, not your paginator | All 8 Lezzoo (IQ) venues return exactly 60 items regardless of size. A Magento row count is never a catalog size |

Re-run only the failing source key(s). **Log the outcome to the probe log either way** —
a source that probe-passed and then failed to scaffold is a distinct, useful verdict.

---

**STOP. Read `report.md` before continuing.**
