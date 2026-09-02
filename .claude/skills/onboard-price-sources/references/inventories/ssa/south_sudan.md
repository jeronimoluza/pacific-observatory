# South Sudan

_Inventory written: 2026-09-01_

Final F&B sweep, wave (2026-09), agent B. Cold-start (no prior inventory file
existed). Already-covered before this pass: `wfp_prices` (official_avg,
shared SSA fetcher) — 1 source / 0 food, no retail coverage.

**Result: 0 sources shipped. No viable online grocery found.**

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Juba Mall | Google Play `com.matt.jubamall`; guessed `jubamall.com` | **DEAD — cert mismatch, app-only** | Search calls it "the only online supermarket in South Sudan" (Android app). `jubamall.com` resolves but TLS fails with a hostname/certificate mismatch (`no alternative certificate subject name matches`) on every impersonation profile tried — not a WAF, a broken/misissued cert. No usable web catalog found. |
| Doyoom | https://doyoom.com | **OUT OF SCOPE — restaurant delivery, no grocery** | Live site (200, real content). Confirmed by page title ("South Sudan's #1 Online Food Delivery Platform – Order from Top Restaurants") and a scan of the HTML for grocery/supermarket keywords (zero hits) that this is a prepared-meal restaurant aggregator (COICOP 11, restaurants), not a food-and-beverage retail source. Does not qualify under this sweep's win criteria. |
| Karibu App, Zaylo | (app-only / Vercel preview) | **OUT OF SCOPE — restaurant delivery** | Same category as Doyoom: food-delivery from restaurants, not grocery retail. |
| UNION Super Market / Juba Mall Supermarket | Facebook only | **NOT PROBED — no web presence** | Facebook-page-only physical supermarkets; no independent website or ordering platform found. |
| Shop Ninja | https://shopninjaug.com | **NOT PROBED — cross-border reseller, low priority** | General online store shipping from Kampala (Uganda) to Juba in 2-3 days, not a South-Sudan-based grocery operation; deprioritized as out-of-market for a South Sudan price series. |

No delivery marketplace (Jumia/Glovo/Bolt/Yango-style) operates in South
Sudan. This looks close to a **structural absence** for online grocery
specifically (the market has real e-commerce activity — food delivery,
cross-border resale — but no working grocery storefront was found), though
the Juba Mall lead (broken cert, not a dead business) is worth one re-check
if the cert gets fixed.
