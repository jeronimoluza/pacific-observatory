# United Arab Emirates — price source inventory (menaap/gulf_states)

_Inventory written: 2026-09-01_

Cold-start inventory (menaap region had no prior inventory file). UAE started
this pass at 7 sources / 0 food-and-beverage sources; the workbook's only UAE
row (Amazon UAE) is a general marketplace and does not count as food.

## Onboarded this pass

| Source | Channel | Platform | Notes |
|---|---|---|---|
| `lulu_ae` | hypermarket | Akinon (shared GCC `gcc.luluhypermarket.com/en-ae`) | Sibling of lulu_kw/om/bh/sa. This locale's PDP no longer server-renders a price span (newer frontend build); price comes from the JSON-LD `offers.price`/`priceCurrency`, which — unlike the sibling locales — is genuinely populated for in-stock items (only OOS SKUs fall back to the "0.00"/null stub the siblings always show). 203-row sample: 31.0% food (Grocery + Fresh Food breadcrumbs). |
| `choithrams_ae` | supermarket | Bespoke JSON API (`/api/websf/`) behind an Angular SPA shell | Found via Playwright network-capture on the (non-WAF'd) homepage; same-origin API answers plain curl_cffi with no auth. Full unbounded catalog walk: 10,516 rows, 70.9% food by category. |

## Candidates probed and rejected

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| Carrefour UAE | carrefouruae.com | DEAD (pre-existing, re-confirmed) | Already in `known_blockers.md` — Akamai, one MAF Gulf tenant covering carrefourqatar.com/carrefourksa.com/carrefouruae.com. Not re-probed beyond a curl_cffi 403 re-check. |
| Spinneys | spinneys.com/en-ae | DEAD | Azure Application Gateway, HTTP 403 on curl_cffi (3 impersonations) AND headless Playwright. See `known_blockers.md` → Azure Front Door WAF. |
| Union Coop | unioncoop.ae | DEAD | Fastly edge synthetic 405 "Not allowed" on every path/method/UA, curl_cffi AND Playwright. See `known_blockers.md` → new "Fastly synthetic 405" section. |
| Kibsons | kibsons.com | PARKED | Next.js app-router `[locate]` dynamic route — grocery-delivery platform gated on a delivery-location/area selection before any product or price data loads. Homepage alone is 3.2MB with no embedded catalog. Would need a Playwright session that completes area selection; not attempted this pass (budget). Worth revisiting as a dedicated Playwright effort — genuine UAE grocery delivery catalog. |
| Ansar Gallery | ansargallery.com | REJECTED-FOR-LOCALITY | Site's own i18n copy says "We only serve Qatar, Oman, Bahrain." (UAE conspicuously absent despite the key name `weOnlyServeQatarOmanBahrainUae`); `/ae` and `/en-ae` paths both 404. Not a UAE source. |
| Day to Day (daytodayuae.com) | daytodayuae.com | No online store | WordPress/WooCommerce plugin present but no `wc/store/v1` or `wc/v3` REST namespace exposed, no `/shop` link anywhere on the site — brochure site for a physical-store chain, not an e-commerce catalog. |
| Zoom Grocery | zoomgrocery.com | DEAD | Domain resolves but serves a 114-byte stub; effectively no live site. |
| Organic Foods & Cafe | organicfoodsandcafe.com | Not Shopify (false positive) | `/products.json` returns the Next.js SPA shell HTML, not a Shopify Storefront JSON response — this domain is not actually a Shopify store despite the path matching. |
| Noon Minutes / Noon Daily | noon.com/uae-en/now-uae/ | Not probed further | 404 on the guessed path this pass; noon.com is itself a large marketplace (would need its seller directory, not its own catalog, per the marketplace-is-a-directory rule) — not chased given lulu_ae/choithrams_ae already closed the food gap. |
| Talabat Mart | talabat.com/uae | Not probed further | Delivery-aggregator storefront (marketplace channel, would not count toward the food-source bar per this wave's rules even if built) — deprioritized once 2 genuine grocery retailers were secured. |

## Dead ends worth remembering

- Any UAE grocery lead that turns out to be a Next.js **app-router `[locate]`** or similar dynamic-location route (Kibsons, Talabat, Noon Minutes) should be assumed to gate price/stock behind a resolved delivery area — plan for a Playwright session that completes area selection, not a plain curl_cffi probe.
- Not every "GCC shared storefront" locale behaves like its siblings: `gcc.luluhypermarket.com`'s en-ae locale silently swapped its price-rendering mechanism (HTML span → JSON-LD) relative to en-kw/en-om/en-bh/en-sa. Check the JSON-LD directly before assuming a sibling's spider logic ports unchanged.
