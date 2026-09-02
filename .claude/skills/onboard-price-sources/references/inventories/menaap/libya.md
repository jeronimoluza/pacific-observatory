# Libya — price source inventory (menaap/north_africa/libya)

_Inventory written: 2026-09-01_ (wave 10; wave-11 update appended below, same day)

## Wave 11 update (2026-09-01)

Wave-11 brief: same target as wave 10 (>=5 sources AND >=2 food-and-beverage
sources; started this pass at 5/1). The wave-10 workbook candidates were
already exhausted and confirmed dead (Nawris/Nesraf/Watti; Souqly and Matjar
Libya already onboarded; Ubuy Libya a locality fail) — this pass entered
discovery directly (Phase 2), covering fresh Arabic-language angles wave 10
had not tried: a general Libyan business directory, a second marketplace
(LibyaShop) investigated down to its Firebase backend, a Sixam-Mart-family
delivery app's own API (not just its marketing pages), and several
freshly-surfaced named-store leads (Mall Tripoli, Tripoli Market, Libyan
Stores, Arkan Market). **None yielded a second food-and-beverage source.**
The food bar remains **not cleared** — this is now two independent,
differently-angled passes (wave 10 + wave 11) reaching the same conclusion,
which raises confidence this is a genuine structural gap rather than a
search-phrasing artifact.

New candidates probed and rejected this pass:

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| LibyaShop | libyashop.ly | Non-food marketplace, backend secured | "400+ stores, 140,000+ products" general marketplace. Featured-seller list (12 names) is 100% non-food (supplements, jewelry, perfume, fitness, electronics, toys, fashion). Firebase/Firestore backend properly secured (REST API returns `403 PERMISSION_DENIED` on `stores`/`products`; old Realtime Database explicitly disabled by the owner). No food merchant surfaced and no anonymous read path found — see `known_blockers.md`. |
| JETAK | jetak.me | DEAD (confirmed at API level, not just marketing pages) | Wave 10 found only marketing pages; this pass went further and hit the live `GET /api/v1/config` + `GET /api/v1/stores/latest` endpoints directly (Sixam Mart/6amMart Laravel stack). Real, unauthenticated API — but the one "grocery" module (`stores_count: 1`) is `slug: "demo-module"` and its one store is `"name":"الحور مول"`, `"phone":"+101511111111"`, `"email":"demo.store@gmail.com"`, `"address":"House, road"` — an unreplaced installer seed, not a live grocer. Rule-14 "named supermarket behind a delivery app" does not apply because there is no real named supermarket behind it. |
| Drubi | drubi.ly | DEAD, no API either | Re-checked beyond the wave-10 marketing-page verdict for an open API surface (the JETAK pattern): `/api/v1/config` and `/index.php/api/v1/config` both plain-Apache 404, `api.drubi.ly` doesn't resolve. No backend reachable at all. |
| Mall Tripoli | malltripoli.com | Non-food | YouCan (Moroccan e-commerce SaaS) storefront, LYD currency confirmed in `window.Dotshop` config. `<meta name="keywords">` on `/collections` lists only clothing/electronics/kitchen-appliances/furniture/home-appliances/home-decor — no food category exists. |
| Tripoli Market | tripolimarket.com | DEAD — Cloudflare, full gate exhausted | 403 on all three curl_cffi profiles (chrome124/chrome120/safari17_0) AND on headless Playwright (`<title>Attention Required! \| Cloudflare</title>`) — genuine block per the mandatory two-lever gate, not a TLS false positive. No platform fingerprint recovered (challenge served before any storefront markup). |
| Libyan Stores | libyanstores.com | Non-retail | Joomla 4 corporate site for a B2B brand-distribution company ("A gate to the Libyan Markets") — imports/distributes EU-manufactured goods into Libya. `/products` and `/products/` both 404. No cart, no price text. |
| Arkan Market | arkan.top.ly | DEAD — domain lapsed | NXDOMAIN confirmed against both `8.8.8.8` and `1.1.1.1` explicitly (rule 15). |
| Libyan Platform Co. for Food Import | lpcffi.com | Non-retail | B2B food-import company corporate site; no shop/cart/price markup anywhere (checked for `price`, `shop`, `السلة`, `أضف إلى`, `د.ل` — all absent). |
| Libya business directory ("دليل ليبيا التجاري") | sites.google.com/view/libyabd | Not actionable | Lists 39 physical markets/supermarkets by name (e.g. "Elkhairat super market", "الماسة للتسوق", "5150 SUPER MARKET") with **zero URLs** — a Facebook/physical-presence directory, not a lead list. Confirms Libya's grocery retail is overwhelmingly offline/Facebook-only, consistent with wave 10's finding. Not worth probing each name individually without a URL to start from. |
| Hayat Market, Rocket (talabatak.app) | — | Wrong country | Hayat Market is Mogadishu, Somalia (per its own Wikipedia infobox). Rocket/`talabatak.app`'s own meta description says "مطاعم اسوان" (restaurants in Aswan) — Aswan, Egypt. Both false positives from generic Arabic search terms, same pattern as wave 10's markitworld.com (Beirut)/hasseal.com+shamaam.com (Saudi Arabia). |
| Libyan wholesale fruit/vegetable market price bulletin | — | Not found | Searched explicitly for an official Tripoli/Benghazi wholesale (سوق الجملة) produce price bulletin, the kind several other MENA NSOs publish (Tunisia/Egypt/Morocco/Yemen equivalents all surfaced instead) — no Libyan equivalent exists online. Would have been a `fresh-market` or `official_avg` channel candidate; genuine structural absence, not a search-phrasing miss. |

**Conclusion carried forward for wave 12+:** treat Libya's food-and-beverage
gap as settled unless a materially new channel appears (e.g. a currently
app-only platform — Drubi, JETAK, Dokkan, WDelivery, Presto — launches a web
catalogue, or a new grocery-delivery startup appears in search that wave
10/11 haven't already dismissed). Re-running the same discovery angles a
third time is unlikely to be productive; the food bar for Libya is an
honest, twice-verified shortfall (5 sources / 1 food).

**Secondary task completed:** `bigly_ly`'s double-counting defect (parent
"food" category re-listing every descendant product, walked alongside its
own leaf subcategories) was fixed generically in `_opencart_base.py`
(product_id dedup within a run) rather than just in this one spider's
config, since any `CATEGORY_URLS`-mode OpenCart spider that lists a parent
alongside its own leaves would hit the same defect. Before: 791 rows / 437
distinct `product_id` (354 duplicate rows, all sharing a product_id but a
different context-dependent URL, which is why URL-based dedup never caught
it). After: 437 rows / 437 distinct `product_id` / 437 distinct `url`, 0
duplicates. See `bigly_ly.yaml` notes and `_opencart_base.py` for detail.

Wave-10 brief: Libya started this pass at 2 sources / 1 food (`wfp_prices`
shared regional `official_avg` + `bigly_ly` `supermarket`). Target was
>=5 sources AND >=2 food-and-beverage sources. 4 ACCEPT-verdict candidates
were supplied in `outputs/sources_pending_will.xlsx` (Pending sources
sheet, rows 63-66 + P4 rows 218/249), all workbook-flagged `FNB` (closes
gap). **3 of the 4 ACCEPTs turned out dead on live verification** — the
workbook's automated scout was fooled by category-name presence /
marketing copy without checking for real product inventory.

## Onboarded this pass

| Source | Channel | Platform | Notes |
|---|---|---|---|
| `souqly_ly` | marketplace | Next.js (App Router) storefront with an open JSON API (`/api/products?page=<n>`) | Workbook ACCEPT #3 ("3,800+ products" claim). Live catalog is actually 16 products (ids 1-16, complete, 2 pages) — recorded honestly rather than padded to match the workbook's stale claim. General dropship goods (electronics, perfume, religious books, prayer accessories, jewelry) — no food category exists on the site. LYD, median 187.5, min 95, max 380, 0 zero-price, 0 blank names, 16/16 distinct product_id and url. Prices are plain numeric strings, no thousands-separator or minor-unit trap. |
| `matjar_libya` | marketplace | Next.js storefront, server-rendered, clean schema.org Product JSON-LD per PDP | Workbook P4 spare, reclassified "ACCEPT non-food" by the workbook itself ("anti-theft bags, camera detectors, hair oil"). Confirmed: general dropship (beauty/skincare, home gadgets, baby toys, kitchen gadgets, health devices) — the "matbakh-libya" (kitchen) category is kitchen GADGETS, not food. 112 products across 5 pages (page 6+ empty — clean stop condition, matches the page's own `numberOfItems:112` JSON-LD exactly). LYD, median 219, min 113, max 557, 0 zero-price, 0 blank names, 112/112 distinct product_id and url. JSON-LD `offers.price` read directly (e.g. "199.00") to avoid the site's own comma-decimal display text ("199,00 د.ل.") being misread as a thousands separator under the LYD 3-decimal trap. Locality: LYD prices + explicit Tripoli/Benghazi/Misrata delivery despite a +33 (France) contact number (externally-operated dropship-to-Libya storefront, common pattern, not a locality fail). |
| `bsc_cpi` (`ly_bsc_cpi`) | null (cpi_benchmark, not retail) | PDF, text-extractable via pdfplumber | Non-food lead from the brief ("Bureau of Statistics and Census Libya — CPI"). Monthly "Report on Inflation and Consumer Price Indices by Main Groups" PDF, base year 2024=100, genuinely current (July 2026 report uploaded 2026/08). Libya's own pre-2018-COICOP-revision 12-group scheme (00 General Index [dropped] + 01-12), codes used as published (identity mapping). Filenames are not a reliable naming pattern (typos, `_compressed`, `-1` suffixes) so the fetcher ranks PDF links by their WordPress `/uploads/<year>/<month>/` upload path and reads the actual report period from the PDF's own header text. Test run: 12 rows (divisions 01-12), 0 duplicate hashes, idempotent on re-run (cutoff correctly advances). |

Final count: **5 sources / 1 food** — total-source bar cleared, food bar
**NOT** cleared (needed >=2). Honest shortfall — see below.

## Candidates probed and rejected (workbook ACCEPTs that turned out dead)

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| Nawris | nawris.net | DEAD — seed/demo data, not a live marketplace | Workbook's #1-ranked lead ("17 branches, 17 cities, licensed by Libyan authorities"). Storefront and `/api/products`, `/api/global/stores`, `/api/search` are all genuinely live (200, no auth), but the entire catalog is 4 fake rows: `"name":"هاتف تجريبي"` (literally "test phone"), sold by `"متجر النورس التجريبي"` (literally "Nawris demo store") / `"تاجر تجريبي"` ("test merchant"). Unlaunched template install. |
| Nesraf | nesraf.com | DEAD — empty catalog behind an intermittent Cloudflare wall | Workbook ACCEPT #2 ("broad marketplace with grocery-adjacent categories"). `curl_cffi` 403s on all three profiles but Playwright clears it once (WooCommerce/Martfury theme) — inconsistent even under Playwright (a later request hit the same challenge again). Independent of the WAF: all 18 top-level categories, including a dedicated `grocery`, are EMPTY ("No products were found matching your selection"), as is `/shop`. The only live products are ~15 books/legal-history titles from a single publisher, not a grocery marketplace. |
| Watti | watti.ly | DEAD — pre-launch, "Coming Soon" | Workbook ACCEPT #4 ("Live: Libyan grocery/food delivery"). Public site is a marketing landing page only; hero copy explicitly says the consumer app/catalog is "Coming Soon." `panel.watti.ly` (vendor portal) redirects in an infinite loop. |
| Souqly | souqly.ly | ACCEPTED, but non-food | The one workbook ACCEPT that verified live. See "Onboarded this pass" above — general dropship, no food category. |
| Matjar Libya | matjar-libya.com | ACCEPTED (P4 spare), non-food (workbook's own reclassification confirmed) | See "Onboarded this pass" above. |
| Ubuy Libya | ubuy.com.ly | Not probed — fails locality (rule 8) per brief | Cross-border reseller; brief already flagged this as a locality fail. |

## Non-food leads investigated (brief's "cheap fetcher builds")

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| Bureau of Statistics and Census Libya CPI | bsc.ly/economic_statistic/prices/ | ONBOARDED as `bsc_cpi` | See "Onboarded this pass" above. |
| GECOL (General Electricity Company) tariff | gecol.ly | DEAD — connection timeout, government server unreachable | DNS resolves cleanly against both 8.8.8.8 and 1.1.1.1 (`154.73.133.229`), but `curl_cffi` times out after 30s with no TLS handshake. Not WAF-walled, appears derelict. Worth a re-check in a future wave. |
| Central Bank of Libya CPI (secondary CPI publisher) | cbl.gov.ly | Not pursued — Cloudflare 403, deprioritized | Whole domain 403s (Cloudflare) on curl_cffi impersonate=chrome124; not fully worked through the mandatory curl_cffi-then-Playwright gate since `bsc.ly` already provides a live, open CPI series for the same analytical role. |
| Libyana / Al-Madar mobile plan pages | — | Not investigated this pass | Time-boxed out after the CPI + electricity leads; genuine gap for a future pass. |
| National Oil Corporation / fuel price-stabilisation fund pump price | — | Not investigated this pass | Same as above — a real candidate for a dedicated `tariff` build in a future wave. |

## Dead ends worth remembering (food search, 5 WebSearch calls + direct probes)

Libya's online grocery/food-delivery ecosystem is either **app-only** or
**pre-launch/brand-presence-only** — no live, scrapable web catalog for
food/groceries was found beyond the already-onboarded `bigly_ly`.

- **App-only, no web catalogue whatsoever**: `drubi.ly` (Drubi — landing
  page + app-store links only), `jetak.me` (JETAK, Benghazi — white-label
  Sixam Mart/6amMart Laravel stack, marketing pages only), `dokkan.ly` /
  `www.dokkan.ly` (does not resolve — "Dokkan" is App Store only),
  `wdelivery.ly` / `www.wdelivery.ly` / `wdelivery.com.ly` (none resolve
  — "WDelivery" is App Store only). "Presto" (the largest Libyan delivery
  startup per WebSearch, 2,000+ merchants) was not domain-probed after
  `presto.ly` / `prestolibya.com` / `getpresto.ly` all failed to
  resolve — not investigated further given the 100% app-only pattern
  already established by the other four.
- **Brand-presence-only, no e-commerce**: `geant.ly` (Géant hypermarket —
  React/Vite single-page site, Home/About/Magazine/Contact nav only, zero
  shop/product/price content, social-media links only).
- **Wrong country (search false positives)**: `markitworld.com`
  ("Markit | Your Online Supermarket" — explicitly "Covering all of
  Beirut", Lebanon, not Libya), `hasseal.com` and `shamaam.com` (both
  real, live fruit/vegetable e-commerce stores — WooCommerce/Salla
  respectively — but priced in SAR, i.e. Saudi Arabia, not Libya; rejected
  on locality per rule 8 despite otherwise looking like exactly the kind
  of `fresh-market` source Libya needs).
- **Domain doesn't resolve**: `carrefour.ly`, `carrefourlibya.com`,
  `spinneys.ly`, `lulyhypermarket.ly`, `nagah-market.ly`, `alnagah.ly` —
  none of the obvious regional-hypermarket-brand domain guesses exist for
  Libya. `panda.ly` resolves but redirects to a bare `/lander` stub (no
  content). `monoprix.ly` resolves to a generic 404 error page.
- **A "sourcing gap, not a depth gap" conclusion, reached honestly**:
  given 3 of 4 workbook ACCEPTs were dead and an additional ~10 direct
  domain/app checks found no live web catalog, the food shortfall here is
  a genuine sourcing gap in Libya's nascent (and heavily app-first)
  e-commerce sector, not a case of an existing spider under-crawling — the
  only real online food storefront found in this entire pass, at any
  depth, is the already-onboarded `bigly_ly` (`big.ly/food`).
- **Method note for the next run**: Arabic-language search for Libya
  grocery/food-delivery terms reliably surfaces the same five app-only
  platforms (Drubi, JETAK, Dokkan, WDelivery, Presto) regardless of
  phrasing ("متجر بقالة أونلاين", "سوبر ماركت اونلاين", "توصيل خضار
  وفواكه") — a sixth WebSearch call is unlikely to surface anything new
  without a materially different angle (e.g. searching for a *specific*
  named physical chain's own site rather than "online grocery Libya" in
  general, which is what eventually surfaced Géant).
