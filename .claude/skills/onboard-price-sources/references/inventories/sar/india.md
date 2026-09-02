# India

_Inventory written: 2026-09-01_

Final F&B sweep (SAR agent A). Baseline: 2 food sources (dmart_in
hypermarket, starquik supermarket). Goal was breadth of retailer type, not
another supermarket/hypermarket. Result: **2 built**, both specialty-food,
distinct from each other and from the existing hypermarket/supermarket
coverage — freshtohome_in (meat/seafood/eggs) and happilo_in (dry
fruits/nuts/seeds/snacks).

| Source name | URL | Channel | Source type | Cadence | Auth required? | Machine-readable? | Anti-bot risk | Per-SKU IDs? | Notes |
|---|---|---|---|---|---|---|---|---|---|
| FreshToHome (BUILT: `freshtohome_in`) | https://www.freshtohome.com/ | specialty-food | Meat/seafood/egg D2C delivery | Weekly | No | Yes (JSON-LD on PDP) | Low — 200 on curl_cffi chrome124, no WAF | Yes (sku in JSON-LD) | Magento-family storefront. Category listings are per delivery city; Bangalore alone lists 425 PDP hrefs on one unpaginated page. PDP price is ONLY in a schema.org Product JSON-LD block (no data-price-amount, no og:price). Verified 425/425 rows, 100% INR, food share 100%. |
| Happilo (BUILT: `happilo_in`) | https://www.happilo.com/ | specialty-food | Dry fruits/nuts/seeds/snacks D2C | Weekly | No | Yes (`/products.json`) | Low — Shopify, open endpoint | Yes | Shopify storefront via shared `_shopify_base`. Found and fixed a shared-base bug locally (subclass override only): `_items()`'s `if not price` guard does not catch the string "0.00"; 8/181 raw variants priced at 0 and are now filtered. Verified 173/173 rows after fix, 100% INR, food share 100%. |
| BigBasket / Blinkit / Zepto / Swiggy Instamart / JioMart | (market leaders) | — | Quick-commerce grocery marketplaces | — | — | — | Not probed — inverse-correlation law (market leaders are WAF-hardened; probe budget spent on FreshToHome/Happilo instead) | — | Not investigated this pass. Candidate for a dedicated anti-bot effort, not a routine sweep. |
| Nature's Basket | https://www.naturesbasket.co.in/ | supermarket (gourmet) | — | — | — | — | 403 on curl_cffi chrome124, chrome120, AND safari17_0 | — | Real WAF (all three TLS fingerprints failed). DEAD for this pass. |
| Milkbasket | https://www.milkbasket.com/ | convenience (dairy/daily subscription) | — | — | — | — | 403 on curl_cffi chrome124, chrome120, AND safari17_0 | — | Real WAF (all three TLS fingerprints failed). DEAD for this pass. |
| Country Delight | https://www.countrydelight.in/ | specialty-food (dairy subscription) | — | — | — | — | 200 on TLS but Angular SPA; `websiteapi.countrydelight.in` API returns 403/404 on unauthenticated probes, no pincode/session established | — | Needs deeper session/pincode reverse-engineering than the timebox allowed. Not a confirmed dead end — worth a re-probe with a proper pincode cookie flow. |
| bbdaily.com (BigBasket subsidiary) | https://www.bbdaily.com/ | — | Daily milk delivery | — | — | No | — | — | App-only — landing page is pure marketing ("Buy or subscribe now on bbdaily... through the app"), no web catalogue. DEAD, and same operator as BigBasket regardless. |
| Otipy | https://www.otipy.com/ | fresh-market (farm-to-table) | — | — | — | — | Connection timeout on curl_cffi chrome124 | — | Unreachable in the timebox. Not confirmed as WAF vs. down — worth a re-check. |
| 24Seven (convenience chain) | https://www.24seven.co.in/ | convenience | — | — | — | — | Connection timeout on curl_cffi chrome124 | — | Unreachable in the timebox. |
