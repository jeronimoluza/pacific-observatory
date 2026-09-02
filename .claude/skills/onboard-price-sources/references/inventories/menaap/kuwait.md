# Kuwait — price source inventory (menaap/gulf_states)

_Inventory written: 2026-09-01_

Cold-start inventory. Kuwait started this pass at 2 food sources (`lulu_kw`, `taw9eel_kw`, both hypermarket) plus `jarir_kw`/`xcite_kw` (electronics).

## Onboarded this pass

| Source | Channel | Platform | Notes |
|---|---|---|---|
| `sinbadsupermarket_kw` | supermarket | Shopify, standard `/products.json` | Real online supermarket, 1,779-product catalog across Grocery/Biscuits/Candy/Chips/Chocolates/Coffee&Tea/Drinks/Frozen/Nuts/Pet-Food plus normal Cleaning/Household/Personal-Care departments. `Shopify.country="KW"`, currency KWD (3 decimals, confirmed from the page). 1,780 rows scraped, 0 blank names, 1 row at price 0.0 (out of 1780 — negligible, downstream drop expected), food-ish categories ≈56% by row count. Cold-refetched 2/2 products, both matched live. |

## Candidates probed and not yet completed (worth a follow-up pass)

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Salamarket (سوق سلة) | www.salamarketkw.com | NOT COMPLETED | 460KB homepage, Next.js. No `__NEXT_DATA__` script tag found (likely App Router) and no visible prices in raw HTML — would need a Playwright network trace. Not pursued given time budget after `sinbadsupermarket_kw` closed the food gap for this pass. |
| Arzaq Grocery | arzaqgrocery.store | NOT PROBED PAST HOMEPAGE | 38KB homepage, real Arabic-titled supermarket ("أرزاق - سوبر ماركت أونلاين في الكويت"). Not fingerprinted this pass. |
| eBaqala | ebaqala.com | NOT PROBED PAST HOMEPAGE | 110KB homepage ("eBaqala.com — Online Grocery & Supermarket Delivery in Kuwait"). Not fingerprinted this pass. |
| Saf Kuwait | safkuwait.com | NOT PROBED PAST HOMEPAGE | Small (7.9KB) homepage — likely thin/SPA; not investigated further. |
| QbuyMart | qbuymart.com | INCONCLUSIVE | 403 on curl_cffi chrome124 — not re-probed with other TLS profiles or Playwright this pass. |
| Co-op Kuwait | co-opkw.com | INCONCLUSIVE | Homepage is only 2.3KB (likely a redirect stub or thin landing page) — the real cooperative-society storefronts in Kuwait are typically per-branch, not a single national site; would need per-cooperative discovery. Not pursued. |

## Dead ends worth remembering

- **Kuwait has a dense, healthy independent-grocer web-storefront ecosystem** — the marketplace-first sweep (search for "سوبر ماركت الكويت اونلاين") returned 10+ distinct real candidates on the first pass, several already confirmed as real Shopify/e-commerce sites (Sinbad, and likely Salamarket/Arzaq/eBaqala too). This country is NOT exhausted — a follow-up pass focused on Salamarket, Arzaq, and eBaqala (all showed substantial page weight, a good sign) would likely yield 1-2 more sources quickly.
- Do not re-onboard `lulu_kw` or `taw9eel_kw` via a different storefront name — both are already covered.
