# Namibia

_Inventory written: 2026-09-01_

Final F&B sweep, wave (2026-09), agent B. Cold-start (no prior inventory file
existed). Already-covered before this pass: 2 non-food sources (per the
sweep worklist), 0 food.

**Result: 0 sources shipped. No viable online grocery found.**

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Shoprite Namibia | https://www.shoprite.com.na | **DEAD — brochure/store-locator only** | Live Adobe AEM site (`shopriteafrica` clientlibs — the same pan-African corporate template used across the Shoprite Group's African markets), page title generic "Home". Only nav links are `/store-locator.html`; no shop/cart/product markup anywhere, no WooCommerce/Shopify/Magento fingerprint. |
| Checkers Namibia | https://www.checkers.com.na | **DEAD — brochure only, no e-commerce** | Same AEM template family (title "Checkers Namibia Home Page"). Has a `/world-of-checkers/liquorshop.html` page that reads like a real online liquor shop from its name, but the content is pure marketing copy ("Checkers offers a premium range of wines, beers, spirits...") with zero product listings, zero "add to cart", zero ordering flow. South Africa's Checkers Sixty60 rapid-delivery app does not extend to Namibia. |
| Metro Namibia | https://www.metro.com.na | **DEAD — brochure only** | Title "Metro Namibia – A Brand you can trust"; no shop link, no add-to-cart anywhere on the page. |
| Woolworths, Food Lovers Market, Fruit & Veg City (Namibia) | (no domains found) | **NOT PROBED — no resolvable domain** | `woolworths.com.na`, `foodlovers.com.na`, `fruitandveg.com.na` all NXDOMAIN. |
| SPAR Namibia, Pupkewitz | https://www.spar.co.na (timeout), https://www.pupkewitz.com.na (timeout) | **NOT PROBED — unreachable this pass** | Both connection-timed-out on a single curl_cffi attempt (15s); not re-tried with a longer timeout or a second impersonation profile. Worth a re-check, not confirmed dead. |

Namibia is served almost entirely by South African-headquartered chains
(Shoprite Group, SPAR Group) whose pan-African corporate sites are
brochure/store-locator templates with no online ordering for this market —
consistent with the same finding for Eswatini in this same pass (identical
Shoprite AEM template, same "Home" title). No delivery marketplace
(Jumia/Glovo/Bolt/Yango-style) operates in Namibia. This reads as a
**structural absence of online grocery** for the market rather than a
search gap, though `spar.co.na` and `pupkewitz.com.na` timing out (not
confirmed dead) are loose threads worth a fast re-check.
