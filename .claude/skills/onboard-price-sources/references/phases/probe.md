# Phases 3 → 4 — feasibility probing and selector extraction

Every candidate passes through here, whatever produced it. **Every candidate leaves
a probe-log row — the ones that pass and the ones that don't.** A run that records
only its wins teaches the next run nothing, which is why the corpus has 2,731 shipped
manifests and no recoverable record of how any of them was found.

```bash
# before probing
python scripts/probe_log.py lookup <host>

# after probing, always, pass or fail
python scripts/probe_log.py append --run-id <id> --country <slug> --host <host> \
  --verdict <ok|blocked|no_catalog|app_only|out_of_scope|unreachable|needs_work> \
  --lever curl_cffi:chrome124,firefox133 --tell http-403 \
  --platform woocommerce --url-shape /wp-json/wc/store/v1/products \
  --discovery-method ddgs --discovery-detail "<the query that surfaced it>" \
  --rank-predicted 2
```

The appender **refuses** a `blocked` or `unreachable` verdict with no `--lever`. That
is deliberate: a verdict with no lever named is indistinguishable from "nobody looked",
and that ambiguity is how 112 bare-`curl` 403s became permanent skips.

A prior hit does NOT always mean "blocked" — some rows record a workaround, and a
verdict that changed over time is the most informative row in the store. `lookup`
prints the history and flags a flip. **Look the operator up as well as the host:**
blocking is per tenant, not per hostname.

---

## Phase 3 — Tier classification *(scaffolding = spider)*

**Don't write selectors before classifying.** Most "obvious" selectors are wrong on
SPA sites because the body has not hydrated.

**Fingerprint before you climb the ladder.** Check what the storefront runs
(`../platform_fingerprints.md`). Shopify, WooCommerce, Sapo, Magento, Vendure, Algolia
or Typesense means the catalog endpoint is already known and you land on Tier 1B
without probing anything.

```
Tier 1A — HTML/CSS, server-rendered          extraction_pattern: scrapy_html
  ↑ curl_cffi impersonate="chrome124" → h1 + og: meta + a price in raw HTML?
Tier 1B — JSON API, no auth                  extraction_pattern: scrapy_api
  ↑ Playwright network-capture → /api/, /v1/, /v2/, /graphql returning ≥5 KB JSON
    with product fields, and works with only Origin/Referer set?
Tier 2 — Playwright-rendered HTML            extraction_pattern: scrapy_playwright
  ↑ Playwright dump, 6–8 s wait + scroll → product cards with name + price?
SKIP — document the reason
  Cloudflare/Akamai/PerimeterX 403 · ERR_CONNECTION_RESET · empty PDP / login wall
  · app-only · aggregator with no per-product URLs · JS that doesn't hydrate at 8 s
```

Probe commands and scripts: `../probe_patterns.md`. Class doctrine — which CDN family
behaves how, which tell means what: `../blocker_classes.md`.

### Mandatory gate: never reach SKIP without a network trace

A 403 on the front page says nothing about the backend. Render the page once in
Playwright, read the network tab, look for the internal JSON endpoint. Many hardened
fronts have a completely open JSON API behind them — confirmed on chemist_warehouse,
makro_pro, mm_mega_market, sm_markets_savemore, lazada.ph, shoppy_mn, farro_fresh,
basic_homemart. The spider then hits it directly over plain HTTP and Playwright never
runs at collection time. **"Playwright to discover, plain HTTP to scrape"** is the
single highest-yield move in this phase.

This gate needs the Chromium binary, not merely the `playwright` package —
`poetry run playwright install chromium`; a8's `~/venv` already has it. When you
genuinely cannot render, the honest close is `verdict: blocked` with the `curl_cffi`
ladder you ran as the lever. Never promote an un-traced host to a clean SKIP, and never
write a trace you did not take: a fabricated trace is how a recoverable host becomes
permanent.

### Mandatory gate: a bare-`curl` 403 is NOT evidence of a WAF

Cloudflare, Akamai and DataDome overwhelmingly fingerprint the **TLS handshake (JA3)**,
not the User-Agent.

```bash
poetry run python -c "
from curl_cffi import requests as r
x = r.get('https://DOMAIN/', impersonate='chrome124', timeout=30)
print(x.status_code, len(x.text))"
```

Ladder: `chrome124` → `chrome120` → `safari17_0` → **`firefox133`**. They are **not**
interchangeable. `mall.cz`/`allegro.cz` 403 on both Chrome profiles and clear only on
`safari17_0`. Seven hosts across Syria, Botswana and Liberia hit an identical
6,192-byte Hostinger `hcdn` 403 that returns 200 only on `firefox133` — two of them
open WooCommerce Store APIs. 11 of 125 retried hosts cleared on `chrome150` or
`chrome131_android`; `rewe_de` needed `chrome133a` specifically.

Measured 2026-08-17: a 279-domain triage probed with bare `curl` + browser UA produced
112 `SKIP_WAF` verdicts. Re-probing with `curl_cffi` alone recovered a large share on
the first lever, including Cloudflare Turnstile *and* Akamai sites. Those verdicts were
mostly measuring curl's TLS handshake.

Measured 2026-09-17, on this repo's own migrated log: **45 of 50** hosts filed as
blocked returned clean 200s in 33 seconds on the `curl_cffi` ladder; 16 had an open
platform catalog endpoint.

**When `curl_cffi` AND Playwright both return 403, stop.** You are facing a real
challenge, and headless Chromium without a residential proxy and captcha solver will
not break Cloudflare/Akamai/Incapsula. Log the verdict naming the lever and the tell,
and move on. Note the ordering: bare curl failing is not the trigger — `curl_cffi`
failing is. Headless Playwright is not the general answer either: it cracked 3 of 100
curl-blocked hosts and scored *worse* than impersonated TLS against Akamai tenants.

Also rule out the cheap false positives: a *different TLD of the same platform* being
open, sitemaps served WAF-exempt while HTML pages 403 (argos.co.uk, leroymerlin.it —
good for a URL-seed list), and burst-throttling that clears at `concurrency=1`. And
watch your own request volume: `handla.ica.se` probed clean in isolation and then failed
three acceptance runs against a challenge its own campaign triggered from one IP.

### "WAF beaten" is not "catalog enumerable"

Two separate claims; a probe must prove both. Clearing the block gets you the homepage,
and a homepage carousel will happily yield 20–50 name/price pairs that look exactly like
a passing probe. Carousels are curated, unpaginated, and reshuffle per visit.

Record both verdicts, and only the second licenses scaffolding:

1. **Access** — a non-homepage URL returns 200 with real content.
2. **Enumerability** — a *category or listing* URL yields products, AND page 2 of that
   same listing yields a *different* set.

On the 2026-08-17 recovery pass, of four domains reported `RECOVERED`, three were
counted off homepage carousels. Re-probing real category paths confirmed tehnomax.me and
hepsiburada.com as genuinely enumerable while tehnomanija.rs was not — its Magento REST
returns 401 and its category paths 404. Same access verdict, opposite decision.

This is the probe-time twin of the Phase 6 ≥5-rows gate. Also test page 2 on **both**
the apex and `www.` — `beares.co.sz` and `hubbardshardware.gd` silently drop the
pagination parameter on the apex and re-serve page 1 forever.

### A live platform API is not a priced catalog

A 200 from `/wp-json/wc/store/v1/products` that paginates proves reachability and
nothing else. Six dead ends in one 2026-09-11 wave were exactly this: `cyberstore.co.bw`
(679 products, every one `price=0`), `abc-guinea.com` (208, all zero),
`globicare-pharma.com` (39), `mpharmaco.com` (63), `einkaufland.li` (gift vouchers,
`x-wp-total=1`), `shop.tgi.li` (26 SKUs, all DTM motorsport tickets). **Fetch an actual
product and look at its price** before ranking a candidate or handing it to an agent.

Check the response currency matches the country, too. `ctm.co.bw` silently resolves to
the CTM **Kenya** store view and returns KES without an explicit `Store: BW` header —
well-formed, healthy-looking, and nothing downstream would flag Kenyan prices filed
under Botswana.

For Tier 2 sites, dump the HTML to `/tmp/probe_<key>_listing.html` and
`/tmp/probe_<key>_pdp.html` so Phase 4 can grep files instead of re-fetching.

---

## Phase 3-fetcher — Feasibility probing *(scaffolding = fetcher)*

Tiers do not apply. Probe the **payload shape**:

- **`rest_api`** — hit it with `requests` + a real browser UA. Note date / region /
  commodity parameters, whether responses paginate, whether there is an `as_of` per row.
  Common failures: an undocumented required `Referer`; prices nested under
  `data.items[*].priceHistory[*]` needing flattening; a rolling window (last 12 months
  only — backfill via Wayback or a sister "yearly" endpoint).
- **`pdf`** — `curl` it, open with `pdfplumber`. Empty `extract_text()` means image-only;
  `pytesseract` OCR is acceptable at ~5–10× runtime. Regulator PDFs often carry a
  "Schedule 1 / Retail" section *and* a "Schedule 2 / Bulk" or "Drum Sale" section —
  anchor on the retail one only. **Always anchor on the LAST occurrence of
  "SCHEDULE 1"**: re-published orders with corrigenda leave the stale earlier table in place.
- **`tabular_download`** — download with `requests`, open with `pandas`. Identify sheet,
  header row, COICOP-division column. Stats offices love merged header cells — expect to
  skip rows or read with `header=[0,1]`.
- **`html_scrape`** — try `pandas.read_html` first; it is the lowest-effort extractor
  when it parses. Otherwise BeautifulSoup with explicit selectors.
- **Tariff schedules** — cadence is annual/irregular. Check whether an archive of prior
  tariffs exists or only the current one; if only current, snapshot with
  `period_kind: effective_from` and `effective_from` = release date.
- **`cpi_benchmark`** — pick the published machine-readable form (REST > CSV > XLS > PDF).
  Note whether the source publishes a single all-items index, a COICOP-1999 grouping, or
  the COICOP-2018 13-division grouping; `coicop_codes:` records what is available.

Save every raw payload to `/tmp/probe_<source_key>_sample.{json,csv,xlsx,pdf,html}` so
fetcher development does not re-fetch.

A fetcher endpoint needing a session cookie or returning Cloudflare-protected responses
may still work with `requests.Session` + browser-realistic headers — but **test from a
cold cache** before declaring success.

---

## Phase 4 — Extract real selectors *(scaffolding = spider)*

Open the dumped HTML (Tier 2) or the live page (Tier 1) and identify:

- **product_name** — prefer a stable attribute (`[data-test="product_name"]`, Long Chau)
  or `<img>` alt text on a product card (City Mall MM). Avoid `<a>::attr(title)` as a
  high-priority fallback: overlay badges ("sale") frequently steal it. Always try
  `meta[property='og:title']::attr(content)` as a PDP fallback.
- **price** — a specific class (`att-product-detail-latest-price`, Co.opmart) or a
  `data-price` attribute (Carrefour TW). On atomic-CSS sites (Sayurbox-style
  Twitter/RN-Web classes) there is no clean selector — extract via text regex
  (`Rp\s?[0-9.,]+`).
- **product_id** — SKU / barcode / canonical-URL-trailing id. Often
  `meta[property='product:retailer_item_id']`, an `<input name='id'>`, or parsable from
  the URL.
- **category** — breadcrumb. Many sites have none on PDP; leave it null rather than
  invent one. A reliable breadcrumb is high-value even when it costs extra work: it is
  what makes a product auditable and what a human labeller reads on a hard case.

**Verification rule: before scaffolding, every selector must have been observed matching
the right text in a real dumped HTML file.** This is the single biggest determinant of
whether the spider works on first run. Never invent selectors — if the probe HTML is
empty or hydration didn't complete, fix the probe or skip the site. And do not trust a
scout sub-agent reporting `selectors_unknown: true`: that is a signal to run a real
Playwright probe, not to guess anyway.

**Parser trap.** `bmsonline.co.bw` emits a second `<!DOCTYPE html><head>` inside its own
head; `lxml`/parsel sees 170 nodes of a 76 KB page and every selector returns zero, at
HTTP 200, with no error. BeautifulSoup `html.parser` returns all 20 cards. If a probe
looks clean and every selector returns nothing, compare two parsers before concluding
anything.

---

**STOP. Read `scaffold_spider.md` or `scaffold_fetcher.md` — whichever matches this
candidate's `scaffolding` — before continuing. Do not read both.**
