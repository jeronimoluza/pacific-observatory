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

## Update — 2026-09-11

Re-probed the priority-chain list from the onboarding brief (Shoprite,
Checkers, USave, SPAR, Pick n Pay, Woolworths, Choppies, OK Foods Namibia).
**All re-confirmed dead/unreachable or not found** — see
`references/known_blockers.md` (Namibia section) for the per-domain evidence.
Net new finding: "OK Foods Namibia" is the Shoprite Group's own AEM brand
template (`okfoods.co.za/na/en_NA/`), not an independently Namibian-founded
chain. spar.co.na and pupkewitz.com.na are now confirmed unreachable across
2 independent sessions (connection timeout on 5 different client profiles
total, not a TLS/WAF signature).

**This pass shipped sources anyway — via two paths the chain-domain-guessing
search never reaches:**

1. Live web search past the chain-name-guessing pattern surfaced three real,
   independent Namibian retailers with no predictable domain pattern:
   - `shop.woermannfresh.com` — Woermann Brock supermarket, ~22,700-SKU
     whole-catalog sitemap walk. **By far the largest single addition
     possible for this country** (prior corpus: 18 distinct product names
     total). Channel: supermarket. Shipped as `woermannfresh_na`.
   - `meat-namibia.com` — Buschmann Meat Packers butcher/meat-box delivery,
     WooCommerce Store API (non-standard `/wc/store/products`, no `/v1/`).
     5-SKU genuinely-complete catalog. Channel: fresh-market. Shipped as
     `meat_namibia_na`.
   - `embassyliquorstore.com` — Windhoek liquor store, Wix Stores, JSON-LD
     PDPs. First division-02 (alcohol) source for Namibia. Channel:
     specialty-food. Shipped as `embassyliquor_na`.
2. The national statistics office, nsa.org.na — not a retailer at all, but
   its monthly CPI Excel workbook carries both a COICOP-labelled division
   index series (Tab 6, full 2002-present history in one file) and a genuine
   zonal average-RETAIL-price table for ~15 food items (Table 14, current
   month only, NAD). Shipped as `na_nsa_cpi` (cpi_benchmark) and
   `na_nsa_zonal_food_prices` (official_avg).

Namibia is no longer "0 sources shipped" as of the 2026-09-01 write above —
5 new sources shipped this pass (3 retailer spiders + 2 NSA fetchers),
verified via `prices collect --source <key>` test runs.
