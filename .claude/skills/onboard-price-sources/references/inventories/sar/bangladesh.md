# Bangladesh

_Inventory written: 2026-09-01_

Final F&B sweep (SAR agent A). Baseline: 3 food sources (chaldal, othoba,
shwapno_bd — all supermarket-channel). Goal was breadth of retailer type,
not a 4th supermarket. Result: **2 built** — khaasfood_bd (specialty-food:
organic/halal meat, dairy, spices, honey) and deshi10_bd (fresh-market:
fresh produce, meat, dairy alongside packaged grocery).

| Source name | URL | Channel | Source type | Cadence | Auth required? | Machine-readable? | Anti-bot risk | Per-SKU IDs? | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Khaas Food (BUILT: `khaasfood_bd`) | https://www.khaasfood.com/ | specialty-food | Organic/halal food producer-retailer (Dhaka) | Weekly | No | Yes, with a trap | Low — 200 on curl_cffi chrome124, no WAF | Yes (uuid in RSC chunk) | Next.js App Router, same defect pattern as `dmart_in`: category pages carry NO price (client-fetched), PDPs embed a `"product":{...}` object in a backslash-escaped React Server Component stream chunk. 148 sitemap PDP URLs, all verified: 148/148 rows, 100% BDT, food share 100%. |
| Deshi10 (BUILT: `deshi10_bd`) | https://www.deshi10.com/ | fresh-market | Curated fresh/organic grocery (AIZ/6valley theme) | Weekly | No | Yes (server-rendered cards) | Low — 200 on curl_cffi chrome124, no WAF | Yes (numeric id in wishlist onclick) | 100 categories (mostly food: fresh fruit/veg/meat/poultry/dairy/fish, plus a personal-care tail), paginated via `?page=N`, verified real pagination (page 2 returns a distinct product set). 632/632 rows verified, 100% BDT, food share ≈76.6%. |
| Priyoshop / PriyoShopRetail | https://priyoshop.com/ , https://priyoshopretail.com/ | — | B2B MSME supply-chain | — | — | No | — | — | JS-redirects to a WordPress marketing site for a B2B corner-shop/HoReCa distribution business (app/WhatsApp order channel). No consumer web catalogue. DEAD. |
| Foodpanda Bangladesh (pandamart) | https://www.foodpanda.com.bd/ | marketplace (quick-commerce) | — | — | — | — | 403 on curl_cffi chrome124 (not re-probed with Playwright or other fingerprints this round) | — | Not pursued further this pass — restaurant-delivery-first platform, pandamart grocery vertical not directly reachable at this domain root. Worth a dedicated re-probe. |
| Evaly, Rokomari, Shajgoj, Bagdoom, Ajkerdeal, Shomvob | various | — | General e-commerce / non-food verticals | — | — | — | Evaly is a defunct/scandal-collapsed marketplace (2021); Rokomari is books; Shajgoj is beauty/cosmetics; Bagdoom and Ajkerdeal timed out on probing; Shomvob is a social-commerce reseller app | — | Checked and ruled out as non-food or non-functional for this pipeline's purposes. Not deep-probed beyond a homepage fetch. |
| Meena Bazar, Agora, Unimart | various | supermarket | — | — | — | — | agorasuperstores.com returned HTTP 500; unimart.com.bd has an SSL cert/hostname mismatch | — | Not pursued — same channel (supermarket) as the 3 already-onboarded sources; also technically broken at probe time. Redundant-channel skip, not a genuine dead end worth re-chasing first. |
