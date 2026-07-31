# 2026-07-30 — EAP retail source expansion (discovery + onboarding)

## Goal

Skyrocket the number of retail price sources across EAP (East Asia, Southeast
Asia, Pacific Islands). Two coupled asks in one day: (A) a leaf-gap-driven pass
to fill weak/zero-obs deep COICOP-01 leaves, and (B) a source-count-driven pass
to broaden the corpus generally. This log covers both, weighted to (B) — the
discovery-methodology research + the 24-source onboarding batch that followed it.

Downstream consumer is the cross-country PPP / Real-Exchange-Rate F&B basket, so
"more sources" means more independent local retail catalogs feeding the
enrich → classify → build pipeline, not just more SKUs from existing chains.

## Method

**Batch A (leaf-gap driven, 12 sources).** Computed div-01 leaf coverage from
`data/prices/build/eap_fnb_observations.parquet` vs the 269 COICOP-2018 leaves in
`data/prices/enrich/coicop_categories.xlsx`. Bottleneck was corpus/source
coverage, not gold labels. Dispatched 12 parallel onboarding agents at
under-sourced countries + specialty leaves. (Full detail: memory
`eap_fnb_weak_leaf_coverage_20260730`.)

**Batch B (source-count driven, 24 sources).** Dispatched one Sonnet research
agent to find a *scalable* discovery method rather than one-google-per-country.
Verdict memo (job-tmp `eap_source_discovery_methodology.md`, 102 candidates in
`eap_candidate_sources.csv`):

- Ranked discovery methods, best→worst: **(1) aggregator/marketplace enumeration**
  (one API = 5–20 retailers), (2) platform fingerprinting, (3) local-language
  search, (4) Wikipedia/listicle seeds, (5) app-store charts. Generic English
  "grocery in X" search is the **worst** method.
- **Inverse-correlation law:** in EAP, aggregator size and scrapeability are
  inversely correlated. Market leaders (Korea Naver/11st/Gmarket/Coupang, China
  JD/Tmall, HK HKTVmall) are WAF-hardened — every Korean marketplace probed
  403'd or returned a JS shell. Mid-tier/regional aggregators and small-market
  grocers on off-the-shelf platforms (Shopify/WooCommerce/Ecwid/Sapo/OpenCart)
  verify clean first try. Budget probe time toward the latter; treat market
  leaders as a separate anti-bot/Playwright project.

Then dispatched 13 parallel onboarding agents (one per country) on the 25
live-verified rank-4/5 candidates. Independence discipline (same as Batch A):
in-place, no git, no shared-file edits, inline selectors → orchestrator reviews
and commits each. 24 of 25 shipped.

## Sources added (Batch B — 24 new, 13 commits `4915ed17..49138500`)

Full-catalog scrape row counts verified post-commit (`prices collect --source X
--skip-fetchers`, no item cap).

| Country | Source | Platform / mechanism | channel | full rows |
|---|---|---|---|---|
| Malaysia | sunshine_online | OpenCart SSR listing | supermarket | 32,534 |
| Vietnam | emartmall | OpenCart SSR (`route=product/category`) | supermarket | 19,557 |
| Taiwan | costco_taiwan | SAP Commerce; sitemap → JSON-LD PDPs | supermarket | ~15k (full-crawl) |
| Taiwan | yahoo_shopping_tw | SSR Redux `isoredux-data`, F&B-kw seeded | aggregator | 7,978 |
| Malaysia | health_lane | OpenCart-derived O2O white-label | pharmacy | 5,291 |
| Australia | harris_farm_markets | Shopify `/products.json` | supermarket | 4,612 |
| Myanmar | goodzay | Shopify root `/products.json` (multi-vendor) | aggregator | 4,183 |
| Singapore | little_farms | Magento SSR listing | supermarket | 3,572 |
| Cambodia | niront | Shopify `/products.json` (USD) | aggregator | 3,240 |
| Japan | au_pay_market | `api.wowma.net` category-ranking JSON | aggregator | 2,000 |
| Thailand | lemon_farm | Shopify `/products.json` (organic) | supermarket | 1,756 |
| Indonesia | yogya_online_minimarket | Yogya-group SSR listing | supermarket | 1,537 |
| Indonesia | yogya_online_supermarket | Yogya-group SSR listing | supermarket | 1,358 |
| Japan | lohaco | ASKUL Nuxt SSR category pages | supermarket | 1,269 |
| Indonesia | paskomnas_trading | Laravel SSR `/product?page=N` (fresh) | supermarket | 466 |
| Tonga | tongamarket | WooCommerce Store API (`/wp-json/wc/store/v1`) | aggregator | 466 |
| Singapore | zairyo | Shopify `/products.json` (JP specialty) | supermarket | 422 |
| Vietnam | dichonhanh | Custom SSR (wet-market fresh) | supermarket | 307 |
| Trung… Vietnam | trungson_pharma | CS-Cart SSR (`?page=N`) | pharmacy | 278 |
| Nauru | eigigu_supermarket | Ecwid REST 403 → SSR-HTML card fallback | supermarket | 269 |
| Vietnam | vissan_mart | Magento SSR (`data-price-amount`) | supermarket | 274 |
| Tuvalu | jy_ocean_trading | Shopify `/products.json` (**first TV retail**) | supermarket | 186 |
| Vietnam | rautuoi247 | Sapo/Bizweb `/products.json` (fresh) | supermarket | 62 |
| Malaysia | apex_pharmacy | ASP.NET WebForms SSR | pharmacy | 89 |

Repo went **238 → 260** discoverable sources (`prices collect --list`).

### Platform-endpoint cheatsheet (reused across the batch, scaffold near-free)

- **Shopify:** `/products.json?limit=250&page=N` (root = full cross-vendor
  catalog for multi-vendor stores; paginate until empty `products`).
- **WooCommerce:** `/wp-json/wc/store/v1/products?per_page=100&page=N` — public,
  no auth; prices are in **minor units**, divide by `10^currency_minor_unit`.
- **Sapo/Bizweb** (VN Shopify-alike): also exposes `/products.json`.
- **OpenCart / Magento / CS-Cart:** listing cards carry name+price inline
  (`data-price-amount` on Magento) — no PDP visits needed.
- **Ecwid:** Storefront REST usually auth-gated (bare 403, token not in page JS);
  fall back to SSR `.grid-product__*` cards.
- **SAP Commerce (Spartacus):** OCC `/rest/v2/...` needs a session; use the
  product sitemap → per-PDP `schemaorg_product` JSON-LD instead.

## Dead-end (documented, not shipped)

- **Myanmar `bnf_mart`** — route-gated Laravel storefront. Every catalog route
  (`/shop`, `/category/*`, `/product-detail/*`, `/search`) 302-redirects to home
  regardless of cookies/session/JS, confirmed under headless Chromium; only an
  ~11-item homepage carousel is reachable. Belongs in `references/known_blockers.md`
  as "route-gated Laravel storefront" (deferred — that file had pre-existing
  uncommitted edits this session).

## Notes for downstream

- **Currency overrides:** niront prices in **USD** (not KHR — Cambodia dual-currency
  retail); tongamarket in **NZD** (not TOP). Both set from the site's actual
  returned currency, not the `countries.yaml` default — same pattern as hikiotonga.
  These need FX at build.
- **Partial-catalog sources:** `eigigu_supermarket` captures page-1-per-category
  only (client-side JS pagination); `au_pay_market` and `yahoo_shopping_tw` are
  top-N ranked/keyword slices, not exhaustive catalogs (same shape as the existing
  `rakuten` spider). `apex_pharmacy` dropped pagination (load-more AJAX returned
  empty). Not defects — flagged so coverage isn't over-read.
- All are `coicop_classification: deferred_gemini`, `coicop_codes` unset (wide
  retail), so rows classify post-collect via the embedding→head classifier.

## Backlog

- **Fetcher-pipeline wiring** (carried from Batch A): PNG FPDA (54k) + Lao WFP
  (22k) `official_avg` datasets are parked because the `prices fetch` CLI is
  unimplemented and fetcher YAMLs break `collect --list`. Biggest unrealized value.
- **WAF-hardened mega-aggregators** — GrabMart (3000+ retailers), foodpanda
  pandamart, LazMart, Makro PRO — highest paper-leverage, need a dedicated
  Playwright/stealth spike, not routine onboarding.
- **`known_blockers.md` consolidation** — bnf_mart + Korean-marketplace 403s +
  eigigu Ecwid-403; deferred (pre-existing uncommitted edits in that file).
- Indonesia fresh leaves via segari.id (signed-API reverse-engineering); Guam
  real Cost-U-Less (Freshop `cost_u_less` key serves Caribbean stores, not Guam);
  6 Pacific micro-states confirmed no viable retail e-commerce.

Related: [[eap_fnb_weak_leaf_coverage_20260730]], [[eap_retail_source_expansion_20260730]].
