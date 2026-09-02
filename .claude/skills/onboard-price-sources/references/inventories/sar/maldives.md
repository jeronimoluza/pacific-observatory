# Maldives

_Inventory written: 2026-09-01_

Scope note: this is a **food-and-beverage-focused seed**, not a full 13-division sweep — written from a depth pass targeting new F&B retail (division 01/02) sources only, per the SAR agent-B wave. WebSearch budget was exhausted mid-pass (session-wide cap shared across 12 parallel agents); remaining candidates below were found via WebFetch on already-known URLs and direct `curl_cffi` domain probing, not fresh search.

Already onboarded before this pass: good_food_mv (supermarket, Shopify, organic/natural), littlefino_mv (supermarket), whim_mv (supermarket, Odoo), redwave_mv (pharmacy, WooCommerce). Shipped this pass: **blackgoldfoods_mv** (specialty-food).

| Source name | URL | Channel / role | Machine-readable? | Notes |
|---|---|---|---|---|
| Blackgold Foods | https://blackgoldfoods.mv/ | specialty-food, retailer_sku | Shopify `/products.json`, open | **SHIPPED 2026-09-01** as `blackgoldfoods_mv`. Imported UK/AU gourmet pantry/snacks/frozen. 851 rows, MVR, ~94.5% food share. See manifest for detail. |
| Mu Express | https://www.muexpress.mv/ | supermarket (general), retailer_sku | Odoo `/shop/category/...`, server-rendered | Reachable, large general-grocery catalog (appliances/baby/bakery/appliances too) — same shape as existing whim_mv (Odoo). **Not onboarded this pass**: deprioritized in favour of retailer-type breadth per the wave brief (would be a 4th/5th supermarket-shaped source). Good candidate for a future depth-only pass if supermarket SKU count becomes the bottleneck. |
| EAT.mv | https://eat.mv/ | supermarket, retailer_sku | Unknown (blocked) | Plain Apache 403 on `curl_cffi` chrome124/chrome120/safari17_0 — no Cloudflare/challenge markers, reads as an application-tier/geo allowlist. See `known_blockers.md` (Country-wide IP-fence cohort, Maldives). Re-probe from an MV residential IP. |
| DhiGrab | https://www.dhigrab.mv/ | marketplace (mostly restaurant) | Store directory server-renders names+counts; per-store product data behind Firestore realtime `Listen` channel, no static endpoint | ~120 partner stores, overwhelmingly restaurants/cafes. Grocery-shaped stores exist (Nokron Mart, West End Mart, Meat Street) but are thin (18-114 items each) and each needs its own Firestore query / click-through. Not pursued this pass — see `known_blockers.md`. |
| Seagull Foods | https://foods.seagullmaldives.com/ | fresh-market (fresh produce importer), retailer_sku | Shopify, but `/products.json` 401s | Password-protected / pre-launch storefront. Dead end this pass. |
| GannaMart | https://gannamart.com/ | supermarket, retailer_sku | App-only | Static "coming soon"-style landing page, no web catalog. `gannamart.mv` does not resolve. Dead end. |
| Foodies | https://foodies.mv/ | restaurant delivery (not F&B retail) | App-only | Restaurant/home-cook delivery marketplace, wrong COICOP division (11, not 01/02). Dead end for this skill's scope. |
| maldiviancart.com | — | unknown | — | Domain does not resolve (NXDOMAIN). Dead — was listed in a 2026 blog roundup of MV grocery delivery services but appears to have lapsed. |
| STO eSTOre | https://storate.sto.mv/ | supermarket (state trading org), retailer_sku | Not probed | State Trading Organization's online supermarket arm — large national chain. Not probed this pass (deprioritized: would be another supermarket-type source, and existing 3-4 supermarkets already cover Maldives; revisit only if supermarket depth becomes the ask). |

## Currency note

Maldives (MVR) sources verified this pass: Blackgold Foods confirms `Shopify.currency active=MVR` and `priceCurrency` meta = MVR on PDPs — matches `countries.yaml`. No minor-unit or symbol-inference traps found.
