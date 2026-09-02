# Syria — price source inventory (menaap/middle_east)

_Inventory written: 2026-09-01_

Cold-start inventory (menaap region only had west_bank_and_gaza/united_arab_emirates/afghanistan/libya/morocco prior to this pass). Syria started this pass at 0 food-and-beverage sources (`tsaooq_sy` is a general marketplace scoped to a thin 4-item food category; `wfp_prices` is `channel: null` official_avg, not a retailer).

Syria's online grocery ecosystem is dominated by app-only delivery platforms (Movo, BeeOrder, Target Market, Savy/MySave, Moovmart, SarieApp) — none expose a browsable web catalogue; all are marketing landing pages funneling to native iOS/Android apps. The one genuine web-scrapable win found is a diaspora-facing gift/remittance platform with a real grocery category.

## Onboarded this pass

| Source | Channel | Platform | Notes |
|---|---|---|---|
| `dokan_sy` | marketplace | Custom Laravel "AIZ"-template storefront (same template as `souqmy_ye`), `/search2` JSON listing endpoint | Diaspora gift/remittance site ("your bridge to your loved ones in Syria") — top-ups, Sham Cash transfers, flowers, sweets, electronics — SCOPED to `categories[]=66` ("market dukkan" / groceries). 254 rows, 0 blank names, 0 zero/negative prices, 100% USD (diaspora-paid, not SYP). Cold-refetched 2/2 products, both matched live. |

## Candidates probed and rejected

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| BeeOrder | beeorder.com | APP-ONLY | Static marketing landing page, zero internal shop paths. See `known_blockers.md`. |
| Movo | movo.delivery | APP-ONLY | Every route serves the identical static Bootstrap landing page; no app bundle at all. |
| Target Market | (no website) | APP-ONLY | Only Google Play / App Store / Instagram listings exist — no website. |
| Savy Market / MySave | savy.market | APP-ONLY | WordPress with `wp-json` exposed but NO WooCommerce namespace registered; only a Google Play badge for `shop.mysave.customer`. |
| Moov Mart | moovmart.com | APP-ONLY (thin) | Next.js `pages/index` chunk is 2.2KB with zero API/app-store references — barely-built landing page. |
| Syria Market | syriaamarket.com | REJECTED — wrong country | Real Shopify store, real Syrian-brand-food catalog, but `Shopify.country="EG"` / `Shopify.currency.active="EGP"` — Egypt-based diaspora shop, not Syria-resident. Locality trap. |
| Namlieh Market | namliehmarket.com | DEAD — NXDOMAIN | Does not resolve. |
| SarieApp | (Google Play only) | APP-ONLY | Aleppo-only food delivery app per search snippet; no website found. |

## Dead ends worth remembering

- **This market skipped the web entirely and went straight to native apps.** Every genuine Syrian grocery-delivery brand found this pass (Movo, BeeOrder, Savy, Moovmart, Target Market, SarieApp) is app-only — likely driven by payment-rail constraints (sanctions/banking) that make an app + informal payment flow easier than a card-based web checkout. Don't expect a web catalogue from a Syrian grocery-delivery brand without checking for one explicitly first.
- **"Syria"-branded shops found via search are frequently diaspora businesses in a different country** (syriaamarket.com → Egypt). Always check `Shopify.country`/`Shopify.currency` (or the equivalent platform signal) before building, even when the brand name and product catalog look completely native.
- **The winning pattern here was a "gift for family back home" site, not a grocery-delivery app.** `dokan.sy` isn't marketed as a supermarket at all (it's a top-up/gift-delivery service for the diaspora) but has a real, paginated grocery category — worth checking this category of site (money-transfer + gift-delivery hybrids) for other sanctioned/conflict markets where normal e-commerce is thin.
- **The "AIZ" Laravel marketplace template (`/search2` AJAX endpoint, `aiz-card-box` markup, `showAddToCartModal(<id>)`) is now confirmed on two unrelated MENAAP sites** (`souqmy_ye`, `dokan_sy`) — worth fingerprinting explicitly in future MENA discovery passes.
