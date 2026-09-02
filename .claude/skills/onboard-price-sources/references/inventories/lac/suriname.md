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

**Result: 7 sources / 1 food.** Clears the >=5-source bar; falls short of the
>=2-food bar. See "Food discovery — extensive, still short" below for what was
tried.

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
