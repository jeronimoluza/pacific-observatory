# Guinea-Bissau

_Inventory written: 2026-09-12_ (Phase-3 entry from a 32-row PENDING
candidate list; no fresh discovery run)

Before this pass: 6 manifests (`ikuma_gw`, `elado_gw`, `s_360v2sarl_gw`,
`ariah_gw_services`, `wfp_prices`, `wb_rtdi_prices`), 1 filled COICOP leaf of
257. **Result: 3 shipped.** Worked the low-coverage rule — took whatever
verified, cheapest first, no gap-ranking.

## Shipped

| Source name | URL | Channel / role | Verified rows | Notes |
|---|---|---|---|---|
| `nhamburguer_gw` | https://meucomercio.com.br/nhamburguer | supermarket / `retailer_sku` | **3,737** | The run's big win, and it was hiding behind a foreign hostname. |
| `telecel_gw` | https://telecel.gw/planos-tarifarios | `null` / `tariff` (08.3.2.0) | 12 | Official mobile operator rate card + bundles. |
| `bissauonlinemarket_gw` | https://bissauonlinemarket.com/ | marketplace / `retailer_sku` | 7 | Tiny but real; barely clears the 5-row bar. |

### Traps these three carry

1. **A `.com.br` host can be a domestic retailer.** `nhamburguer_gw` is NHA
   PEDIDO, a Bissau grocery on the Brazilian white-label platform
   meucomercio.com.br (Nextar). The store record gives Avenida Pansau Na Isna,
   Bairro de Santa Luzia, Bissau, lat 11.8747 lon -15.5913, and the storefront
   prices in FCFA. Filtering this candidate list by TLD would have thrown away
   the largest catalogue in the country.
2. **`perPage`, not `page`.** The Nextar API at
   `POST api.ecommerce.nextar.com/api/v2/prod/products` **ignores `page`
   entirely** — page=0/1/2/3 return an identical window. `perPage` is the only
   lever and is honoured to the whole catalogue (100 -> 100, 1000 -> 1000,
   5000 -> 3,793). A page-loop spider here would re-emit the same first N rows
   forever and look like it was working. Enumerability had to be proven by the
   perPage ladder, since this API cannot express a page-2 diff.
3. **Static headers, no session.** That API needs only `client: NEX-SITE`,
   `shop-code: <id>`, `token: bGlueGludGVncmF0aW9udG9rZW4=` (base64
   "linxintegrationtoken", a site-wide constant in the public JS bundle).
   Playwright was needed to *find* it and never runs at collection time.
4. **Ignore `PromoSalePrice`.** Several nhamburguer rows carry a promo price
   whose `PromoEndAt` is years in the past — the platform never clears them.
   `SalePrice` is the only reliable current shelf price.
5. **Telecel's HTML has no prices at all.** 369 KB of tRPC/Next.js shell, zero
   price strings — an `html_scrape` extractor returns nothing. The hydration
   endpoint `GET /api/trpc/plans.list,bundles.list?batch=1&input=<json>` is
   open over plain HTTP. Also: `telecel.gw` and `telecelgb.com` are the SAME
   site (byte-identical HTML, same analytics site id) — one manifest, not two.
6. **The Telecel plan's own price is 0.** Telecel+ is free to hold; its value
   is the rate card in sibling fields (calls 72 XOF/min, SMS 30/35, intl 120).
   Emitting only priced plan rows would have yielded nothing from `plans.list`.
7. **Seven price nodes per page on bissauonlinemarket.** Elementor repeats the
   whole catalogue as a "related" grid on every ad page. The FIRST
   `.jet-listing-dynamic-field__content` node is the page's own price —
   verified against all 7 ads. Selecting all nodes emits the catalogue once
   per page.

## Rejected, with the measured reason

| Source | URL | Reason |
|---|---|---|
| `carrosbissau_gw` | carrosbissau.com | **SYNTHETIC CONTENT.** Rolls-Royce Silver Shadow in Quebo, Ferrari Dino 246 GT in Canchungo, Lancia Flaminia in Gabú, MG Midget in Mansoa — one classic car per GW town, round-robin. A 2023 RAV4 listed at XOF 57,405 (~US$95) with a gmail advance-fee contact. Site is 200/SSR and enumerable; the *content* is the problem. Prior triage had it P1 build-now. |
| `wropo_gw` | gw.wropo.com | **SEEDED DEMO.** 22 listings total in `sitemap/posts.xml`; only 4 carry a price and **all four are the identical 380,000 CFA**, including an aluminium bistro set and a forged-document ad ("EU Passports ID Card Social Security"). Category pages hold 2 items; page 2 is empty. Titles are machine-generated dropship copy. Prior triage had it P1 build-now. |
| `juntosgb_gw` | juntosgb.com | Shopify, `/products.json` wide open, 10 products — but `/meta.json` says `country: FR`, city "Mantes la ville", `currency: EUR`. A France-based diaspora merch shop selling Guinea-Bissau football kit, not a GW retailer. |
| `ceiba_bissau_hotel` | ceibabissau.com | WooCommerce Store API returns 200, but every room's `prices.price` is **"0"** and `currency_code` is EUR. No price observations exist to collect. |
| `africarrieres_gw_tariffs` | africarrieres.com/guinee-bissau/pt/tarifs | Candidate-facing job-platform plans, prices in clean `span.text-3xl` nodes — but only **4 distinct priced rows** (490 XOF/credit, 4 900/30d, 11 900/90d, 39 900/365d; the 11 900 renders twice). Below the 5-row bar. The "~3 967 FCFA/meses" strings are derived monthly equivalents, not published prices. |
| `canalplus_gw_subscriptions` | subscribe.canalplus.com/gw/tab/offres | **GEO-GATED.** 200 on curl_cffi, but Playwright from a European datacenter IP never gets past "CANAL+ est disponible dans votre zone géographique / Continuer" — the offers never render and `hodor.canalplus.pro` returns nothing. Needs an in-country exit node, not a TLS fingerprint. |
| `ctd_bissau_tuition` | ctdbissau.com | 403 on chrome124, chrome120 AND safari17_0. Hostinger `hcdn` edge. Genuine block, not a curl artifact. |
| `orange_bissau_mobile_internet` | orange-bissau.com | TLS certificate verify failure, then connection timeout at 45 s on every profile. Host effectively unreachable. |
| `amatlgb_gw` | amatlgb.com | **NXDOMAIN** — `Could not resolve host`. Site is gone since the 2026-09-10 probe. |
| `joxko_gw_mobile_topups` | joxko.com | International top-up reseller: 40 offers priced in **EUR** for XOF credit. Cross-border reseller margin, not a domestic operator tariff. `telecel_gw` covers this properly. |
| `uquid_gw_topups` | shop.uquid.com | Same shape — Wix storefront, USD crypto-checkout reseller prices for XOF top-ups. |
| `foodiesbae_bissau_term` | foodiesbae.com | **NOT GUINEA-BISSAU.** Homepage carries "Dakar" 68 times against "Bissau" 4 — and the Bissau hits are the dish *oseille feuille de Bissau* (hibiscus leaf), not the city. It is a Senegal platform. |
| `pharmaconnect_bissau` | pharmaconnect.me | Returns a 6.2 KB stub with zero country keywords; no Bissau pharmacy attribution verifiable. |
| `stampera_guinea_bissau_stamps` | stampera.eu | International philatelic seller, EUR. Collector market, not domestic retail. |
| `worldbanknotes_gw_collectibles` | worldbanknotes.eu | International numismatic seller, EUR, obsolete Guinea-Bissau peso notes. Not a consumer price. |
| `bookingauto_gw_car_rental` | bookingauto.net | 403 Cloudflare on all three impersonation profiles. |
| `hotels_scanner_bissau` | hotels-scanner.com | 403 Cloudflare on all three impersonation profiles. |
| `skyscanner_bissau_hotels` | skyscanner.fr | Redirects to an Amazon-hosted captcha (`/sttc/px/captcha-v2/`). PerimeterX. |
| `booking_bissau_hotels` | booking.com | Reachable, but a date-sensitive travel-meta aggregator; nightly rates vary per query date and are not a stable observation. Not pursued. |
| 9 news / blog / guidebook rows | — | `ang_ese_tuition_2025`, `cashew_base_price_news_gw`, `conosaba_bandim_food_news`, `eagb_contract_tariffs_news`, `jeanmichelvoyage_bissau_prices`, `jornalnopintcha_food_cement_prices_2022`, `odemocratagb_cashew_2023`, `opentravelguide_gw_transport_costs`, `petitfute_bissau_restaurants`. All one-off articles or editorial guidebook pages, not maintained machine-readable sources. The cashew and EAGB rows are genuine *leads* for an official producer-price / utility-tariff feed — worth chasing at ANCA / EAGB / the regulator, not at the blog. |

**Blockers worth carrying to `known_blockers.md`** (not written there this run —
sibling agents were editing that shared file concurrently): `ctdbissau.com`
(Hostinger hcdn 403, survives all three impersonation profiles),
`bookingauto.net` and `hotels-scanner.com` (Cloudflare 403, same),
`skyscanner.fr` (PerimeterX captcha redirect), and
`subscribe.canalplus.com/gw` (geo-gate, not a WAF — the distinction matters,
a fingerprint will never fix it).

## Still open for Guinea-Bissau

- **EAGB electricity/water tariffs.** Only a news report found (contract fees
  cut to 17,000 / 10,000 FCFA effective 2026-05-01). Division 04 is unfilled
  and an official EAGB or regulator publication would fill it.
- **Cashew producer reference price.** Government sets it annually (410 FCFA/kg
  in 2025, 375 in 2023/2022, 360 in 2021, 350 in 2020). Consistently reported
  by press; the primary ANCA/Ministry source was not located.
- **Orange Bissau.** The other mobile operator. Host was unreachable this run —
  worth one cheap re-probe later, since `telecel_gw` alone makes division 08
  single-operator.
- **Canal+ GW.** 25,000 FCFA/month TV subscription sits behind a geo-gate; an
  in-country exit node would land COICOP 08.3.9.2.


---
_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 zero-budget pass)

Before this pass: `wfp_prices` only, 0 retail sources. **Result: 1 shipped.**
The prior pass ran with zero WebSearch budget and explicitly asked for a
Portuguese-language search; that search immediately found the country's own
self-described first online supermarket.

## Shipped

| Source name | URL | Channel / role | Status | Notes |
|---|---|---|---|---|
| `ikuma_gw` | https://www.ikuma.online/ | supermarket / `retailer_sku` | **SHIPPED** | "1º Supermercado Online da Guiné Bissau". WooCommerce with **761 product URLs** in `product-sitemap.xml`. Test run scraped 7 items; prices sane against XOF (Água com Gás 250, aftershave 2,250, an upright freezer 375,000 ≈ US$620). Groceries and general merchandise both present, so `coicop_codes` is left unset for the classifier. |

### Two traps this source carries

1. **Store API is half-broken.** `/wp-json/wc/store/v1/products` returns
   **HTTP 500** on every variant tried (`per_page`, `page`, the older
   `wc/store` namespace), while `/products/categories` returns 200 with 140
   categories. A Store-API probe that only checks the categories route would
   wrongly conclude the API works. The spider uses the sitemap instead.
2. **JSON-LD emits a placeholder currency.** PDP JSON-LD carries
   `priceCurrency: "ABC"`, which is not a currency at all. The manifest forces
   `XOF` via the spider's `FORCE_CURRENCY`. Anything trusting the page's own
   currency code here would emit garbage.
_Inventory written: 2026-09-01_

SSA sweep, agent A. Country had only `wfp_prices` (shared regional HDX
fetcher) before this pass — 0 retail sources. **Result: 0 sources shipped.**
**This pass ran with zero WebSearch budget** (session-wide cap exhausted
before this country's turn) — every candidate below came from direct domain
probing and one WebFetch on a directory page, not a real search sweep.
Treat as a weak/partial pass; re-run Phase 2 with search access before
concluding Guinea-Bissau has no online grocery sector.

## Dead ends

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Bissau Online Market | https://bissauonlinemarket.com/ | **NO CATALOG API** | Live 232KB WordPress/WooCommerce-flavoured page but the Store API 404s and no price markup was detected on the homepage. Described in search results as a free classifieds/advertising platform rather than a retailer — likely seller-authored listings even if a catalog is found. Low priority. |
| SPAR Guiné (Bissau) | facebook.com/sparguine | **FACEBOOK-ONLY** | Real SPAR franchise presence in Bissau with no independent domain found. |
| Jumia | jumia.gw | **DEAD** | Carried forward: Cloudflare "Just a moment…" on a domain not in Jumia's active market list. |
| Casa Alberto | casaalberto.com | **PARKED** | Carried forward. |
| Kalliste Bissau | kalliste.gw | **NXDOMAIN** | Carried forward. |

## Next steps

- Re-check whether Ikuma's Store API 500 is ever fixed; a working API would be
  much cheaper than 761 PDP fetches.

## Common Crawl coverage

Probed 2026-09-02 by the common_crawl session: 8 crawls spanning 2019-2026,
`max_blocks=40`. Counts are host records in the CC index and, separately, the
subset matching the manifest's `archive_path_re`.

| Source | Crawls with host | Host records | Matching PDP regex | Verdict |
|---|---|---|---|---|
| `ikuma_gw` (WooCommerce, sitemap walk) | 5/8 | 1017 | 797 | Good. |


`archive_prefix` on `ikuma_gw` was shortened to the bare registrable host on
2026-09-02. It is a plain **string** prefix applied to cdx lines *before*
`archive_path_re` is consulted, so a path in the prefix hard-caps what any regex
can see, and a wrong one fails silently — no manifest, no miss record, no error.
Filtering is `archive_path_re`'s job. Over-inclusion is free (`surt_prefix`
rstrips the trailing slash regardless), and a bare host survives the URL-scheme
migrations that break path prefixes.
| Jumia | jumia.gw | **DEAD — Cloudflare challenge / no real storefront** | Same "Just a moment…" 403 pattern as jumia.td/jumia.cg; Jumia's active market list does not include Guinea-Bissau. |
| Casa Alberto (Bissau) | casaalberto.com | **DEAD — parked domain** | Resolves 200 but is a bare client-side redirect stub (`window.location.href="/lander"`), no content. |
| Kalliste Bissau | kalliste.gw | **NOT FOUND — NXDOMAIN** | |
| goafricaonline.com Guinea-Bissau directory | goafricaonline.com/gw, /gw/annuaire | **INCONCLUSIVE** | Both pages return HTTP 200 but the category/listing structure appears to be client-side rendered — no supermarket/food category links were recoverable from the static HTML via regex. Would need a JS-capable fetch to actually browse this directory; not attempted this pass. |
| Le Ninho Bissau, Bijagos supermercado | — | **NOT FOUND** | No resolvable domain found for either name; not chased via search (budget exhausted). |

**Conclusion:** No viable food-and-beverage retail source confirmed this
pass, but confidence is low given no real search ran. Re-check with fresh
WebSearch budget, particularly for Portuguese-language local terms
("supermercado Bissau online", "compras online Guiné-Bissau") which this
pass could not run.
