# Somalia

_Inventory written: 2026-09-01_

Final F&B sweep, wave (2026-09), agent B. Cold-start (no prior inventory file
existed). Already-covered before this pass: `wfp_prices` (official_avg,
shared SSA fetcher) — 1 source / 0 food, no retail coverage.

**Result: 1 source shipped (adeeg_so, hypermarket).**

| Candidate | URL | Channel / role | Status | Notes |
|---|---|---|---|
| Adeeg.com | https://adeeg.com | `hypermarket`, retailer_sku | **SHIPPED** as `adeeg_so` | Hayat Market's official e-commerce platform (Mogadishu). Vanilla Shopify storefront — `/products.json?limit=250&page=N` confirmed live, empties at page 17 (~3,777 products across 16 full pages + a 27-item tail). Shopify.currency reports `{"active":"USD"}` — priced in USD, not the countries.yaml default SOS; read off the page. Big-box catalogue: groceries (baby food/milk, dairy & cheese, spices, canned foods, bakery, butchery, breakfast cereals, chips/snacks) cross-sold with general merchandise (electronics, baby gear, books, cameras, belts/caps) — rough keyword-based food-share estimate ~37-40% of rows, hence `channel: hypermarket` not `supermarket`. Used the shared `_shopify_base.ShopifyBaseSpider` unmodified. |
| Hayat Market (own domain) | https://hayatmarket.com | — | **REJECTED — duplicate/non-functional storefront** | Same brand as Adeeg.com. `wp-json/` namespace list has no `wc/*` (WooCommerce) route registered and `/shop/` 404s — this is a WordPress/Newfold marketing site, not a working e-commerce surface. Do not onboard as a second source for the same operator. |
| Aaran Hypermarket | https://www.aaranonline.com | would be `hypermarket` | **PROBED, DEAD (empty product grid)** | Real Odoo (`website_sale`) storefront — confirmed via `data-main-object="product.public.category(...)"` and genuine category taxonomy (Grocery, Fresh Food, Electronics & Appliances, Life Style & More). But every category's `<div class="o_wsale_products_grid_table_wrapper">` (including the top-level `/shop` "all products" view) rendered **completely empty**, both via curl_cffi and a full Playwright render with `networkidle` — no product cards, no AJAX call to a products endpoint observed in the network trace. Fails the >=5-rows gate outright (0 rows). Hypothesis: either the storefront's default pricelist/currency-selection cookie gates the grid server-side (Odoo `website_sale` sometimes requires a resolved pricelist before rendering), or the catalog is genuinely unpublished/empty behind a live-looking category nav. Worth a re-check with an explicit currency/country cookie set, or a full session warm-up through the homepage first, but do not re-probe casually — it already consumed a full Tier-2 (Playwright) escalation with no signal. |
| SafewaySupermarket | https://safewaysupermarket.com | — | **DEAD — expired domain** | Page returns "Your domain is expired" parking template. |
| Hiiliye | https://hiiliye.com | — | **SKIPPED — app-only marketing SPA** | React/Vite single-page marketing site for a delivery app ("one app for supermarket, food, gas, and suuq deliveries"); no web catalog, no API sniffed on the marketing page itself. Would need the mobile app's API reverse-engineered — out of scope for this pass. |
| Somali Stores / somalistores.com | https://somalistores.com | — | **NOT PROBED — 403 on first touch** | curl_cffi impersonate=chrome124 returned a bare 403 on the homepage; not re-probed with chrome120/safari17_0 this pass (time-boxed). Re-probe before writing off — per onboarding rule 9, a single impersonation profile's 403 is not sufficient evidence of a real block. |

## COICOP / channel coverage after this pass

Somalia: 2 sources / 1 food — `adeeg_so` (hypermarket, retailer_sku, COICOP
01/02 plus general merchandise) + pre-existing `wfp_prices` (official_avg).
Everything outside food/general-merchandise-carried-by-adeeg remains
uncovered at the retail level (housing, utilities, health beyond what
adeeg's small pharmacy-adjacent categories carry, transport, communication,
recreation, education, restaurants, insurance — COICOP 03-13 mostly ex-01).
Next-pass leads in cheapest-first order: (1) re-probe `somalistores.com`
with `chrome120`/`safari17_0` before writing it off, (2) re-check Aaran
Hypermarket's empty grid with a warm session/explicit pricelist cookie —
real second grocery source if it renders, (3) Hiiliye's mobile-app API if a
network trace can be captured from the app itself (out of scope for a
web-only pass).
