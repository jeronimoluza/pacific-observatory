# Mozambique

_Inventory written: 2026-09-01_

Wave 7 pass. Already-covered before this pass: `bazara_mz` (marketplace), `recheio_mz`
(hypermarket), `vipspar_mz` (supermarket), `wfp_prices` (official_avg) — 4 sources / 2 food.
This pass needed 1 more source of any channel; target was >=5 sources AND >=2 food.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| TaAqui Delivery | https://www.taaqui.co.mz/ | marketplace | **SHIPPED** as `taaqui_mz` | Next.js app; catalogue is genuinely behind the API as the workbook warned, but the backing host `central.taaqui.co.mz` has a no-auth single-item endpoint `GET /api/v1/items/details/<id>` (most other routes need `zoneId`/`moduleId`/`latitude`/`longitude` custom headers). Sequential integer ids; range walk 1-360 found the whole live catalogue. 188 items verified live 2026-09-01 (188 distinct product_id, 188 distinct url, 0 zero/blank rows, 100% MZN, price range 20-4120, median 529). **Not food**: the platform's "grocery" module (module_id=1) is actually a houseplant nursery + a tobacco/apparel shop, not groceries; the bulk of real content is 7 Maputo restaurants' menus (module_id=2, "food" = food-away-from-home, not retail) plus a small footwear/apparel slice. Scaffolded honestly as `channel: marketplace`, which does not count toward the food bar. |
| Casa Bhay Supermercado | http://krolyc.co.mz/ | — | **DEAD — Cloudflare challenge** | Domain doesn't match the brand name (workbook flagged this). `curl_cffi` 403 across chrome124/chrome120/safari17_0/chrome99; headless Playwright confirms a real Turnstile "Just a moment..." challenge, not a TLS false positive. See `known_blockers.md` § Cloudflare strict. |
| Shoprite Mozambique | https://www.shoprite.co.mz/ | — | **DEAD — no online store** | Same pan-African AEM `shopriteafrica` corporate-portal tenant already logged dead for Ghana (`shoprite.com.gh`) and other markets — sitemap is entirely recipes/offers/store-locator, `/ofertas.html` has no per-product prices, guessed catalog paths all 404. |
| Mambo Store | https://mambostore.com/ | — | **DEAD — parked domain** | HugeDomains for-sale page, not a live retailer. `mambostore.co.mz` doesn't resolve. |
| Pingo Doce / Premier, Kaya Delivery, Deskoncerto, Farmacia Calendula | (various `.co.mz` guesses) | — | **NOT REACHABLE — no working domain found** | `www.pingodoce.co.mz`, `www.premier.co.mz`, `premier.co.mz`, `www.premiersupermercado.co.mz`, `kaya.co.mz`, `www.kaya.co.mz`, `kayadelivery.co.mz`, `deskoncerto.co.mz`, `www.deskoncerto.com`, `www.calendula.co.mz`, `www.farmacalendula.co.mz`, `farmaciacalendula.co.mz` all NXDOMAIN. Not spending WebSearch budget hunting the correct domain given the "any channel" bar was already cleared by TaAqui — worth a named-search pass (not a generic sweep) in a future run if Mozambique needs COICOP-gap-driven food sources specifically (Pingo Doce/Premier is the most food-relevant of this group and worth a real search first). |

## COICOP / channel gap after this pass

Mozambique ends at 5 sources / 2 food (existing `recheio_mz` hypermarket + `vipspar_mz`
supermarket). The new source (TaAqui) is `marketplace` and does not add food-channel
coverage — its real content (restaurant meals, plants, tobacco, footwear) mostly falls
outside COICOP-01 retail grocery anyway. A genuine food-coverage lift for Mozambique
would need a real hit on the Pingo Doce/Premier lead above, or a fresh discovery pass
(Mozambique has no populated marketplace-directory or wholesale-feed candidates found
this round).
