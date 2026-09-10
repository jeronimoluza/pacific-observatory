# Botswana — price source inventory

_Inventory written: 2026-09-10_

Cold start (no prior inventory file). Discovery run used the **`ddgs` Python library**
as the search backend instead of WebSearch — 62 queries in English, Setswana and
Afrikaans, 633 result rows, 222 distinct non-noise domains, 37 probed with
`curl_cffi impersonate=chrome124`.

Country: `ssa/southern_africa/botswana` — currency BWP, languages `[en]`.
Already onboarded before this run: `notwanepharmacy_bw` (spider, pharmacy),
`fews_net` (fetcher, official_avg).

## Verified enumerable — ready to scaffold

| Source | URL | Platform / endpoint | Verdict | Notes |
|---|---|---|---|---|
| Sefalana Online Store | shopsefalana.com | nopCommerce, `GET /api/products?limit=100&page=N`, no auth | **ACCESS + ENUMERABLE** | ~316,600 products (last non-empty page 3166). page1∩page2 = ∅. `price` is a plain BWP decimal (NOT minor units), `sku`, `se_name`, `full_description` present. ~21% of rows carry `price: 0.0` — filter them. Top Botswana grocery/wholesale chain; catalog is packaged-grocery shaped ("KELLOGGS All Bran Flakes 500G", "KOO Fruit Peach Halves 3.06Kg"). **Highest-value F&B source found for this country.** |
| Luna Rosa | lunarosa.co.bw | WooCommerce Store API `/wp-json/wc/store/v1/products?per_page=100` | ACCESS + single-page catalog | 83 products, `currency_code=BWP`, `currency_minor_unit=2` (divide by 100). Meat/fish/deli/prepared ("Lekgotla Rump/T-Bone", "Salmon", "King-clip", "Cheese"). Small but clean, division 01 + some 11.1. |
| Letsema Horticulture Market | letsemahm.co.bw/weekly-prices/ | HTML table, 1 `<table>` on the weekly-prices page | ACCESS, fetcher-shaped | Woo Store API carries only 4 products (Apples, Green/Red Peppers, Onions, Mangoes) — the real value is the **weekly-prices HTML table**. Build as `fetcher` / `html_scrape` / `official_avg`, not a spider. Fresh produce = the structural gap supermarkets do not fill. |

## Reachable, catalog endpoint not yet found — need a Playwright network trace

Per the skill's mandatory gate, none of these are a SKIP verdict; they are unfinished probes.

| Source | URL | Status | Note |
|---|---|---|---|
| Choppies (online store) | echoppies.com | 200, Next.js SPA | Real Choppies e-commerce storefront. `/api/products`, `/api/catalog/products`, `/api/v1/products`, `/sitemap.xml` all 404. Needs a network trace. **The prior run recorded Choppies as a dead end after probing `choppies.co.bw` — the corporate site, not the store.** |
| SPAR2U | spar2u.co.bw | 200, 2.5 MB | SPAR Botswana online. Large hydrated page, endpoint not guessed. |
| Mmaraka | mmaraka.app | 200, prices in HTML | Botswana marketplace. Found **only** by the Setswana query `mmaraka wa dijo Botswana`. |
| Dijo | dijo.app | 200 | Food & grocery delivery, Gaborone. |
| Zebras Delivery | zebras.co.bw | 200 | Groceries + food delivery. |
| Gabs Eats | gabseats.com | 200 | Gaborone delivery platform. |
| Wanzy | order.wanzyapp.com | 200 | Food/grocery/essentials delivery, Gaborone. |
| TRANS Cash & Carry | trans.co.bw / tradeworldbw.com | 200 | Wholesale — worth chasing for `official_avg`-adjacent wholesale prices. |
| Pula Market | pulamarket.co.bw | 200 | Marketplace — probe the **seller directory**, not the catalog. |
| Meeticks | meeticks.co.bw | 200 | "Shop Local Botswana Businesses" marketplace/directory. |
| Beef Boys / Food Mart | beefboys.co.bw | 200, WordPress | Meat. No Store API on tested paths. |
| Senn Foods | sennfoods.com | 200, WordPress | Botswana food manufacturer. |
| Cakeman | cakeman.co.bw | 200, prices in HTML | Bakery, Gaborone. |
| Crown Bakery | crownbakery.co.bw | 200 | Bakery. |
| Sanctified Delights | sanctifieddelights.co.bw | 200, WooCommerce | Store API returned nothing on tested paths. |
| Game Botswana | game.co.bw | 200 | Specials page only. |
| Yourmart | yourmart.co.bw | 200, CS-Cart | Storefront appears to be a CS-Cart demo shell — verify it is a real Botswana catalog before spending more. |

## Official / statistical candidates (`official_avg`, `cpi_benchmark`)

| Source | URL | Note |
|---|---|---|
| Statistics Botswana — Prices | statsbots.org.bw/prices | Live prices landing page, 7 PDFs incl. "Botswana Food & Beverage Imports". CPI publications live here. `cpi_benchmark` + `official_avg` — split into two manifests if both shapes exist. |
| Bank of Botswana — CPI | bankofbotswana.bw | Consumer Price Index page, price strings present in HTML. |
| BAMB (Botswana Agricultural Marketing Board) | bamb.co.bw | Producer prices for scheduled crops, published as PDF ("2021/2022 marketing season — producer prices"). `/prices/` 404s — find the real path. `pdf` / `official_avg`. |
| Botswana Meat Commission | bmc.bw | `regional-cattle-prices` page. Narrow `official_avg`. |

## Dead ends — confirmed this run, do not re-search

| Source | Reason |
|---|---|
| hoodmarket.com | HTTP 402 |
| myfoodness.co.bw | DNS does not resolve |
| bescohyper.co.bw | TLS certificate verify failure |
| kgalagadibreweries.co.bw | 403 on `chrome124`/`chrome120`/`safari17_0` — corporate site, no catalog anyway |
| emliquor.com | False positive — a New Jersey liquor store, not Botswana |
| pnpbotswana.co.bw | Pick n Pay Botswana: WordPress but no Store API route; WhatsApp-order only, not a catalog (confirmed by the earlier run and unchanged) |
| bmart.co.bw, shopbw.co.bw, goodsy.co.bw, solleluna.co.bw, tiketi.com | Open catalog APIs verified (Woo Store API / Shopify `products.json` / Woo) but **not food & beverage** — books, appliances, electronics, homeware, bus tickets. Onboard them for other divisions, not this ask. |

## Method note — local-language search

Setswana and Afrikaans queries produced 46 domains no English query returned, but
almost all were academic or linguistic noise (`academia.edu`, `files.eric.ed.gov`,
`researchspace.ukzn.ac.za`, Setswana exam papers, Bible/JW pages). Botswana retail
is conducted in English and `countries.yaml` correctly lists `languages: [en]`.
**Net real yield from local-language search: `mmaraka.app` plus weak leads
(`sennfoods.com`, `agric.app`, `rekaafrika.com`).** Worth one cheap pass, not a
large query budget, for this country.

## `ddgs` backend gotcha

`ddgs` rotates across 8 text backends including `wikipedia` and `grokipedia`. With
`region="wt-wt"` the wikipedia backend builds `https://wt.wikipedia.org/...` and
DNS-fails, so **9 of 23 queries silently returned 0 results** — indistinguishable
from "no such source exists". Pin the backends:

```python
d.text(q, backend="duckduckgo, google, brave, mojeek, startpage, yahoo", max_results=20)
```

All 14 re-run queries then returned 14–18 results each. Never read a 0-result ddgs
query as a dead end without checking the backend.
