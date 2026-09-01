# Lesotho

_Inventory written: 2026-09-01_

Wave 8 pass. Already-covered before this pass: `virtualmall_ls` (supermarket),
`wizashopping_ls` (marketplace), `wfp_prices` (official_avg) — 3 sources / 1 food.
This pass needed 2 more sources, at least 1 food, to reach the >=5 sources /
>=2 food bar.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| BiteLiqour (on LocalBites) | https://store.localbites.co.ls/stores/biteliqour | specialty-food | **SHIPPED** as `bite_liqour_ls` | Single first-party bottle/liquor store hosted on the LocalBites food-delivery platform (merchant-on-aggregator pattern, same as `*_wolt_*`/`chawshin_lezzoo_iq`). First cut shipped only 24 of 66 rows (Next.js SSR page-1 cap, correctly flagged by the orchestrator as a failure signature). Fixed by finding the real client-side paginated JSON API (`api.localbites.co.ls/api/delivery-zone/products?store=biteliqour&page=&per_page=&latitude=&longitude=`, requires `Accept: application/json` or it silently serves the HTML SPA shell instead of erroring) buried in the frontend JS bundle. 62 rows verified live (62 distinct product_id/url, 0 blank/zero-price, 100% LSL, median M155, range M17-747) -- the remaining 4 of 66 catalog rows are genuinely unpriced on the retailer's own site (null price and special_price), not a scraping miss. |
| LocalBites (marketplace, 13 non-liquor stores) | https://store.localbites.co.ls/ | marketplace | **SHIPPED** as `localbites_ls` | Workbook candidate "LocalBites Lesotho" — ACCEPT verdict, groceries flagged 'coming soon' at survey time. Re-verified 2026-09-01: groceries is STILL not live (`/categories/groceries` etc. all resolve 200 "No Products found"). The 14-merchant directory (`api.localbites.co.ls/api/stores`, open JSON) is 13 restaurants/QSR chains (Barcelos, Debonairs, Foso Foods, Golden City Palace, Highlands Bliss, Hungry Lion, KFC, Lecholi Family Restaurant, Purple Coffee, Stadium Fast Foods, Steers, Trout Fish Market, Boba Heaven) plus BiteLiqour (shipped separately). "Trout Fish Market" reads like a fresh-fish grocer by name but sells prepared fish-and-chips meals, not fresh fish — not a fresh-market. None are supermarkets, so this is honestly `channel: marketplace` (COICOP 11 restaurant coverage), does NOT count toward the food bar. 152 rows verified live (152 distinct product_id/url, 0 blank/zero-price, 100% LSL, median M72, range M7-600) across 13 stores, each capped at its own SSR page-1 (same limitation as BiteLiqour). |
| Pick n Pay Lesotho | https://www.pnp.co.ls/ | — | **DEAD — no DNS** | Both `www.pnp.co.ls` and `pnp.co.ls` are NXDOMAIN under `curl_cffi impersonate=chrome124` (no TLS handshake even starts). Not a redirect-to-SA-parent case — the domain simply doesn't resolve. |
| Shoprite Lesotho | https://www.shoprite.co.ls/ | — | **DEAD — no online store** | Resolves natively (not a redirect to the SA parent; genuine `/ls/en/` AEM path) but is the same pan-African `shopriteafrica` corporate-portal tenant already dead for Mozambique/Ghana: nav is category-description pages, store-locator, and a promo page with no per-product prices and no catalog PDF. No `/shop`/`/products`/`/catalogo` path exists. |
| Choppies | https://www.choppies.co.bw/ (guessed .co.ls variants all NXDOMAIN) | — | **NOT REACHABLE** | Botswana-headquartered chain operates in Lesotho per general knowledge, but no Lesotho-specific domain found (`choppies.co.ls`, `www.choppies.co.ls` both NXDOMAIN); the .co.bw site is Botswana's own storefront/pricing and out of scope (wrong country). Not pursued further. |
| Econo Foods Maseru | shop.econofoods.co.za (SA parent domain); listed on Pricemate at `pricemate.info/shops/@econofoodsmaseru` | wholesale | **DEAD — zero products listed** | Real Maseru branch (Main North 1 Road) confirmed via WebSearch + the Pricemate listing (country=Lesotho, currency=Loti, category "Groceries & Household"), but Pricemate's own API returns `total_published_products: 0` for this shop (`GET api.pricemate.info/api/products?shop_id=6` → empty). The SA `shop.econofoods.co.za` storefront is the group's own domain, not Lesotho-specific pricing — did not pursue given the empty Pricemate listing already answers "no live catalogue for this branch." |
| Pricemate (pricemate.info) | https://pricemate.info/ | — | **PARKED — platform found, no populated Lesotho shop yet** | A genuine multi-country (Lesotho/Botswana/South Africa) shop-price-comparison app with per-shop pages SSR'd via Nuxt and a `api.pricemate.info` JSON backend. The one Lesotho shop found (Econofoods Maseru) has zero products. The shop directory endpoint (`/api/shops`) requires auth, so there is no way found this pass to enumerate OTHER Lesotho shops that might have real listings. Worth a future re-check — if a second Lesotho shop with populated products turns up, this could be a good `retailer_sku` or `marketplace` source. |
| Mpeoa Supermarket, Furong Supermarket | Facebook pages only | — | **NOT REACHABLE — no website** | Real Maseru supermarkets per WebSearch, but no scrapable web presence (Facebook-only). |
| Spar Lesotho, OK Foods Lesotho, Metro Lesotho, Food Lovers Lesotho | `.co.ls` guesses | — | **NOT REACHABLE** | All guessed domains (`spar.co.ls`, `okfoods.co.ls`, `metro.co.ls`, `foodlovers.co.ls`/`food-lovers.co.ls`) are NXDOMAIN. Not pursued via WebSearch given budget — worth a named search in a future pass if Lesotho needs more food-channel depth. |

## COICOP / channel gap after this pass

Lesotho ends at 5 sources / 2 food (`virtualmall_ls` supermarket +
`bite_liqour_ls` specialty-food). `localbites_ls` (marketplace) adds real
COICOP-11 (restaurants) coverage but does not count toward the food-retail
bar. Lesotho's genuine online-grocery market is thin: both franchise
candidates (PnP, Shoprite) are dead, LocalBites' own groceries module still
hasn't shipped, and no independent Lesotho supermarket e-commerce site was
found despite 43 physical grocery stores existing in Maseru per directory
listings — almost all are Facebook-only or have no web presence at all. A
future pass chasing more food depth should: (1) re-check LocalBites'
groceries category periodically (workbook already flagged it as pending
once), (2) re-check whether Pricemate populates products for a second
Lesotho shop, (3) try a named search for Spar/OK Foods/Food Lovers Lesotho
franchise sites rather than guessed domains.
