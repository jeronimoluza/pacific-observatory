# Afghanistan — price source inventory (menaap/afghanistan)

_Inventory written: 2026-09-01_

Cold-start inventory. Wave-10 brief: Afghanistan started this pass at 4
sources / 0 food (`wfp_prices` official_avg + three `marketplace` sources:
`kabulshop_af`, `4sough_af`, `etohfa_af`). Target was >=5 sources AND >=2
food-and-beverage sources. 6 workbook candidates were supplied in
`outputs/sources_pending_will.xlsx` (Pending sources sheet, rows 109-110 +
184-185 + 247-248), none flagged food-channel by the workbook itself.

## Onboarded this pass

| Source | Channel | Platform | Notes |
|---|---|---|---|
| `melat_shop_af` | supermarket | Dara.af marketplace backend (open Laravel REST API, `backend.dara.af`) filtered to one seller | **Rule-14 split**, not a new domain. Dara.af has exactly 5 registered sellers total (`GET /api/v1/sellers`); Melat Shop (960 products) is the only one that reads as genuine grocery — dairy, spices, biscuits, baby feeding, personal care, one line's own `attributes` naming the supplier as "سوپرمارکیت‌های هفت‌سین" (Haftsin Supermarkets). The other 4 (Zala, Easy Shop, Asan Mart, and an inactive "Haftseen" account with 0 products) were checked and rejected as non-food. 1,357 rows, 578 tagged `Food` outright (+180 Beverage, +16 Milk & Dairy, +9 Chocolates & Snacks, +7 Cooking Oil) — food-and-beverage-adjacent share ~58%. AFN, median 75, min 5, max 3,549 (no outliers). 0 zero-price, 0 blank names, 1,357/1,357 distinct product_id and url. |
| `superstan_af` | supermarket | WooCommerce Store API behind an "hcdn" bot-wall, scraped via `scrapy-playwright` (same pattern as the existing `dawana_sd` Sudan spider) | Found via Dari WebSearch (`سوپرمارکت آنلاین کابل خرید مواد غذایی` → English follow-up `Kabul Afghanistan online grocery delivery supermarket website`), not the workbook. Self-described "Afghanistan's first cryptocurrency supermarket". **Confirmed GIFTING/REMITTANCE PLATFORM, not domestic retail** — its own About Us page: "so that the Afghans who live outside of Afghanistan can shop for their families or loved ones who were left behind", plus a crypto-to-cash remittance product at /send/ and a donation pitch. Prices (USD) carry a delivery/donation margin — 0.5L water at $0.80 is ~4x Kabul street price; bulk staples (wheat flour 50kg $30) price near market. Flagged loudly in YAML `notes:` per rule 8. curl_cffi impersonate chrome124/chrome120/chrome131/safari17_0 all flat-403 (identical "Checking your browser" hcdn challenge); Playwright navigating straight to the API URL passes cold, no homepage warm-up needed. **Triple-language catalog, not single**: 93 raw listings = 43 English + 33 Persian + 17 Arabic (by permalink path). 29 English/Persian pairs share a real `sku` and a WPML hreflang link — deduped to the English member. The 17 Arabic listings have a BLANK `sku` and NO hreflang link (confirmed on live pages) — a disconnected second catalog that conflicts on price where it overlaps (sugar $5.00 vs $4.20, lentils $4.00 vs $5.50, rice10kg $17 vs $12, tomato paste $3.00 vs $1.50 — 4 of 8 spot-checked). Dropped in full rather than fabricating a translation match. Net: 93 → **47 canonical rows** (43 en + 4 fa-only singles). Also fixed a double-HTML-entity-escaping bug in `&#8211;` (WordPress stores the literal entity text in the title; Chromium's `<pre>` JSON viewer escapes it a second time) — `html.unescape()` now loops to a fixed point. Food-and-beverage share ~49% (23/47). 0 zero-price, 0 blank names, 47/47 distinct product_id and url. |

Final count: **6 sources / 2 food** — bar cleared. (superstan_af row count corrected from an initial 93 to 47 after a coordinator audit caught unmerged triple-language listings; see the dedup note above.)

## Candidates probed and rejected

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| Agrix agricultural marketplace | agrixmarketplace.com | DEAD — expired domain, now a parking page | The one workbook candidate flagged as plausibly food. Root path JS-redirects to `/lander`, which resolves to a GoDaddy/wsimg domain-parking shell (`window.LANDER_SYSTEM="PW"`, `parking-lander` bundle) — the marketplace itself no longer exists at this domain. |
| Dara | dara.af | Marketplace itself REJECTED as a source (channel=marketplace catalog not worth scraping directly) but its seller directory yielded `melat_shop_af` | Workbook said "item prices were not exposed" — true for the rendered homepage/shop page (only price-filter-slider "0 AFN" placeholders in static HTML), but a Playwright network trace of `/en/shop` found the real backend (`backend.dara.af`, open REST, no auth) serving full product+price JSON. Per the marketplace-is-a-directory rule, split into first-party sellers instead of scraping the blended catalog — see `melat_shop_af` above. Zala (762 products, mostly beauty/fragrance/fashion) and Easy Shop (426 products, mostly books/electronics) were also checked via the same API and rejected as non-food. |
| Halim Pharma | halimpharma.com.af | Correctly excluded — pharmacy, not food | Not probed further; workbook already classified it correctly and pharmacy never counts toward the food bar regardless of catalog depth. |
| Taza Pharma | tazapharma.af | Correctly excluded — pharmacy, not food | Same as above; not probed. |
| Ubuy Afghanistan | ubuy.com | Not probed — fails locality (rule 8) per brief | Cross-border reseller; brief already flagged this as a locality fail. |
| World Prices Afghanistan | world-prices.com | Not probed — `aggregate_proxy`, never counts | Brief already flagged this; would not have counted toward either the source or the food bar even if verified live. |
| sawda.af ("Online Grocery Shopping and Online Supermarket in Afghanistan") | sawda.af / www.sawda.af | DEAD — NXDOMAIN | Surfaced by English WebSearch as the top-billed Afghan online-grocery hit. Re-resolved against both 8.8.8.8 and 1.1.1.1 per rule 15 — both apex and `www.` return NXDOMAIN. Site does not currently exist despite being indexed. |
| haftsin.com | haftsin.com | DEAD — parked domain | Guessed while chasing the "Haftsin Supermarkets" name found in a Melat Shop product's `attributes.Manufacturer` field. Returns a 114-byte JS-redirect-to-parking-lander page, same signature as agrixmarketplace.com. `haftsin.af`, `haftseen.af`, `haftsinsupermarket.com`, `melatshop.af`, `melatshop.com` all fail DNS resolution outright (no site ever existed at those names, or a coincidental unrelated brand). Haftsin does NOT appear to run its own direct-to-consumer web storefront outside of supplying Melat Shop on Dara.af. |
| kabulshop_af "مواد خوراکی" (food) category, re-examined for a rule-14 split | api.kabulshop.com | Investigated, no split taken — fragmented across sellers, and the top seller isn't actually food | Only 18 of 477 kabulshop_af rows carry the `مواد خوراکی` (food) category tag, spread across 9 different `companyId` sellers (max 8 rows for any one). The single dominant seller in that slice sells herbal weight-loss teas, black-garlic supplements and cosmetics soaps/serums under the same "food" tag — not a genuine grocery merchant. Splitting it out would have required relabeling a wellness/cosmetics seller as food, which rule "label honestly" forbids. |
| 4sough_af, re-examined for a per-seller split | 4sough.com | Investigated, no split possible — no seller identity exposed | 4sough.com's PDPs carry substantial grocery-adjacent categories (rice, spices, nuts, biscuits) but expose no `seller`/`vendor`/`store` field anywhere in the server-rendered HTML or JSON-LD (checked for `__NEXT_DATA__`, `"seller"`, `"vendor*"`, `"store*"`, `"shop*"` keys — none present beyond generic "become a seller" UI copy). Unlike Dara, there is no backend endpoint that lets you scope a request to one first-party merchant, so a rule-14 split is not mechanically possible here without a bespoke per-product page scrape that groups by (unavailable) seller identity. |
| Superstan, non-grocery homepage claim ("free food delivery for vulnerable families") | superstan.market | Onboarded anyway — verified as real retail, not aid-only | The site's own marketing copy leans on a cryptocurrency-charity framing, and a handful of SKUs are pre-bundled "Emergency"/donor-style packages (Baby Care Package, Winter Clothing Package). The majority of the 93-SKU catalog is plain per-item grocery pricing (individual rice/oil/lentil/egg/tea SKUs at normal per-unit prices, not just bundles), so it was treated as a genuine retail catalog rather than excluded as an aid-only listing. |

## Dead ends worth remembering

- **The workbook's 6 Afghanistan candidates were 0-for-6**: 2 pharmacies
  (correctly pre-excluded, not food), 2 locality/aggregate-proxy rejects
  the brief had already called, and the one "could plausibly be food"
  candidate (Agrix) turned out to be an expired, now-parked domain. The
  workbook did not close this country; fresh discovery did.
- **Rule-14 (split a marketplace into first-party merchants) is
  candidate-dependent, not a mechanical win.** It worked on Dara.af
  because Dara's backend exposes a `seller` object with a stable
  `seller_id` you can filter on. It failed on kabulshop_af (the food tag
  is fragmented across many small non-food sellers) and was structurally
  impossible on 4sough_af (no seller identity in the page at all). Check
  for a `seller`/`vendor`/`store` field in the API or page data *before*
  assuming a marketplace can be split — don't assume every `*_wolt_*`-style
  win generalizes.
- **A "Manufacturer" or "Brand" attribute string naming a real supermarket
  chain (here: "سوپرمارکیت‌های هفت‌سین" / Haftsin Supermarkets, on a Melat
  Shop dairy product) is worth a 5-minute domain-guessing detour, but
  don't over-invest** — every direct-domain guess for Haftsin/Haftseen
  either 404'd on DNS or resolved to a parked-domain page. The brand
  appears to sell only through Melat Shop's Dara.af storefront, not its
  own site.
- **Two of Afghanistan's genuinely live grocery-adjacent sites (Dara,
  Superstan) were both hiding real JSON APIs behind a front that looked
  unpromising at first glance** (Dara: empty price sliders on the
  rendered shop page; Superstan: a flat curl_cffi 403 on every
  impersonation profile). Both fell to the standard playbook — Playwright
  network-trace for Dara, "Playwright to discover, plain-Playwright to
  scrape" for Superstan's hcdn wall — reinforcing that a front-page
  block or an empty static render is not evidence of a dead source.
- **Dari + Pashto search yielded almost nothing Afghanistan-specific**
  beyond confirming 4sough_af (already onboarded) and Facebook-only food
  pages (not scrapable as a catalog); the Iranian online-supermarket
  ecosystem (Digikala, Okala, Modiseh, Tezol) dominates Dari-language
  search results and is not a valid Afghanistan source. The winning query
  was an **English** search ("Kabul Afghanistan online grocery delivery
  supermarket website"), which surfaced both sawda.af (dead) and
  superstan.market (the actual win) — worth remembering that for this
  particular country, local-script search underperformed English, the
  opposite of the general guidance.
- **A shared `sku` plus a WPML hreflang pair is a real join key; a blank
  `sku` and no hreflang is proof of NO relationship, not evidence to
  fuzzy-match around.** superstan_af's catalog turned out to carry THREE
  language editions, not two — English and Persian are genuine
  WPML-linked translations (shared sku, hreflang pair), but a third,
  Arabic edition sits on completely disconnected WordPress posts (blank
  sku, zero hreflang) that partially duplicate the same commodities at
  DIFFERENT prices. The safe move was to drop the unlinked edition
  outright rather than guess a name-translation match — a spot-check
  showed the guess would have been wrong 4 of 8 times.
- **A single `html.unescape()` call is not always enough.** Some
  WordPress-stored titles carry a LITERAL HTML entity string (`&#8211;`)
  as their actual title text (not a transport-encoding artifact), and
  Chromium's `<pre>` JSON-viewer re-escapes that leading `&` to `&amp;`
  when serializing page HTML source — the exact source `response.text`
  reflects for a scrapy-playwright spider. One `html.unescape()` pass
  only peels back the second layer, leaving a still-visible `&#8211;` in
  the output. A quick manual check using Playwright's `innerText` (which
  silently resolves one layer as part of DOM text extraction) can mask
  this and make the bug look fixed when it isn't — always check the raw
  `response.text`/`page.content()` path the spider itself uses, not a
  convenience accessor. Loop `html.unescape()` to a fixed point instead
  of calling it once.
