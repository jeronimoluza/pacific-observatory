# Chad

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
