# Suriname — price source inventory

_Inventory written: 2026-09-01_

Config directory: `src/prices/configs/lac/south_america/suriname/`. Currency SRD.
Wave-13 brief handed exactly one candidate (Kirpalani's); everything else below
came from Dutch-language discovery (`online supermarkt Suriname`, `boodschappen
bezorgen Paramaribo`, plus targeted follow-ups for named chains and utilities).

## Onboarded (7 sources: 1 food, 6 non-food)

| Source key | analytical_role | channel | Notes |
|---|---|---|---|
| `telesur_sr` (pre-existing) | retailer_sku | electronics | Telesur device/accessories shop, WooCommerce Store API. |
| `avoda_sr` | retailer_sku | **supermarket** | "De online supermarkt van Suriname" — HEM Suriname N.V.'s SRD webshop. 1,226 SKUs, 33.9% in Levensmiddelen-family categories on a full unbounded run. **This is Suriname's only onboarded food source.** |
| `kirpalani_sr` | retailer_sku | dept-store | The brief's supplied candidate. Confirmed general/home retailer (Magento SSR) — no grocery department anywhere in the 47-link nav or the `/groothandel` wholesale landing page (0 products). 3,014 rows on an unbounded run (max-items 3000, cap hit — real catalog is larger). Not food. |
| `abs_cpi` | cpi_benchmark | null | ABS monthly CPI PDF. Each release carries a rolling ~24-month table; one download backfills ~2 years. 240 rows (24 months x 10 divisions) on first run. Division "9/10" (Recreation+Education bundled) and the all-items "Totaal" column are intentionally dropped (no clean COICOP code / no sentinel). |
| `ebs_tariff` | tariff | null | N.V. EBS electricity tariff (nvebs.com), clean HTML tables, base fee + per-kWh consumption tiers. 11 rows, effective Dec 2024. |
| `swm_tariff` | tariff | null | SWM drinking-water tariff (swm.sr), one clean HTML table, 9 tariff groups. 9 rows, no stated effective date (period_kind: snapshot). |
| `telesur_tariff` | tariff | null | Telesur prepaid mobile-internet bundle tariffs (www.telesur.sr/prepaid/) — genuinely different source from `telesur_sr` (different page, different analytical_role, no shared product namespace; documented explicitly in the YAML `notes:` so it doesn't read as a duplicate). 6 rows. |
| `wangfamirie_sr` | retailer_sku | **supermarket** | Netherlands-run diaspora grocery/parcel webshop for delivery to Suriname (WooCommerce Store API, EUR-priced). 3,601 SKUs, real grocery departments dominant by count (DRANKEN, ONTBIJT, VLEES, ZUIVEL, GROENTEN, etc.). Independent catalog/operator from avoda_sr / now2su.com / surishop.nl. **Second onboarded food source, found 2026-09-11.** |

**Result (as of 2026-09-01): 7 sources / 1 food.** Clears the >=5-source bar; falls short of the
>=2-food bar. See "Food discovery — extensive, still short" below for what was
tried.

**UPDATE 2026-09-11: now 8 sources / 2 food.** `wangfamirie_sr` (Netherlands-run
diaspora grocery webshop) shipped after a fresh Dutch+English `ddgs` sweep
(named-chain checks for Total Foods, Baas Foodmarket, Mr. Chin's, Wong
Supermarket, VSH Foods/United, Su-Store — none panned out as real Suriname
web-storefronts, see new dead-end rows below) plus a general re-run of
"supermarkt Suriname online bestellen" — style queries. Clears the >=2-food bar.

## Food discovery — extensive, still short

Only one genuine, scrapeable, in-country food retailer was found. Every other
lead in the brief (Choi's, Tulip, Superkoop, Goedkoop, Combé Markt) and every
follow-up lead found during discovery was DEAD or a duplicate:

| Candidate | Status | Evidence |
|---|---|---|
| **Choi's Supermarket** (`choisupermarket.com`) — brief's named "largest chain" | **DEAD** | Expired SSL cert; page is a 2008-era cPanel "Temporarily Disabled" hosting-suspension stub, not a live storefront. Facebook page (`facebook.com/choisupermarket`) is active but has no e-commerce/ordering link. Business itself is real (3 physical locations per whoswho.sr) but has no working website. |
| **Tulip Supermarket** (`tulip-supermarket.com`) | **DEAD (brochure only)** | Live single-page site (Unsplash stock photo, `#departments` anchor, social links) with zero product listings, zero prices, no ordering flow. Physical presence only. |
| **Superkoop** / **Goedkoop** (brief-named chains) | **NOT FOUND** | Two separate Dutch-language WebSearches turned up nothing under either name as a Suriname supermarket. Possibly defunct, mis-named in the brief, or too small to have any web footprint. |
| **Combé Markt** | **NOT FOUND** | Only a street-address reference (Grote Combeweg 121) in a generic directory; no website located. |
| **now2su.com** (HEM Suriname N.V.'s diaspora-order storefront) | **SAME SHELF as avoda_sr — not onboarded** | `hem.sr/nl/webshops` explicitly lists both `avoda.sr` and `now2su.com` as HEM's own storefronts. A 300-item sample from each Store API found 277/300 (92.3%) identical product names — same catalog/backend, EUR-priced for diaspora order/pickup vs. avoda's SRD domestic pricing. Onboarding both would double-count one shelf (rule 19). |
| **hem2b.com** (HEM's B2B wholesale webshop) | **NOT PURSUED** | Same corporate group as avoda/now2su (further same-distributor overlap risk); `channel: wholesale` would not count as food regardless. |
| **Fernandes Express** (grocery delivery, active per 2020-2024 news coverage) | **DEAD / GEO-FENCED** | Canonical webshop domain `fernandes-express.com` no longer resolves (NXDOMAIN, confirmed against both 8.8.8.8 and 1.1.1.1) — even though a live 2024 news article still links to it via a `bit.ly/FernandesExpressShop` redirect that lands on the dead domain. A `shop.fernandes.sr` subdomain does resolve in DNS but times out at the TCP layer (15s, both plain curl and curl_cffi) — consistent with a country geo-fence (same signature as other CDN connection-reset entries in `known_blockers.md`) rather than a WAF challenge. |
| **surishop.nl** (NL-domiciled diaspora grocery-delivery-to-Suriname reseller) | **NOT PURSUED — thin/near-empty** | `/Levensmiddelen` category page renders mostly `€0,00` placeholder rows (1 real product with a price). Would also fail the Phase-6 >=5-row gate; not investigated further. |
| Restaurant/prepared-food delivery apps (`paramariboeethuis.nl`, HomeDeliverBox) | **OUT OF SCOPE** | Prepared-meal ordering (COICOP 11, restaurants), not retail grocery SKUs — doesn't fit the food-channel enum (`supermarket, hypermarket, convenience, fresh-market, specialty-food`) even if scraped. |
| Kirpalani's `/groothandel` (wholesale landing page) | **CONFIRMED EMPTY** | 0 `product-item-link` / `data-price-amount` matches — informational page, not a catalog. |

| **Foodbasket** (`foodbasket.sr`) — new 2026-09-11 lead, not in the 2026-09-01 pass | **DEAD (backend infra)** | Live Next.js SPA ("affordable daily groceries across Suriname") but its own tRPC API backend fails DNS resolution server-side (`getaddrinfo ENOTFOUND synergy-core-api-x7ui4.ondigitalocean.app`, HTTP 500 on every `warehouses.getAll` call) — the app cannot list a single warehouse, let alone a product. See `known_blockers.md`. |
| **Total Foods Suriname**, **Baas Foodmarket**, **Mr. Chin's supermarket**, **VSH Foods** / **VSH United** (as a food retailer) | **NOT FOUND** | Dutch + English `ddgs` sweep (pinned backends) found no Suriname web storefront under any of these names. VSH United is a real Suriname conglomerate (shipping/trading/holdings) with no grocery/food division found. |
| **Wong Superstore** (Djamoestraat 42, Paramaribo) | **NOT FOUND — no website** | Real physical supermarket (confirmed via OpenStreetMap/Mapcarta/Cybo map listings) but no web storefront domain found under any obvious name. |
| **Su-Store / Superstore** | **NOT FOUND / MISIDENTIFIED** | Search under this name surfaces only "SUpremium Store" (Albertlaan 6, Paramaribo — an electronics/general store per Facebook, not food) and the already-onboarded `luckystore.com` (electronics). No food-retail "Su-Store" found. |
| **Wang Famirie** (`wangfamirie.com`) | **SHIPPED as `wangfamirie_sr`** | See onboarded table above. |

**GOw2 Energy (Staatsolie's retail fuel arm) — probed, not shipped (structural
row-count gate, not a discovery failure):** `gow2.com/en/fuels/` publishes
live, dated pump prices (Gasoline/Diesel, e.g. "48.32 price in SRD/liter
updated 25/03/2026") but the page structurally only ever carries 2 priced SKUs
— it can never clear the Phase-6 >=5-row gate from a single fetch. A Wayback
Machine historical-snapshot backfill was attempted to build up enough past
effective-dated rows, but `web.archive.org/cdx/search/cdx` returned `429 Too
Many Requests` on every attempt (shared-fleet Wayback throttle, per this
skill's own `known_blockers.md` policy-ceiling note) — not pursued further
under wave-13 time budget. **Worth a dedicated retry** (run alone, off-peak)
if Suriname fuel coverage is revisited; the fetcher shape would otherwise be
trivial (regex two `SRD ##.##` + date values off one static page).

## Non-onboarded platform notes

- Kirpalani's (`kirpalani.com`) is Magento 2 (Luma theme, "BluebirdDay" skin).
  GraphQL (`/graphql`) is Cloudflare-challenge-gated; REST (`/rest/V1/products`)
  is 401 (consumer not authorized). Neither surface is usable — the spider
  scrapes server-rendered category HTML instead (`MagentoSSRBaseSpider`).
- avoda.sr / now2su.com / hem2b.com are all WooCommerce Store API
  (`/wp-json/wc/store/v1/products`), same as the pre-existing `telesur_sr`.

## Food discovery — pass 4 (2026-09-11, fill-gap-sources worktree)

Fourth independent same-day pass, targeting a fresh set of named chains not
covered by passes 1-3 (Mr. Bing, Bas Supermarkt, Superbaas, Vreedzaam,
Prijsklopper, Amazing supermarket, Foodcity, Chinese/Javanese tokos).
WebSearch was unavailable (session-wide budget exhausted); substituted
`curl_cffi impersonate=chrome124` against `html.duckduckgo.com/html/`.
**Result: no new source. Zero of the 7 new named candidates resolved to a
real, reachable, Suriname-domiciled webshop.**


## Food discovery — pass 5 (2026-09-11, fill-gap-sources worktree, OSM-driven)

Fifth same-day pass. Brief handed 6 named candidates not covered by passes
1-4 (VSH Foodmart, Baas Supermarket, C1000/Continent Suriname, Kortom,
Wong/Wong's supermarket, Hermitage Mall grocers) plus a Shoprite/SPAR/Pick n
Pay check. **All 6: NOT FOUND** — no DNS resolution under any guessed
domain variant (`vshfoodmart.*`, `baassupermarket.*`, `c1000*.{sr,com}`,
`continent*.{sr,com}`, `kortom*.{sr,com}`, `wong*supermarket*.{sr,com,online}`,
`hermitagemall*`), and none appear among 506 Suriname shop nodes pulled from
OpenStreetMap Overpass (`shop~supermarket|convenience|grocery|greengrocer|
butcher`, within the SR admin boundary). **Shoprite/SPAR/Pick n Pay:
confirmed absent** — no DNS hit, no OSM match, consistent with "no SA
regional chain operates in Suriname."

Consistent with passes 1-4's WebSearch outage: this pass's WebSearch was
*also* already at the session-wide 200-call cap before it started. WebFetch
against duckduckgo.com/html, bing.com, ecosia.org, mojeek.com and r.jina.ai
all failed or returned decoy content (DDG CAPTCHA; Bing returned unrelated
RV-park/stock-ticker results for Suriname-specific queries; Ecosia/Mojeek
403; r.jina.ai needs an API key). **Pivoted to OpenStreetMap Overpass as
the primary discovery tool** — for a country this thin on searchable web
presence, pulling every tagged shop node and checking which ones carry a
`website` tag outperformed every search-engine path tried this pass and
cost one API call. Of the 506 OSM nodes, only 6 carried a `website` tag;
this is a reasonable proxy for "how much of Suriname retail food has ANY
web presence" — most of the country's supermarket/convenience landscape is
small Chinese-family-run shops with none at all.

Two of those 6 website-tagged nodes were new, live, and shipped:

| Source key | channel | Catalog | Verified 2026-09-11 |
|---|---|---|---|
| `rossignolslagerij_sr` | specialty-food (butcher, Shopify) | `/products.json`: 94 products / 254 SKU-variant rows, single page (page 2 empty — confirmed true catalog size, not truncation) | 254 rows, 254 distinct URLs |
| `vcm_sr` | specialty-food (butcher, WooCommerce Store API) | `wp-json/wc/store/v1/products`: 170 products (page1=100 + page2=70, zero id overlap — real pagination) | 100 rows (max-items cap), 100 distinct URLs |

`vcm_sr` is VCM Slagerijen, the retail butcher/webshop arm of N.V.
Verenigde Cultuur Maatschappijen — the parent site `vcm.sr` explicitly
routes "webshop, catering services" to `winkel.vcm.sr`, while a sibling
arm `boerderij.vcm.sr` (wholesale agriculture/livestock) was deliberately
NOT onboarded to avoid a retail/wholesale double-count of the same
producer group. `rossignolslagerij_sr` is Rossignol Slagerij, whose
physical branches appear three times in the OSM dataset (Rossignol,
Rossignol Slagerij, Rossignol 2 GO).

The other 4 website-tagged OSM nodes were dead ends: `bestmart.sr`
(zero-byte, already on record), `Zinnia Supermarket` (Facebook page only,
no independent site — unreachable without login), and **`choisupermarkt.com`**
— note the Dutch spelling (no "e"), a *different* domain from the
already-recorded-dead `choisupermarket.com` (English spelling, expired
cert) — which resolves 200 via Cloudflare with a real Shopify fingerprint,
but the domain has been **squatted**: the page served is an Indonesian
togel (illegal-lottery/gambling) spam site (`<title>TOTO TOGEL 158`,
canonical link to `youknowwesew.com`), not the real Choi's storefront. New
failure signature, not previously on record — the lapsed domain of a real
defunct-website business got picked up by a spam operator.

A handful of other domain guesses tried and confirmed dead this pass:
`surimarket.com` (parked `/lander` redirect, 114 bytes), `transamerica.sr`
(resolves but serves a bare `404.html` — registered, no site behind it,
despite "Transamerica" being a real physical shop per OSM), `soengngie.com`
→ redirects to `soengco.com` (Soeng Ngie & Co is a Surinamese-Chinese
sauce/condiment brand content site — recipes and product marketing, zero
shop/cart, not a retail price source), `soengngie.sr` (suspended-hosting
stub), `vshfoods.com` (VSH Foods — real, live, but a manufacturer/export
brand site with zero shop/cart content, confirming the same "not a
retailer" verdict passes 1-4 already reached for VSH under other domain
guesses), `kersten.sr` (N.V. C. Kersten & Co — resolves with shop/cart
keywords but is the Toyota-dealership site, automotive not food).

**Suriname now at 11 sources / 4 food** (avoda_sr general grocery +
wangfamirie_sr general grocery + rossignolslagerij_sr + vcm_sr, the latter
two meat-narrow specialty-food). The ABS average-price lever flagged by
pass 3 (`statistics-suriname.org`) now shows 200-on-all-profiles per the
main `known_blockers.md` (line 37 — was a transient network issue, not a
block) and is the best remaining target for general division-01 depth; not
re-attempted this pass.
