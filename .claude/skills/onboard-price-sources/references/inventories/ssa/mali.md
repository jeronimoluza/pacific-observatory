# Mali

_Inventory written: 2026-09-01_

Wave 9 pass. Cold-start: zero workbook candidates (confirmed against
`outputs/sources_pending_jero.xlsx` — "NO CANDIDATES - discovery" sheet lists Mali as
`retailer_sources_now=0, any_sources_now=0, sources_needed_to_reach_5=5`), and Mali had
**no country-specific source at all** — the only manifest was the shared regional
`wfp_prices` HDX fetcher. Target was >=5 sources AND >=2 food. **Result: 5 sources / 2
food — target met.** Full evidence for dead leads is filed in `known_blockers.md` under
the matching headings.

## Sources built this pass

| Source key | Channel | `analytical_role` | Rows (test run) | Notes |
|---|---|---|---|---|
| `fpma_mli` | null | `official_avg` | 2585 | FAO GIEWS FPMA Tool REST API, reporting partner Afrique Verte (Sahel cereals NGO — distinct from WFP). 35 series (market x commodity), millet/sorghum/maize/rice, monthly to 2026-08. |
| `minicim_ml` | `supermarket` | `retailer_sku` | 2118 | CIM Market (Bamako), Odoo 19 storefront, 7 physical stores, 10 categories, ~68% food share. |
| `lacornichemali_ml` | `supermarket` | `retailer_sku` | 1014 | La Corniche Mali (Bamako), WooCommerce "Freshio" grocery theme, Store API. ~51% food share by top-level category. 30/1044 raw listings were leftover Faker-generated theme demo data (category="Freshio Category") — filtered in the spider. |
| `malitel_ml_tariff` | null | `tariff` | 21 | Moov Africa Malitel prepaid mobile-data plan cards, COICOP 08.1.0. Needs `verify=False` (permanent cert misconfig, not a block). |
| `wfp_prices` (pre-existing) | null | `official_avg` | — | Shared regional HDX fetcher, unchanged this pass. |

## Dead ends / discovery notes

| Lead | URL tried | Status | Notes |
|---|---|---|---|
| OMA — Observatoire du Marché Agricole | `http://www.oma.gov.ml/` | **DEAD — domain gone** | The brief's #1 lead. `oma.gov.ml` is genuine NXDOMAIN against both `8.8.8.8` and `1.1.1.1` (not a sandbox DNS lie). OMA (created 1989, weekly price collection across 35-64 markets) appears to have lost its independent web presence. |
| APCAM (OMA's parent body, "OMA/APCAM") | `https://apcam.ml/` | **DEAD — brochure only, no data** | Domain resolves and serves 200 (185.221.182.190). Page is a single-page marketing site ("À Propos / Missions / Secteurs / Actualités / Contact") with a modal link literally titled "Bourses & Prix des Céréales / Consulter les cotations hebdomadaires sur les marchés ruraux" — but that link, and every "Actualités" article "Lire le communiqué" link, points at `#contact` (an in-page anchor), not a real bulletin or data page. No table, no PDF, no download anywhere on the site. Confirmed this is not a data source, just brand messaging. |
| FEWS NET (USAID) market price facts | `fdw.fews.net/api/marketpricefacts/?country_code=ML` | **DEAD — zero data despite valid geography** | The shared `_shared.ssa.fews_net` fetcher already covers 13 SSA countries; Mali is NOT one of them and for good reason. `country_code=ML` is a *valid* choice in FEWS NET's own geography endpoints (`/api/geographicunit/`, `/api/market/` both return real Mali records — 1628 geographic units, 40 markets incl. Bamako) but `/api/marketpricefacts/?country_code=ML` returns `{"count":0}` — confirmed against a working comparator (`country_code=CI` returns 4929 facts). FEWS NET tracks Mali's markets but does not publish price facts for it. Do not re-add Mali to `_COUNTRIES` in `fews_net.py` without re-checking this count first. |
| INSTAT Mali (Institut National de la Statistique) | `https://instat.gouv.ml/` | **UNREACHABLE this pass, not confirmed dead** | `instat.gouv.ml` resolves (74.208.235.136 via 8.8.8.8) but every request (curl_cffi impersonate=chrome124, 30s) timed out. Per the brief's note on intermittent Malian gov domains, this deserves a retry in a future pass rather than being written off — DNS is not lying here, the host is just not answering right now. |
| EDM-SA (Énergie du Mali) | guessed `edm-sa.ml`, `edm-sa.com`, `edm.ml` | **NOT FOUND — no domain located** | All three guessed domains are genuine NXDOMAIN on both `8.8.8.8` and `1.1.1.1`. Did not spend WebSearch budget hunting further this pass (electricity tariff was the 4th-priority lead and the pass reached 5/2 without it) — the real domain, if EDM-SA has one, is still unknown. Worth a fresh search next pass. |
| Orange Mali | `https://orange.ml/`, `https://www.orange.ml/` | **UNREACHABLE this pass, not confirmed dead** | `orange.ml` resolves (165.160.13.20) but connection timed out (28s) on two separate attempts (including one retry). Not pursued further — Malitel's tariff page already covered the `tariff` role. Worth a retry. |
| Moov Africa Malitel | `https://malitel.ml/` | **LIVE — built (`malitel_ml_tariff`)** | See sources table above. |
| smart-market.ml | `https://www.smart-market.ml/` | **DEAD — domain gone** | Surfaced by search as "Smart Market, votre marché en ligne à Bamako" with a `/boutique/` page. Genuine NXDOMAIN on both `8.8.8.8` and `1.1.1.1` — the business (if still operating) has lost this domain. |
| Au Grand Frais de Bamako | Facebook page only (`facebook.com/Grandfraisbamako`) | **NOT PURSUED — Facebook-only presence** | Search surfaced only a Facebook video/page, no independent website found. Facebook Shops/Marketplace pages are not catalog-API-backed in general; not probed further this pass. |
| Livrado Mali | App Store listing only | **NOT PURSUED — app-only, no web catalogue** | iOS App Store page found (`apps.apple.com/us/app/livrado-mali/`); described as meal/grocery/mail delivery. No web storefront surfaced. |
| CITY FOOD Mali | App Store listing only | **NOT PURSUED — app-only, no web catalogue** | Same pattern as Livrado Mali. |
| Shopreate (via Fikaso) | `https://www.fikaso.fr/menu-livraison-de-courses-a-domicile-shopreate-bamako` | **NOT PURSUED — third-party delivery-app listing page, not a merchant catalogue** | Fikaso is a delivery-app directory; the linked page is a service description, not a per-SKU catalogue. Would need Shopreate's own site/app, which the search did not surface directly. |
| Mali-achats | `https://www.mali-achats.com/`, `https://mali-achats.com/boutique/alimentation` | **NOT PURSUED — marketplace, deprioritized once 5/2 was reached** | General marketplace with an "alimentation" (food) category; found live and reachable. Not probed for platform/API once the target was already met — a real next-pass candidate (either as a directory of first-party merchants, or, if no directory exists, as a `marketplace`-channel catalogue, which does not count toward the food total per the wave-9 rules). |
| Sodishop / food.sodishop.com | `https://food.sodishop.com/` | **UNREACHABLE this pass** | Resolves (51.178.91.158) but timed out (30s) on first attempt; not retried since 5/2 was already reached via other leads. |
| Ikasougou | `https://ikasougou.com/` | **UNREACHABLE this pass — TLS error** | Resolves (45.95.182.190) but `curl_cffi impersonate=chrome124` fails with `TLSV1_ALERT_INTERNAL_ERROR`. Not retried with other impersonation profiles since 5/2 was already reached. |
| Azar Libre Service, Fourmi, Metro, Grand Marché (brief's named Bamako supermarkets) | not searched individually | **NOT PURSUED — target reached before these were checked** | The brief named these as leads to verify; discovery instead surfaced CIM Market and La Corniche Mali via general French search, which cleared the bar first. These four remain unchecked and are good candidates for a future pass if Mali's food count ever needs to grow past 2. |

## Depth-audit note

No commodity/COICOP-leaf depth audit was in scope this pass — Mali started at zero
sources, so density is "little or no coverage" (take whatever verifies, not gap-ranked).

## What's left to try (not exhausted, just not reached this pass)

- Retry `instat.gouv.ml`, `orange.ml`, `food.sodishop.com` — all three resolved but timed
  out in this session; none were confirmed genuinely dead (no NXDOMAIN, no clean
  connection refusal).
- Find EDM-SA's real domain (electricity tariff — the brief's other cheap non-food lead).
- Probe `mali-achats.com`'s seller directory (if any) rather than its own catalogue.
- Retry `ikasougou.com` with `chrome120` / `safari17_0` impersonation profiles.
- Check Azar Libre Service, Fourmi, Metro, and Grand Marché (named in the brief, never
  reached this pass) if the food count needs to grow beyond 2.
