# Grenada

_Inventory written: 2026-09-01_

Final F&B sweep, lac-agent-A. Cold start — no `lac/` inventory existed for Grenada
before this file. Before this pass: 0 sources total, 0 food. Marketplace-first
discovery (no fresh per-country WebSearch beyond two frugal calls — the CaribeEats
platform's own `/api/init` region list did most of the work) surfaced the CaribeEats
delivery aggregator (backend.caribeeats.com) as the highest-yield generator, since it
also covers St Kitts, Nevis, and Dominica from my worklist (see those countries'
inventory files).

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| CaribeShop GND | https://backend.caribeeats.com/api/business/caribeshop--gnd | supermarket | **SHIPPED** as `caribeshop_gnd` | See config YAML notes for full detail. 1180 SKUs / 39 categories, food-led (~65% food/beverage by product count). Discovered via CaribeEats' `/api/businesses?service_id=groceries&region_id=grenada&lat=<lat>` endpoint, which requires a Playwright context with `geolocation` permission granted (the consumer web app gates the *business directory* behind a location prompt) — the per-business detail endpoint itself (`/api/business/<slug>`) is plain unauthenticated JSON, no Playwright needed at collection time. |
| Real Value Supermarket Grenada (CaribeEats listing) | https://backend.caribeeats.com/api/business/real-value-supermarket-grenada | — | **DEAD — personalized-shopping proxy, no catalog** | `categories: []`. Disclaimer explains a human shopper buys items on your behalf and bills you after — not a fixed-price catalog. |
| shop.realvalueiga.com | https://shop.realvalueiga.com/ | — | **PARKED — LocalExpress address-gate** | Same operator as above, different (native storefront) platform. See `known_blockers.md` § "API requires dynamic security key / JWT". |
| RAMS Grenada (CaribeEats listing) | https://backend.caribeeats.com/api/business/rams-grenada | — | **DEAD — empty catalog** | `categories: []`, 0 products. |
| De Fish Market (CaribeEats listing) | https://backend.caribeeats.com/api/business/de-fish-market | fresh-market | **NOT PURSUED — too narrow, deprioritized** | 1 category ("Yellowfin Tuna"), a handful of SKUs at most. CaribeShop GND's much larger catalog covers the gap; revisit only if CaribeShop GND is ever lost. |
| Mount Pure Mineral Water (CaribeEats listing) | https://backend.caribeeats.com/api/business/mount-pure-mineral-water | — | **NOT PURSUED — too narrow, deprioritized** | 1 category ("Water"). Same reasoning as De Fish Market. |
| Grenada Brewery (CaribeEats listing) | https://backend.caribeeats.com/api/business/grenada-brewery | specialty-food | **NOT PURSUED — time budget** | 4 categories (Water, Alcoholic x2, Non-alcoholic), narrow beverage-distributor catalog. Would be a legitimate small COICOP-02/01.2.2 source for a future pass; not shipped this wave in favour of CaribeShop GND's broader catalog. |
| grenadagrocer.com | https://grenadagrocer.com/ | — | **DEAD — demo/seed WooCommerce install** | See `known_blockers.md` § "Placeholder / seed demo-data catalog". |
| caribeeats.com CaribeShop (general marketplace catalog view) | https://caribeeats.com/biz/caribeshop--gnd | — | superseded by direct API | The consumer web page for this same business; the API route above is the actual scraping target, no need to render the SPA. |
| caridoor.com | https://www.caridoor.com/ | — | **NOT INVESTIGATED FURTHER — time budget** | WooCommerce (Woodmart theme), framed as Caribbean-groceries-shipped-from-abroad ("The Caribbean at Your Door") — likely a US-diaspora shipping service rather than an in-Grenada retailer; not confirmed either way. Worth a follow-up probe if Grenada needs a second F&B source. |

## COICOP / channel gap after this pass

Grenada ends at **1 source / 1 food** (`caribeshop_gnd`, supermarket, food-led general
catalogue). Division 02 (alcohol/tobacco) is present within CaribeShop's minority
categories but not as a dedicated source — Grenada Brewery (above) is the natural next
candidate. Division 06 (pharmacy) is present within CaribeShop's Personal
Care/OTC-meds categories only. No `cpi_benchmark`, `official_avg`, `tariff`, or
`real-estate` coverage exists for Grenada yet — untried this pass (F&B-scoped sweep).

Next agent: Grenada Brewery and De Fish Market (both listed above, both narrow but
real) are ready-made candidates using the identical `_caribeeats_base.py` shared
spider — just a new `SLUG` and a channel/coicop_codes decision, no new scaffolding
needed.
