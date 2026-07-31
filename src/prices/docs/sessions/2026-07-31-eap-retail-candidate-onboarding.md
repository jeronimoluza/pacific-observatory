# 2026-07-31 — EAP retail candidate fan-out (batch 3) + WAF/Playwright spike

## Goal

Convert the remaining un-onboarded candidates in the 2026-07-30 discovery CSV
(`eap_candidate_sources.csv`, 102 rows, 24 already shipped) into working sources.
Two coupled dispatches: (A) one onboarding agent per country over the tractable /
bounded-probe candidates, and (B) a two-agent WAF/Playwright spike at the
"blocked" bucket (403 / Akamai / SPA-only) that routine onboarding skips.

Downstream consumer unchanged: the cross-country PPP / Real-Exchange-Rate F&B
basket. More independent local retail catalogs feeding enrich → classify → build.

## Method

**Honest triage of the ~78 leftover candidates.** Not all rank-4/5 cheap wins —
~15 VERIFIED/known-platform, ~45 WAF-blocked/JS-shell, ~18 all-WAF single-candidate
microstates. Dispatched **13 country agents** (one per country with real yield:
MY, MM, TL, SG, CN, WS+FJ, ID, VN, TH, PH, KH, AU) each told to ship the
VERIFIED/known-platform sources and take a **bounded ≤2-attempt probe** at that
country's WAF candidates (report-not-force). Then **2 spike agents**: (A) a
Playwright/internal-API spike at client-rendered SPAs, (B) a hard-WAF
characterization spike at Akamai/Incapsula/Lazada/Cloudflare tenants. Same
independence discipline as prior batches: in-place, no git, no shared-file edits,
inline selectors → orchestrator reviews + commits each.

The winning move across the batch was **"Playwright to discover, plain HTTP to
scrape"**: render the SPA once to find the internal JSON API in the network trace,
then write a fast `scrapy_api` spider hitting that endpoint directly. Most sources
below never need Playwright at runtime.

## Sources added (25 new, 9 commits `a66becfd..80ae1bec`)

Row counts are from the `--max-items 60` E2E test (capped), not full-catalog.

| Country | Source | Platform / mechanism | channel | test rows |
|---|---|---|---|---|
| Philippines | sm_markets_savemore | Magento GraphQL (open, WAF-throttles bursts) | supermarket | 491 |
| South Korea | gmarket | Next.js `__NEXT_DATA__` (Cloudflare, UA↔TLS match) | aggregator | 600 |
| Malaysia | alpro_pharmacy | Shopify `/products.json` | pharmacy | 250 |
| Singapore | mustafa_online | Shopify `/products.json` (7.5k+ catalog) | hypermarket | 250 |
| Myanmar | common_health | Shopify `/products.json` | pharmacy | 250 |
| Philippines | lazada_ph_lazmart | Lazada catalog AJAX `/catalog/?ajax=true` (unauth on .ph) | aggregator | 229 |
| Vietnam | kingfoodmart | Next.js `/_next/data/<buildId>/<slug>.json` | supermarket | 224 |
| China | alibaba_health_pharmacy | Tmall async module `asynSearch.htm` (GBK) | pharmacy | 209 |
| Mongolia | shoppy_mn | Cody.mn Elasticsearch `_search` (guest basic-auth); ~59k SKUs | aggregator | 200 |
| Taiwan | friday_shopping | aisearch + frontend-gateway productinfo (food-kw seeded) | aggregator | 200 |
| Vietnam | mm_mega_market | Magento 2 GraphQL `/graphql` (open); 613 leaf cats | hypermarket | 123 |
| Australia | chemist_warehouse | open Algolia index (no WAF); price-band bisection | pharmacy | 123 |
| Malaysia | ampm_pharmacy | WooCommerce Store API `/wp-json/wc/store/v1` | pharmacy | 100 |
| Fiji | new_world_fiji | Vendure `shop-api` GraphQL (per-store token; ÷1000) | supermarket | 100 |
| New Zealand | farro_fresh | Blazor WASM REST `/api/ViewModel/Search/Search` | supermarket | 100 |
| Philippines | rose_pharmacy | WooCommerce Porto SSR (`/product-category/`) | pharmacy | 102 |
| Saymyanmar | saymyanmar | Laravel/Mongo OpenCart-style SSR | pharmacy | 89 |
| Indonesia | pasar_segar | WooCommerce/Martfury multi-vendor SSR listing | supermarket | 86 |
| Thailand | makro_pro | Typesense catalog proxy (open, no auth) | supermarket | 80 |
| Australia | drakes_supermarkets | schema.org Product JSON-LD on PDPs (sitemap-seeded) | supermarket | 64 |
| Myanmar | pacific_aa_online | Laravel Vue `<product :product='{JSON}'>` cards | pharmacy | 60 |
| Samoa | gounders_samoa | Shopify `.myshopify.com/products.json` (bypasses WAF'd apex) | supermarket | 34 |
| Malaysia | pasar_tani | DJ-Classifieds (Joomla) SSR listing | aggregator | 10 |
| Timor-Leste | basic_homemart | Vue3/Cloudflare SPA → open `/dev-api/api/products/list` | supermarket | 50 |
| Timor-Leste | cafe_letefoho | WooCommerce Store API; narrow → `coicop_codes: ["01.2.1"]` | supermarket | 9 |

Repo **~275 → 299** discoverable sources (`prices collect --list`). Also confirmed
**11st is already covered** by the existing `street11_kr` spider (604 rows) — no dup added.

### Reusable platform findings (bank these)

- **Open API behind a "blocked" front is common.** chemist_warehouse (Algolia),
  makro_pro (Typesense), mm_mega_market + sm_markets_savemore (Magento GraphQL),
  lazada.ph (catalog AJAX), shoppy_mn (Elasticsearch), farro_fresh (Blazor REST),
  basic_homemart (`/dev-api/api`) all looked WAF-blocked but had an unauthenticated
  JSON backend the SPA calls. Always Playwright-trace the network before giving up.
- **gmarket / Cloudflare bot-mgmt cross-checks UA↔TLS:** chrome-TLS + Scrapy-default
  UA → 403; chrome-TLS + pinned-Chrome UA → 200.
- **lazada.ph is un-WAF'd; lazada.vn is blocked** — same platform, different TLD posture.
- **smmarkets.ph GraphQL is open but IP-throttles bursts** (curl 28 blackhole ~45s) —
  scrape with browser UA, concurrency=1, autothrottle.
- **New World Fiji (Vendure):** needs per-store `vendure-token` header; `priceWithTax`
  is in **thousandths** (÷1000), not cents.
- **gounders_samoa:** custom domain is WAF-blocked; the backing `*.myshopify.com`
  origin serves the full feed unprotected.
- **Config `channel` enum has no `fresh_market`/`specialty`** — use `supermarket`
  (a `fresh_market` value in one YAML crashed the global `collect --list` loader
  mid-batch; caught and corrected).

## Blocked / dead-end (documented for references/known_blockers.md)

known_blockers.md still has pre-existing uncommitted edits, so signatures are
parked here for a later consolidation pass.

**Hard-WAF / needs-infra (BLOCKED):**
- KR naver_shopping — search API HTTP **418** (datacenter-IP block) + NAVER sign-in gate; needs residential-KR IP + logged-in session.
- HK parknshop (pns.hk) — **Akamai** (`_abck`/`bm_sz`); OCC API `api.pns.hk/occ/v2/` edge-denies datacenter IP. Same family as watsons.com.hk — stop re-probing.
- SG sheng_siong — **Imperva/Incapsula** + Meteor app (data over DDP/SockJS websocket, no REST product API).
- SG redmart — **Lazada slider-captcha** + signed `x-mtop` token; needs captcha infra.
- ID segari — **Cloudflare Turnstile** + price endpoint gated by client **HMAC `x-segari-signature`** (taxonomy open). Signature-forging was safety-gated; not attempted.
- VN aeon_eshop (DataDome), lottemart (Incapsula), pharmacity/guardian/khaisanfood/annam_gourmet (Cloudflare).
- TH villamarket (AWS CloudFront WAF), foodpanda_th (WAF), grabmart_th (app-first, merchant-ID enum).
- PH landers (Cloudflare), foodpanda_ph (Cloudflare+PerimeterX), shopee_ph (captcha SPA), grabmart_ph (captcha), snr (login-gated pricing).
- MY pasaraya_cs (Cloudflare captcha); mydin (host unreachable, TCP timeout on all schemes).
- MM ocean_supercenter, makro_pro_mm (client-rendered SPA, no server-side catalog).
- KH bloc (geo-session-gated; **open `api.php` backend + USD prices confirmed** — best future revisit with Playwright+geo-cookie), l192 (Cloudflare), wownow (bare Nuxt shell).
- AU iga_shop_online (store-select-gated Next.js SPA; API base runtime-injected).
- PNG rh_hypermarket (Cloudflare managed challenge, no auto-clear in headless).

**Dead-end (no scrapeable e-commerce / wrong catalog):**
- TL gybsee (food collections unstocked; catalog is non-food electronics/furniture).
- FJ cost_u_less (Freshop catalog serves Caribbean/USVI stores, no Fiji/FJD — would be price pollution).
- SG prime_supermarket (WooCommerce with only 4 placeholder products; real catalog is a printed brochure).
- TH cp_freshmart (NXDOMAIN — domain gone); foodland shop (Cloudflare but curl_cffi-passable; currently in a maintenance window — **revisit when live**).
- Guam payless_markets (brochureware; "online shopping" link has no transactional catalog).
- Fr. Polynesia carrefour_polynesie (live store IP geo-fenced to FP; main domain is a Calameo flyer).

## Backlog

- **known_blockers.md consolidation** — fold in all signatures above (still deferred; that file has uncommitted edits).
- **Playwright+geo-session revisit for KH bloc** — open `api.php` + confirmed USD prices; only needs a forgeable delivery-location cookie.
- **Full-scrape verification** of the 25 new sources (this session tested at `--max-items 60` only) — mirror the batch-1/2 uncapped-crawl pass.
- Carried from prior: PNG FPDA (54k) + Lao WFP (22k) `official_avg` fetcher wiring (biggest unrealized value; `prices fetch` CLI still unimplemented).

Related: [[eap_retail_source_expansion_20260730]], [[eap_fnb_weak_leaf_coverage_20260730]],
prior session `2026-07-30-eap-retail-source-expansion.md`.
