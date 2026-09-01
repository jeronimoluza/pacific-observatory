# Sierra Leone

_Inventory written: 2026-09-01_

Wave 9 pass, cold-start (no workbook candidates; confirmed empty in
`outputs/sources_pending_jero.xlsx` before starting). Already-covered before this pass:
`fews_net` (official_avg, shared SSA fetcher), `wfp_prices` (official_avg, shared SSA
fetcher) — 2 sources / 0 food, zero retailer sources of its own. Target was >=5 sources
AND >=2 food-and-beverage sources; needed 3 more, >=2 food.

**Result: 6 sources / 1 food.** Total-sources bar cleared; food bar fell one short
despite an extensive, multi-pronged search (11 web searches + ~35 direct domain/endpoint
probes). This is a genuine, documented shortfall, not a stopped-early one — see the dead
ends below.

## Shipped this pass

| Source name | URL | Channel | analytical_role | Status | Notes |
|---|---|---|---|---|---|
| Stats SL CPI | https://www.statistics.sl/index.php/cpi.html | null | cpi_benchmark | **SHIPPED** as `statssl_cpi` | Monthly CPI press-release PDF archive, live continuously 2008-2026. Table 3 of the latest release alone carries the full Dec-2021=100 series back to the base period, so one PDF backfills everything: 792 rows (66 months x 12 divisions) verified on disk. Site 403s a bare non-browser UA but is wide open to any real browser UA -- naive gate, not a WAF. PDF filenames are inconsistent and NOT chronologically ordered on the listing page; fetcher parses month+year out of each filename and picks the max date. |
| Africell SL tariffs | https://www.africell.sl/services/data-bundles/ | null | tariff | **SHIPPED** as `africell_tariffs` | Prepaid/postpaid/TikTok/Mifi-Router/combo mobile data-bundle tariffs. Plain server-rendered HTML tables, no JS, no WAF. 39 rows verified on disk, re-fetched cold and matched exactly. **Currency trap**: labelled "NLe"/"Le" -- confirmed both are the new leone (SLE), not legacy SLL, by magnitude (see YAML notes). |
| Orange SL tariffs | https://www.orange.sl/en/b2c-internet-personal/data-bundles-monthly.html | null | tariff | **SHIPPED** as `orange_tariffs` | Monthly/weekly/daily data-bundle tariffs. Server-rendered offer-variant cards. 10 rows verified on disk, re-fetched cold and matched exactly. **Currency trap, opposite direction from Africell**: every price is labelled "SLL" (legacy code) but the magnitudes are already new-leone scale -- cross-checked against Africell's independently-labelled "NLe" prices for the same bundle sizes (both ~300 for a ~15-20GB bundle). Emitted as SLE with the raw number unchanged. |
| Choithrams (via 247bigmarket.com) | https://247bigmarket.com/store/freetown/ | **supermarket** | retailer_sku | **SHIPPED** as `choithrams_sl` | The one genuine food win. Choithrams (Freetown-headquartered chain) sells through two named vendor storefronts on 247bigmarket.com -- Sierra Leone's own WooCommerce + multi-vendor-marketplace platform (`/store/freetown/`, `/store/kenema/`), NOT a foreign aggregator. Vendor "about" page confirms a real Freetown street address. 272 rows verified on disk (198 freetown + 66... see report; distinct product_id = distinct url = 272, 0 zero/blank), 71-79% food share by category (grocery/beverage/bakery/frozen/snacks/meat/dairy/spread/produce), re-verified via the site's own WooCommerce Store API (`wc/store/v1/products?include=<id>`) which matched the spider's scraped price exactly on every ID checked. channel=supermarket, not marketplace, per GLOSSARY's discriminating test (first-party inventory, curated names -- not third-party/seller-authored). **Currency**: site prices everything in USD; flagged loudly in the YAML per the locality rule (genuine Freetown retailer on Sierra Leone's own marketplace, not a diaspora storefront, but still a foreign-currency price for a country whose own currency is SLE). The marketplace's other 2 vendors (IC Royale = fashion/bags, Sana/skbuildingmaterials = building materials) are non-food and out of scope; a "Goodies" vendor referenced on social media/search results is gone (404 on every slug variant tried) as of 2026-09-01. |

## Dead ends (non-food leads)

| Candidate | URL | Status | Reason |
|---|---|---|---|
| EDSA (electricity tariff) | https://edsa.sl/ | **DEAD -- no published tariff table** | Live DotNetNuke CMS site (200 OK), but the "Tariffs" tab (`/Home/Tariffs`, TabId=21) renders an empty content module -- no tariff schedule, no PDF, nothing under CustomerService/eServices/AboutUs either. The site exists but the price data was simply never published to it. Re-check in a future wave in case this changes. |
| SALWACO (water tariff) | https://www.salwaco.gov.sl/ | **DEAD -- expired cert, empty/default page** | `salwaco.gov.sl` resolves (192.96.217.94, confirmed against 8.8.8.8) but HTTPS times out / has an expired certificate; plain HTTP on the bare IP serves a default Plesk "no website at this address" placeholder. Domain is effectively derelict. |
| Guma Valley Water Company | (no working domain found) | **DEAD -- no reachable domain** | Guessed domains (`gumavalley.gov.sl`, `gvwc.gov.sl`, `guma.gov.sl`, `guma.sl`, `gvwc.sl`, `gumavalleywater.com`) all fail to resolve against 8.8.8.8. Not pursued via web search this pass (budget went to the food side); worth one search in a future wave. |

## Dead ends (food leads)

| Candidate | URL | Status | Reason |
|---|---|---|---|
| Choithram / Freetown Supermarket / Gibrils / Monoprix SL corporate domains | choithram.com (self-signed cert, unrelated), choithrams.com (real, but **UAE storefront** -- locality violation), gibrils.com (404), various guessed .sl domains | **DEAD -- no independent domain; found via 247bigmarket instead** | None of the named chains from the brief have their own working e-commerce domain. Choithrams' actual online presence is exclusively through the 247bigmarket.com marketplace (shipped above). |
| Koussa Group brands (Freetown Supermarket, Freetown Mall, City Supermarket, Venus Corporation) | https://koussagroup.com/{freetown-supermarket,freetown-mall,city-supermarket}/ | **DEAD -- brochure only, no catalogue** | Static WordPress corporate site. Every branch page renders identical boilerplate (address, phone, "quality products" blurb) -- no product listing, no prices, no shop/menu link anywhere on the site. |
| Monoprix Supermarket SL | facebook.com/monoprixsupermarketsl | **DEAD -- Facebook-only** | Physical store on Wilkinson Rd, Freetown; no independent website, no online catalogue. Matches the brief's explicit "Facebook/Instagram-only shops do NOT count" rule. |
| Gibrils | (none found) | **DEAD -- no online presence found at all** | Targeted web search returned no website, Facebook page, or directory listing under this name. |
| Gokkam | facebook.com/gokkam2, Google Play / App Store only | **DEAD -- app-only, no web catalogue** | "Sierra Leone's #1 online ordering and delivery platform" per its own marketing, but the product is exclusively an Android/iOS app; `gokkam.com` does not resolve. |
| SendMe (sendmesl.com) | https://www.sendmesl.com/ | **DEAD -- app-only, no web catalogue** | Web page is a marketing landing page with app-store download buttons only; no browsable restaurant/vendor listing on the web. |
| crowddigitalmedia.com (food delivery) | https://crowddigitalmedia.com/ | **DEAD -- hosting suspended** | HTTP 429 "Site Unavailable / contact your hosting provider." |
| Jumia (jumia.sl) | https://www.jumia.sl | **DEAD -- Cloudflare challenge; likely not real Jumia** | `<title>Just a moment...</title>` 403 on curl_cffi chrome124, chrome120, AND safari17_0 (mandatory-gate failure on all three). Jumia's real African footprint does not include Sierra Leone, so this domain is plausibly parked/unrelated rather than a genuine Jumia storefront; not investigated further per the "all three profiles fail -> stop" rule. |
| Glovo (glovoapp.com/sl) | https://www.glovoapp.com/sl | **NOT PURSUED -- ambiguous country code** | `/sl` almost certainly resolves to Slovenia, not Sierra Leone, on Glovo's platform; Glovo's known African footprint (Kenya, Uganda, Ghana, Ivory Coast, Morocco) does not include Sierra Leone. Not pursued further. |
| Wolt (wolt.com/en/sle/freetown) | https://wolt.com/en/sle/freetown | **DEAD -- 404, not operating in Sierra Leone** | |
| Bolt Food (food.bolt.eu Freetown) | https://food.bolt.eu/en-us/389/freetown | **INCONCLUSIVE, not pursued** | Returns HTTP 200 but is an empty React SPA shell; couldn't confirm without Playwright whether Freetown is a real served city or the route just doesn't validate city IDs server-side. Not worth a Playwright pass for a single-country lead this thin; worth a quick recheck if revisited. |
| The Meat Factory SL (butchery + restaurant) | https://themeatfactorysl.com/menu/ | **CONSIDERED, NOT SHIPPED -- structurally a restaurant, not retail** | Genuinely scrapeable, clean price list (~80 items, "le"-denominated -- same new-leone-magnitude trap as Africell/Orange). Has a small embedded "Butchery"/"Raw Meat" section (roughly 6-9 raw-meat-by-weight SKUs, e.g. "Butchery 1KG Goat Meat 550le") but ~90% of the menu is prepared restaurant food (grilled plates, burgers, pizza, sandwiches) -- COICOP 11.1 restaurant fare, which has no slot in the food-channel enum (`supermarket/hypermarket/convenience/fresh-market/specialty-food`) and is exactly the kind of "stretch a live site to clear the bar" the brief warns against. Rejected rather than built as a narrow "specialty-food" spider scoped to just the butchery rows. |
| Salone Fast Market | https://www.salonefastmarket.com/ | **DEAD -- app-only; SEO markup is fabricated** | Lists a "Food & Agriculture" category, but the link goes to `/app`, an app-store-gated SPA shell. The homepage's JSON-LD `AggregateOffer` for that category (`lowPrice: 50000, highPrice: 5000000` SLL) is generic marketing schema, not real per-item data. |
| Salone E Market | https://saloneemarket.com/ | **DEAD -- essentially empty** | 1.4KB response, no content. |
| Market360 | https://market360.shop/ | **DEAD -- app-only marketplace, general goods not food** | Sitemap and marketing copy confirm this is an app-first marketplace (Google Play / App Store) for electronics/fashion/phones/vehicles; no food/grocery category found, no scrapeable web catalogue. |
| Ubuy Sierra Leone, African Food Supermarket, Motherland Groceries, Brixton Village | ubuy.sl, shop.africanfoodsupermarket.com, motherlandgroceries.com, brixtonvillage.com | **OUT OF SCOPE -- locality violation** | International resellers / diaspora grocers shipping goods labelled "Sierra Leone" to customers abroad (UK/US-style diaspora grocers), not domestic Freetown retail. Same anti-pattern as the Antigua diaspora grocers removed in an earlier wave. |
| goafricaonline.com/sl/directory/supermarkets, infosierraleone.jimdofree.com/business/supermarkets | (directory listings) | **NOT SCRAPEABLE -- phone-directory only** | Business directories, not e-commerce. The jimdofree listing in particular is an A-Z phone-book (name/address/phone, e.g. Choithram Supermarket, Freetown Supermarket, Atsons Supermarket, Essentials Supermarket, God's Time Investment Supermarket...) confirming most named Freetown supermarkets are brick-and-mortar only with no web presence at all. |

## Currency note for future passes

Sierra Leone redenominated in 2022 (SLE = 1,000 old SLL). Every retail price source found
this pass turned out to carry SOME form of this trap, in both directions:
- StatsSL CPI: unaffected (index values, not price levels).
- WFP food prices (pre-existing `wfp_prices`): emits raw SLL as-is per its own prior notes.
- Africell: labels new-leone prices "NLe"/"Le" (correct code, informal spelling).
- Orange: labels new-leone-magnitude prices "SLL" (WRONG/stale code, right magnitude).
- Choithrams/247bigmarket: sidesteps the whole issue by pricing in USD.
- The Meat Factory: "le"-suffixed prices, new-leone magnitude (same pattern as Africell/Orange).

The magnitude cross-check across independent sources (Africell's explicit "NLe" labels vs
Orange's stale "SLL" labels, both landing in the same numeric range for comparable data
bundles) was the decisive evidence for both telecom sources' currency calls -- worth
reusing as a general technique when a single source's own labelling is ambiguous or wrong.

## Recommended next steps for a future pass

1. Re-check EDSA's tariff tab periodically -- the CMS exists and is maintained, just empty.
2. One web search for Guma Valley Water Company's actual domain (not attempted this pass).
3. If Playwright becomes available, confirm whether Bolt Food actually serves Freetown.
4. Melcom-style "big win" food retailer does not appear to exist in Sierra Leone the way it
   does in Ghana -- the market is structurally thinner. Re-run marketplace enumeration in
   ~6 months in case 247bigmarket gains a second food vendor, or a new SL-specific
   marketplace (Salone Fast Market, Market360) moves its catalogue off app-only.
