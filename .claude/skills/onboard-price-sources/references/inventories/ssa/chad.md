# Chad

_Inventory written: 2026-09-12_ (Phase-3 entry from a supplied 41-candidate
PENDING list; no discovery run. Supersedes the 2026-09-02 pass below, which
is kept for its dead ends.)

Chad had **2 filled COICOP leaves** going in. Coverage-density rule applied:
take whatever verifies, cheapest first, no gap-ranking. **Result: 5 shipped**
(4 spiders + 1 fetcher) out of 41 candidates.

## Shipped

| Source name | URL | Role / channel | Verification rows | Notes |
|---|---|---|---|---|
| `nibiya_td` | https://nibiya.com/ | `retailer_sku` / marketplace | **207** (max-items fence, not the catalog) | General Chad classifieds. Laravel+Livewire, but the listing component answers a plain GET at `/filter-resultats?categorieId=<Cat>&page=N`, fully server-rendered. 21 categories crawled (`Emplois` excluded — salaries are not prices). Widest COICOP breadth of anything Chad has. Food category is spelled **`Nouriture`**; `?categorieId=Alimentation` is silently empty. |
| `moov_africa_td` | https://moov-africa.td/ | `tariff` / null | **68** | Mobile operator prepaid bundles, COICOP 08.3.2.0 — **Chad's first source in division 08**. Homepage has zero prices (which is why triage called it NEEDS-CUSTOM-CRAWLER); tariffs live on `/espace-particulier/<offer>/` as Elementor `div.forfait` cards. 7 offer pages, 222 raw cards deduped to 68 distinct tariffs (a shared upsell block repeats across pages). |
| `saweek_td` | https://saweek.com/ | `retailer_sku` / marketplace | **20** (whole storefront) | 6valley multi-vendor marketplace. API 401s without a key; `/sitemap.xml` is misgenerated to `http://localhost/6Valley/...` with the platform's demo catalog and is **not** a URL seed. Server-rendered `/products` is the only surface. |
| `zelvendo_nadjos_td` | https://www.zelvendo.com/boutique/nadjos-shopping-service | `retailer_sku` / fashion | **18** (whole boutique) | One boutique on a small Chadian multi-vendor platform. Name and price come off `button.btn-cart[data-nom][data-prix]` — machine-readable, no display parsing. `?page=N` is a no-op (pages 3-5 byte-identical); the site's own counter says 20 products, so it is a tiny catalog, not a broken paginator. |
| `tchadimmobilier` | https://tchadimmobilier.com/ | `retailer_sku` / real-estate, **narrow 04.1.1** | **5** | WooCommerce Store API open, XAF minor_unit 0. Scoped to rental categories 100+107 only: unfiltered, 79 of 84 listings are property/land **sales** at 5-50M XAF, which are capital transactions with no COICOP leaf. Dedicated spider (not `generic_woo_configured`) because the scoped payload also needs 3 nameless drafts dropped — one priced 240,000,000 XAF, a sale mis-filed as a rental — plus the WooCommerce demo product id 159. |

## Rejected this pass (measured, do not re-probe without new evidence)

| Candidate | URL | Measured reason |
|---|---|---|
| `mssk_app` | https://www.mssk.app/ | **DUPLICATE of `mossosouk_td`.** Has a working `/api/product` (216 products, 9 pages) but 97 of its 196 product names slug-match `mossosouk.com`'s sitemap product slugs — and slug-matching is lossy, so real overlap is higher. It is the Mossosouk app mirror, as the triage note suspected. |
| `daarishop_fr` | https://daarishop.fr/ | **Verified but rejected.** WooCommerce Store API is open and healthy. It is a France-based diaspora send-to-family shop priced in **EUR** (rice 50 kg at 85 EUR, pharmacy voucher). Those are remittance-service prices, not Chadian retail price levels; onboarding them would inject non-Chad price levels into a PPP corpus. |
| `aboufarissolar_td` | https://aboufarissolar.com/ | **Product pages are gone.** Homepage links 41 `product.php?id=N` and 32 `category.php?id=N`, but every one returns the app's own `File not found.` (HTTP 404, 16 bytes — distinct from the host's 1525-byte 404). Only the homepage carousel's marketing copy carries FCFA strings. Not enumerable. |
| `banabaana_td` | https://www.banabaana.com/pays-224-Tchad | **Cannot be scoped to Chad.** The category listings reachable from the Chad page return ads from Abidjan, Dakar and Atlantique (Benin). Pan-African classifieds with a country landing page, not a Chad catalog. |
| `soukdarna_td` | https://www.soukdarna.com/ | **Catalog now near-empty.** SPA; found the backend at `/api/public/products` (`/api/products` 401s). It returns ~1.4 KB — a handful of products across 3 categories, nothing like the ThinkPad/solar-panel catalog the triage note described. Below the 5-row bar. Worth one re-probe if the site refills. |
| `sultana_market_td`, `ampktechnology_td`, `magazana_td` | — | **Mock/demo SPA shells.** 2-3 KB HTML, catch-all router returns the same shell for every path including `/robots.txt` and `/sitemap.xml`; the only API string in their JS bundles is `/api/broadcast`. The "products" in the triage notes ("Smartphone Galaxy Ultra", "Laptop Gaming Elite", "Manteau Long Camel") are generated placeholder catalogs. `magazana` says so itself: `Aucun produit disponible`. |
| `afribaba_td`, `dukafrica_td`, `perle_tchadienne_social` | — | **403 on every path including `/robots.txt`**, under `curl_cffi impersonate=chrome124` *and* `safari17_0`. Not a curl-TLS false positive. |
| `arsat_gaz_domestique_td` | afrique-info.com/article/949 | HTTP **530** (origin down). |
| `airtel_td_internet` | https://www.airtel.td/network/internet-package | **SPA, zero prices server-side.** 6.7 KB shell, 12 JS bundles, only `maps.googleapis.com` in them. Would need Playwright. Real pity — this is Chad's other mobile operator and would pair with `moov_africa_td`. Flagged as the best remaining division-08 target. |
| `ilnet_telecoms_td` | https://ilnet-telecoms.td/offers | 472-byte shell, one JS bundle, no API strings. |
| `shamsconnect_menu_td` | https://shamsconnect.com/menu | **SPA, zero prices server-side** (4.4 KB shell). The bilingual FCFA menu the triage note describes is real but client-rendered; needs Playwright. Best remaining COICOP 11.1.1 target. |
| `jam_pharma_td` | https://www.jam-pharma.com/tarifs | **No medicine prices.** Sitemap is 55 URLs, 44 of them `/pharmacie/*` directory pages. The only prices on the site are its own B2B SaaS subscription tariffs (15,000 FCFA/month to pharmacies) — a software licence, not a consumer price. |
| `konoom_td` | https://konoom.td/ | Corporate media/textile site (`services-fr`, `media-center-fr`, `about-us-fr`). No catalog, no tariff table. |
| `restaurant_bebo_td` | https://mon-site-web-five.vercel.app/ | Generic Vercel default subdomain; the FCFA strings sit in a "Top Restaurants à N'Djamena" review-directory block, not a structured menu. No stable identity, no enumerable menu. |
| `omega_impact_td`, `monrespro_business_td`, `hubformationtchad`, `satech_schooly_td`, `learncafe_td`, `rpm412_kalcal_td`, `sahelpackage_td` | — | **Service/SaaS tariffs, and several are price *ranges*** (Omega Impact quotes "150,000-400,000 FCFA" per engagement). B2B consulting fees, software subscriptions and logistics quotes are not household consumption prices. |
| `belivay_cemac_td` | https://belivay.com/ | Regional CEMAC marketplace, **Cameroon-first**; the candidate URL itself carries `?mock=1`. Django REST backend visible in the JS bundle (`/api/catalog/...`) but no Chad-scoped product locality. |
| `librairie_numerique_africaine_chad` | — | Pan-African digital publisher with Chad-*topic* books, not a Chad retailer. |
| `carros_td` | https://carros.com/ | **NOT PROBED TO A VERDICT.** Global vehicle-listings site with a real 10-shard `sitemap-cars.xml` index and a `sitemap-car_states.xml`. Chad PDPs exist (the triage note cites a Chari-Baguirmi Hilux), but scoping the crawl to Chad was not attempted. Left as the best remaining COICOP 07.1 lead. |
| `abdramani_solutions_td`, `vepaar_lossirimou_td`, `arcep_observatoire_telecom_2020`, `club_mcm_td`, `iambeezy_chad_price_blog`, `petitfute_ndjamena_restaurants`, `starlink_td_tariffs`, `nibiya`-adjacent social pages | — | Social-page mirrors, third-party directory listings, a Scribd PDF, and one price-comparison blog post. None is a first-party catalog with an enumerable surface. `iambeezy` is a **secondary** price write-up of N'Djamena baskets — interesting as a cross-check, not as a source. |

## Next gaps to target (priority order)

1. **`airtel_td_internet`** — Playwright. Pairs with the `moov_africa_td` tariff source to give division 08 two operators instead of one.
2. **`shamsconnect_menu_td`** — Playwright. Would be Chad's first restaurant/COICOP 11.1.1 source.
3. **`carros_td`** — scope the `sitemap-cars.xml` shards to Chad cities/states for COICOP 07.1.
4. **`soukdarna_td`** — re-probe `/api/public/products` in ~6 months; the surface is good, the catalog is currently empty.

---

# Chad — earlier passes

_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 partial pass)

Before this pass: `wfp_prices` only, 0 retail sources. **Result: 1 shipped.**
The source was already identified by the previous pass but rejected for being
non-food; it is onboarded now that non-food sources are in scope.

## Shipped

| Source name | URL | Channel / role | Status | Notes |
|---|---|---|---|---|
| `tchadcommerce_td` | https://tchadcommerce.com/ | marketplace / `retailer_sku` | **SHIPPED** | General vendor marketplace in N'Djamena on WooCommerce. **Store API is open and healthy** — `per_page`/`page` both work, reports `currency_code: XAF` with `currency_minor_unit: 0` (prices need no division). Test run scraped the **whole catalog: 28 items** in one request; XAF 12,500 backpack (~US$20), XAF 10,000 furniture-moving tool — sane. 28 categories led by fashion, solar equipment, home goods and vehicles; "AgroAlimentaire" holds only a handful of items. Small but real, and it is the first retail source of any kind for Chad. |

## French-language search: run, and it came back empty for grocery

A proper French-language search (`supermarché en ligne livraison courses
N'Djamena`) was run this pass — the lever the 2026-09-01 file asked for. It
returned **only directory listings and Facebook pages**: Modern Market, Dembé
Market, Le Grand Marché, Marché de Diguel, Alimentation "La Tchadienne", Le
Bon Marché, Moursal Market. No e-commerce storefront for any of them. This
converts Chad's grocery gap from "unexamined" to a **searched negative**: the
online grocery sector, if any, is Facebook-page storefronts with no
independent catalog or checkout.

## Dead ends (carried forward)

| Candidate | URL | Status |
|---|---|---|
| Modern Market Tchad | facebook.com/Modernmarkettchad | **FACEBOOK-ONLY** (`modernmarkettchad.com` NXDOMAIN) |
| Le Bon Marché | facebook.com/lebonmarcheNDJ | **FACEBOOK-ONLY** (`lebonmarche.td` NXDOMAIN) |
| N'Djamena Mall | ndjamenamall.com | **PARKED** |
| Jumia | jumia.td | **DEAD** — Cloudflare challenge, Chad not in Jumia's market list |
| Sahil Express | sahil-express.com | **RESTAURANT DELIVERY**, not grocery |
| Score Tchad, Casino N'Djamena, Alwatanya, Ramco, SODEA, Sonasut | — | **NO DOMAIN FOUND** |

## Next steps

- Chad's grocery gap now looks structural rather than search-limited. Treat a
  future grocery pass as low-yield; re-check only on the standard ~6-month
  staleness window.

## Common Crawl coverage

Probed 2026-09-02 by the common_crawl session: 8 crawls spanning 2019-2026,
`max_blocks=40`. Counts are host records in the CC index and, separately, the
subset matching the manifest's `archive_path_re`.

| Source | Crawls with host | Host records | Matching PDP regex | Verdict |
|---|---|---|---|---|
| `tchadcommerce_td` (WooCommerce Store API) | 4/8 | 256 | 47 | Thin but real. |


`archive_prefix` on `tchadcommerce_td` was shortened to the bare registrable host on
2026-09-02. It is a plain **string** prefix applied to cdx lines *before*
`archive_path_re` is consulted, so a path in the prefix hard-caps what any regex
can see, and a wrong one fails silently — no manifest, no miss record, no error.
Filtering is `archive_path_re`'s job. Over-inclusion is free (`surt_prefix`
rstrips the trailing slash regardless), and a bare host survives the URL-scheme
migrations that break path prefixes.
_Inventory written: 2026-09-01_

SSA sweep, agent A. Country had only `wfp_prices` (shared regional HDX
fetcher) before this pass — 0 retail sources. **Result: 0 sources shipped.**
Discovery used a mix of live WebSearch (early in the pass) and, once the
session's shared WebSearch budget was exhausted mid-sweep, direct domain
probing + WebFetch on directory pages only. **This is a partial search, not
an exhaustive one — the domain-probing portion found nothing, but a future
pass with a fresh WebSearch budget should re-run proper French-language
queries before treating Chad as settled the way CAR/STP are.**

## Dead ends

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Modern Market Tchad | facebook.com/Modernmarkettchad | **DEAD — Facebook-only** | 2,600 sqm, 12,000+ items per its own description, but no independent website found; `modernmarkettchad.com` does not resolve (NXDOMAIN). |
| Le Bon Marché | facebook.com/lebonmarcheNDJ | **DEAD — Facebook-only** | `lebonmarche.td` does not resolve (NXDOMAIN). |
| N'Djamena Mall | ndjamenamall.com | **DEAD — parked domain** | Resolves 200 but is a bare LWS (French host) domain-registration confirmation/placeholder page, zero content built out. |
| TchadCommerce | tchadcommerce.com | **DEAD for food — thin classifieds site** | Real WooCommerce Store API (open, `/wp-json/wc/store/v1/products/categories`), but total catalogue is only ~33 products across 8 top-level categories; "AgroAlimentaire" (food) has exactly 6 products. Functions as a general classifieds/vendor-listing site (fashion, solar equipment, real estate, vehicles dominate), not an active grocery retailer. Fails the Phase-6 row-count bar for a dedicated food source even before considering channel. |
| Jumia | jumia.td | **DEAD — no Chad storefront** | Returns a Cloudflare "Just a moment…" challenge page consistent with a squatted/reserved domain, not live Jumia infrastructure (same pattern as `jumia.ga` in Gabon's confirmed-dead inventory). Jumia's current active market list does not include Chad. |
| Sahil Express | sahil-express.com | **NOT PURSUED — restaurant/meal delivery, not grocery retail** | Live site but scoped to prepared-food delivery from restaurants, not a supermarket/grocery catalogue. |
| Score Tchad, Casino N'Djamena, Alwatanya, Ramco Tchad, SODEA Tchad, Sonasut | — | **NOT FOUND** | No resolvable domain located for any of these under plausible `.td`/`.com` patterns; not chased further via search (budget exhausted). |

**Conclusion:** No viable food-and-beverage retail source found this pass.
Chad's online grocery sector, if any exists, is confined to Facebook-page
storefronts with no independent catalogue or checkout — structurally similar
to Gabon/CAR/STP. Re-check with a fresh WebSearch budget before writing this
off as permanently exhausted.
