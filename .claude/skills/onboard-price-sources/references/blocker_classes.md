# Blocker classes — what each wall means and what beats it

Per-host verdicts live in `probe_log/` (query with `scripts/probe_log.py lookup <host>`).
This file is the part no per-host record captures: which families behave how, which
tell means what, and which apparent blocks are not blocks at all.

Extracted from `known_blockers.md` (947 KB of prose, deleted 2026-09-17 — recoverable
from git history). That file's own header recorded that a 2026-08-17 re-probe recovered
a large share of 112 `SKIP_WAF` verdicts on one lever, and that on 2026-09-06, 16 of 26
hosts in one shard returned clean 200s while filed as blocked. Treat every inherited
verdict as a hypothesis with a decay rate, which is what `recheck_after` encodes.

## The rule that governs all of the below

**Blocking is applied per tenant, not per hostname.** One AS-Watson, Foodstuffs, MWG,
Lazada or Delivery Hero property being walled means its siblings in other countries
almost certainly are too, even when the exact domain you hold has never been probed.
So look up the operator, not just the domain — a domain-only lookup sends you off to
re-lose the same fight under a different TLD.

## Classes that fall to a TLS fingerprint (re-probe before believing)

Cloudflare, Akamai and DataDome overwhelmingly fingerprint the **TLS handshake (JA3)**,
not the User-Agent. Plain `curl` with a spoofed browser UA gets a 403 from sites a stock
`chrome124` fingerprint walks straight into — no headers, cookies, proxy or captcha.

| Tell | Family | Beaten by |
|---|---|---|
| `cf-mitigated: challenge`, 403 + Cloudflare headers | Cloudflare | `curl_cffi` ladder |
| `server: AkamaiGHost`, 403 | Akamai tenant | `curl_cffi` ladder (better than Playwright — see below) |
| `x-datadome: protected`, 403 | DataDome | `curl_cffi`, often profile-specific |
| `x-amzn-waf-action: challenge`, 405 | AWS WAF | sometimes; content-level PoW does not fall |
| ~212-byte or ~6 KB JS stub at HTTP 200 | Imperva Incapsula | **`firefox133`** specifically |
| 6,192-byte 403 stub, `server: hcdn` | Huawei Cloud CDN | **`firefox133`** only |

**The ladder, in order: `chrome124` → `chrome120` → `safari17_0` → `firefox133`.**
They are not interchangeable. `mall.cz` and `allegro.cz` 403 on both Chrome profiles and
clear only on `safari17_0`. Seven hosts across Syria, Botswana and Liberia hit an identical
`hcdn` 403 that clears only on `firefox133`, two of them open WooCommerce Store APIs.
`comfy.ua` returns the Incapsula stub on all four Chrome/Safari profiles and an 888,601-byte
real page on `firefox133`. 11 of 125 retried hosts returned 200 on `chrome150` or
`chrome131_android` after 403-ing on `chrome120`/`chrome124`; `rewe_de` shipped only because
of that retry and needed `chrome133a`.

A Chrome-and-Safari-only ladder writes every one of those off as a hard block.

## Classes that survive impersonation — genuinely different, record which

- **Content-level proof-of-work** — Amazon's `x-amzn-waf-action: challenge`, JS-execution
  stubs. TLS will not touch it.
- **IP / geo blocks** — Fastly error codes, `cf-ray` resolving to the wrong continent,
  origin-level refusals. Needs an exit node in-country, not a fingerprint. `canalplus` (GW)
  is geo-gated rather than WAF'd: Playwright never clears "Continuer" from a European IP.
- **Genuine SPA shells** that clear the WAF at 200 but ship no embedded product JSON. That
  is a Tier 2 problem, not a block — `elcorteingles.es` is exactly this.
- **Dynamic-auth APIs** — a client-side-generated security header (e.g. `x-security-key`),
  HTTP 429 even with cookie warmup. Skip the API; the HTML front-end is rarely Tier 2,
  because if the HTML were scrapeable the API would not be the path of least resistance.

## Walls that are not walls

- **Queue-it / virtual waiting room** is a warm-up problem, one cookie deep. A cold PDP 302s
  to `<tenant>.queue-it.net`; fetching `/` once sets the acceptance cookie and every
  subsequent PDP returns 200. `nemlig.com` scraped 0 rows through 219 such redirects, then
  shipped 54 rows once the spider fetched the home page first and kept cookies.
- **Your own request volume.** `handla.ica.se` probed clean in isolation and then failed
  three acceptance runs against a challenge triggered by the campaign's own traffic from one
  IP. In a multi-host campaign, late failures are not independent of early success. Pace the
  waves; do not record a blocker your own throughput caused.
- **An expired SSL cert.** `ukrstat.gov.ua` was filed as a TCP-level connection drop and is
  simply an expired cert — `verify=False` gets a real 200.
- **A stale sitemap or a token-walled API, when the HTML is server-rendered.** `heimkaup.is`
  was written off twice (stale sitemap, Jiffy API needs a bearer token); both were true and
  both were irrelevant, because every page carries a complete `window.__INITIAL_STATE__`.
  676 priced products, plain HTTP, no token. **Read the HTML before deriving a verdict from
  a sitemap or an API.**
- **Headless Playwright is not the general answer.** It cracked 3 of 100 curl-blocked hosts,
  and against Akamai tenants scored *worse* than impersonated TLS — drawing hard edge denials
  where `curl_cffi` got an interstitial. Unpatched headless Chromium is itself a fingerprint.

## Structural classes — skip permanently, cheap to confirm

| Class | Signature |
|---|---|
| App-only | No web catalogue; App Store listing is the only storefront |
| Brochure-only WordPress | Real site, no shop, no prices |
| No products (corporate portal) | Marketing site at 200 |
| Aggregator, no per-product URL | Cannot build a stable item key |
| Placeholder / seed demo catalog | Real platform API, demo data. The 6amMart/Sixam Laravel family is the recurring one |
| Shopify store suspended | HTTP 402 |
| Azure Web App stopped | `Error 403 - This web app is stopped` |
| NXDOMAIN / dead origin | Cheapest class to re-check, and pure profit when one comes back |

**A live platform API is not a priced catalog.** A 200 from `/wp-json/wc/store/v1/products`
that paginates cleanly proves reachability and nothing else. On the 2026-09-11 sweep this was
the single most common dead end, six times in one wave: `cyberstore.co.bw` (679 products,
every one `price=0`, PDP reads "Contact Us"), `abc-guinea.com` (208, all zero),
`globicare-pharma.com` (39), `mpharmaco.com` (63), `einkaufland.li` (a gift-voucher platform,
`x-wp-total=1`), and `shop.tgi.li` (26 SKUs, all DTM motorsport tickets). Fetch an actual
product and look at its price.

## Traps that produce a false catalog

- **Multi-tenant Magento serving the wrong country.** `ctm.co.bw` silently resolves to the CTM
  **Kenya** store view and returns KES unless the request carries `Store: BW`. The response is
  well-formed and looks healthy, which makes it worse than an error. `hubbardshardware.gd`
  shares Magento infrastructure with `foodfair.gd` and its GraphQL and REST endpoints return
  *foodfair's* data — its SSR HTML was the only trustworthy path. Check the response currency
  against the country before scaffolding.
- **The apex that does not paginate.** `beares.co.sz` and `hubbardshardware.gd` drop the
  pagination parameter on the apex and honour it only on `www.`, so an apex crawl re-serves
  page 1 forever. Same signature as a truncating paginator, one-word fix. Test page 2 on both.
- **Platform-level truncation.** All 8 Lezzoo (IQ) venue storefronts return **exactly 60** menu
  items in JSON-LD regardless of venue size — confirmed against the full RSC payload, not just
  the `<script>` block. A flat cap across structurally different venues is the tell. A Magento
  row count is never a catalog size.
- **Parser-level silent truncation.** `bmsonline.co.bw` emits a second `<!DOCTYPE html><head>`
  inside its own head; `lxml`/parsel sees 170 nodes of a 76 KB page and every selector returns
  zero, at HTTP 200, with no error. BeautifulSoup `html.parser` returns all 20 cards. Invisible
  without comparing two parsers.
- **A clean sitemap does not imply a scrapable catalog.** The sitemap layer and the product
  layer are protected separately: `nakup.itesco.cz`, `tesco.ie`, `tesco.com` and `koctas.com.tr`
  all serve `robots.txt`, a sitemap index and every product shard openly — thousands of
  genuinely disjoint URLs — while denying every product-detail request on every TLS profile
  *and* on headless Playwright. Fetch a product page before believing a sitemap. (Sitemaps
  served WAF-exempt are still worth having as a URL-seed list — `argos.co.uk`, `leroymerlin.it`.)

## The spider-side gotcha that undoes a correct profile

`RandomBrowserMiddleware` overwrites `request.meta["impersonate"]` unconditionally from
`IMPERSONATE_BROWSERS`, pinned repo-wide to `chrome120`. That makes
`WooBaseSpider.IMPERSONATE_PROFILE` a silent no-op — the spider 403s on every request despite
declaring the profile. Narrow `IMPERSONATE_BROWSERS` in that spider's own `custom_settings`,
or disable the middleware per-spider. `kalico_gd` needed both halves;
`cassandraonlinemarket_ht` established the pattern; `zimolange_na` 403s on the repo default and
opens on `chrome124`.

There is a matching client-path mismatch class: a JS proof-of-work stub that `curl_cffi` clears
but Scrapy does not. If the probe passed and the spider 403s, suspect the middleware before the
site.
