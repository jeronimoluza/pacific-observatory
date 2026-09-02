# Papua New Guinea

_Inventory written: 2026-08-05_

<!-- Axes legend: scaffolding = spider|fetcher ; analytical_role = retailer_sku|official_avg|tariff|cpi_benchmark|aggregate_proxy ; extraction_pattern per skill taxonomy -->

| Source name | URL | COICOP divisions covered | Source category | Cadence | Auth required? | Machine-readable? | Anti-bot risk | Wayback coverage | Per-SKU IDs? | scaffolding | analytical_role | extraction_pattern | coicop_classification | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NSO PNG CPI (quarterly XLSX) | https://www.nso.gov.pg/statistics/economy/consumer-price-index/ | 01–12 (PNG uses 12 expenditure groups aligned to COICOP; XLSX tables downloadable per quarter) | NSO CPI | Quarterly | No | XLSX (per-quarter download, pdfplumber not needed) | Low | Yes (back to 2020) | No | fetcher | cpi_benchmark | tabular_download | publisher_labeled | Each quarterly release page (e.g. /december-quarter-2024/) carries a "Download Tables (.xlsx)" link. Groups: Food & Non-Alcoholic Beverages; Alcoholic Beverages, Betel Nut & Tobacco; Clothing & Footwear; Housing; Household Equipment; Health; Transport; Communication; Recreation; Education; Restaurants & Hotels; Miscellaneous. 12 groups — division 13 folded into 12 by NSO. Group-level index numbers (not just % changes) in Excel. Back to at least 2020. |
| ICCC fuel prices (HTML + PDF) | https://iccc.gov.pg/category/fuel-prices/ | 07.2.2 (petrol/diesel); 04.5.4 (kerosene) | Regulated fuel prices | Monthly | No | HTML table (Port Moresby prices) + PDF (all provinces) | Low | Yes | No | fetcher | tariff | html_scrape | source_curated | Monthly press statement page and PDF. ICCC announces Indicative Retail Prices (IRP) around the 8th of each month. Prices in toea per litre (100 toea = 1 PGK). Port Moresby table in HTML; national/provincial averages in linked PDF (e.g. /wp-content/uploads/2026/04/Press-Statement-IPR-Fuel-Prices-April-2026.pdf). Products: petrol (COICOP 07.2.2), diesel (07.2.2), kerosene (04.5.4). COICOP map: petrol→07.2.2, diesel→07.2.2, kerosene→04.5.4. Archive to at least 2025 on /category/fuel-prices/. |
| ICCC declared goods — rice/flour/sugar | https://iccc.gov.pg/declared-goods/ | 01.1.6 (rice); 01.1.1 (flour/cereals); 01.1.8 (sugar) | Official commodity price surveillance | Quarterly (rice/flour) / Monthly (sugar) | No | PDF (surveillance reports) | Low | Partial | No | fetcher | official_avg | pdf | source_curated | ICCC monitors factory-gate vs. wholesale/retail for Ramu Sugar (monthly), Roots Rice/Trukai (quarterly), Flame flour/3-Roses flour (quarterly). Surveillance conducted in Port Moresby, Kokopo, Lae, Goroka. Reports published as PDFs — fetch from /declared-goods/ page or public registry. COICOP map: rice→01.1.6, flour/cereals→01.1.1, sugar→01.1.8. Most recent 2022 Rice Industry Pricing Review PDF available: /wp-content/uploads/2023/08/2022-Rice-Industry-Pricing-Review-Final-Report.pdf. |
| ICCC water/sewerage MAPs | https://www.iccc.gov.pg/prices-productivity/price-regulation/water-sewerage/ | 04.4.1 (water supply) | Regulated utility prices | 4-year regulatory cycle | No | PDF (gazette and approved rates document) | Low | Yes | No | fetcher | tariff | pdf | source_curated | Water PNG Limited regulated via price-cap approach. Two PDFs available: "National Gazette — Water and Sewerage Services Prices Order 2023" and "Final Approved Water and Sewerage Rate 2023." Current arrangement effective Jan 2023, reviewed Jan 2027. Low cadence but high value — covers water tariff COICOP 04.4.1. COICOP map: water supply→04.4.1. |
| ICCC PMV & taxi fares (gazette PDF) | https://iccc.gov.pg/pmv-taxi-fares/ | 07.3.1 (passenger transport by road) | Regulated transport fares | Annual | No | PDF (National Gazette) | Low | Yes | No | fetcher | tariff | pdf | source_curated | ICCC sets maximum fares for PMV routes (urban and non-urban) and taxi services in 5 centres: Port Moresby, Lae, Mt. Hagen, Kokopo, Alotau. Adjusted annually (fuel+CPI indexed). 2026: urban PMV K1.20/trip; 2024: gazette No. G1019. PDF pairs available per announcement year (public notice + gazette). COICOP map: PMV/taxi→07.3.1. |
| PNG Power electricity tariffs | https://www.pngpower.com.pg/electricity-tariffs/ | 04.5.1 (electricity, domestic) | Utility tariff | Annual/irregular | No | HTML (tariff page exists; WebFetch returned footer only — may need browser UA) | Low | Yes | No | fetcher | tariff | html_scrape | source_curated | PNG Power Ltd (PPL) is the integrated national electricity provider. Tariff page confirmed via web search (pngpower.com.pg/electricity-tariffs/). 5% increase effective March 2025; current tariff approx. US$0.50/kWh (one of highest globally). NEA draft regulation PDF also available (nea.gov.pg). Try browser UA on tariff page; fallback to nea.gov.pg PDF. COICOP map: electricity→04.5.1. |
| FPDA/IFPRI fresh food prices (Excel) | https://fpda.com.pg/market-info/ | 01.1.7 (vegetables), 01.1.5 (tropical fruits), 01.1.4 (other cereals: rice), 01.1.9 (tubers: sweet potato/taro/cassava) | Official food price tracker | Monthly | No | Excel (downloadable from Dropbox; IFPRI collaboration) | Low | Yes | No | fetcher | official_avg | tabular_download | source_curated | FPDA (Fresh Produce Development Agency) + IFPRI collaboration. Excel database downloadable organized by year/crop/market. Tracks 5 PNG urban markets (Port Moresby Gordons, Lae, Goroka, Kokopo, and others). Items: sweet potato, taro, cassava, cooking banana, rice (staples); aibika, cabbage, capsicum, carrot, choko-tips (vegetables); lemon, orange, pawpaw, pineapple (fruits). Monthly average retail prices in PGK/kg. Also publishes quarterly bulletins. Active since 2020. Also accessible at ifpri.org/project/fresh-food-price-analysis-papua-new-guinea. |
| UPNG tuition fees structure (PDF) | https://www.upng.ac.pg/images/documents/2026_FeesStructure_Combined.pdf | 10.1.0 (tertiary education services) | University tuition | Annual | No | PDF (direct link, 477 kB; pdfplumber-extractable confirmed — binary readable) | Low | Yes | No | fetcher | tariff | pdf | source_curated | University of Papua New Guinea (UPNG) annual fees structure PDF. 2026: compulsory fees K3,585–K4,145 for domestic undergrads; K8,185–K26,930 for international students. Per-programme (School of Medicine, Business, Law, etc.) fee breakdown. Also check PNGUoT (pnguot.ac.pg) and Divine Word University for second source. URL pattern: /images/documents/YYYY_FeesStructure_Combined.pdf. COICOP map: tertiary tuition→10.1.0. |
| Hausples.com.pg rentals | https://www.hausples.com.pg/rent/ | 04.1.1 (actual rentals for housing) | Real-estate portal | Daily | No | HTML (server-rendered; listing cards and per-property canonical URLs confirmed) | Medium (Digital Classifieds Group / likely Cloudflare) | Likely | Yes (per-property slug) | spider | retailer_sku | scrapy_listing | source_curated | PNG's #1 real estate portal. Part of Digital Classifieds Group (Australia). 3,000+ listings with PGK prices (K2,000–K3,500/week examples seen). Server-rendered HTML. Per-property canonical URLs e.g. /rent/korobosea/7-moisana-street-section-77-lot-30274/. Filter by: apartment/house/duplex/townhouse/commercial; Port Moresby/Lae/others; price range (below K2,500/week, above K2,500/week). Probe with curl browser UA before Playwright — DCG Fiji sites (e.g. property.com.fj) are Cloudflare-blocked; PNG domain may differ. COICOP map: rental listings→04.1.1. |
| Marketmeri.com classifieds | https://www.marketmeri.com/real-estate/for-rent | 04.1.1 (rentals), 07.1.1 (motor vehicles: cars), 09.1 (electronics) | General classifieds | Daily | No | HTML (server-rendered; canonical per-property URLs with IDs confirmed) | Low–Medium | Likely | Yes (property ID in URL) | spider | retailer_sku | scrapy_listing | classifier | PNG's leading general classifieds (est. 2012). Server-rendered HTML. Canonical URLs e.g. /house-rent-in-9-mile-national-capital-323359 (ID suffix). Rental prices in PGK (K4,500–K6,064 examples). Categories: residential (apartments, houses, bedsits, townhouses, duplexes, serviced apartments), commercial (offices, retail, warehouses), vehicles, electronics, household goods. Covers COICOP 04.1.1 (rentals), 07.1.* (vehicles), 09.1 (electronics). Wide basket coverage. |
| Digicel PNG mobile data plans | https://www.digicelpacific.com/mobile/pg | 08.1.0 (telephone and internet services) | Telco tariff | Irregular | No | HTML (JS-rendered plan cards; /pg/ path 404'd — verify correct URL) | Low–Medium | Unknown | No | fetcher | tariff | html_scrape | source_curated | Digicel PNG (PNG's largest telco). 7 data pack types from 60 MB (K3/day, K6/7-day) to 13 GB. Major price reduction in April 2024 (~70% on 1-day, ~50% on 30-day). Two other operators: Bmobile-Vodafone (bmobile.com.pg) and Telikom PNG. URL to verify: digicelpacific.com/mobile/pg (404 returned on initial probe — try digicelpacific.com/pg or browse main site). COICOP map: mobile data→08.1.0. |
| Bmobile PNG mobile plans | https://www.bmobile.com.pg/ | 08.1.0 (telephone and internet services) | Telco tariff | Irregular | No | JS-rendered (plan categories visible but prices not in SSR HTML) | Low | Unknown | No | fetcher | tariff | scrapy_playwright | source_curated | Bmobile-Vodafone (PNG's second telco). Plan categories confirmed: Moa Plus Packs (unlimited on-net + data), International Call Plans, Special Passes, Postpaid Plans, Roaming. Prices not in server-rendered HTML — JS-loaded. Needs Playwright to hydrate price cards. Lower priority than Digicel (similar COICOP 08.1.0 coverage). COICOP map: mobile plans→08.1.0. |
| WFP/HDX global food prices — PNG | https://data.humdata.org/dataset/wfp-food-prices | 01.1.1 (rice, 01.1.4/01.1.9 tubers/staples) | Official food price tracker | Monthly | No | CSV (HDX 403 via WebFetch — access via global dataset with country filter) | Low | Yes | No | fetcher | official_avg | tabular_download | source_curated | WFP global food prices database covers PNG staples (rice, sweet potato, cassava). HDX 403 on direct WebFetch but dataset is public. Access via data.humdata.org/dataset/wfp-food-prices global CSV, filter by country=Papua New Guinea. Monthly market retail prices in PGK and USD. Complements FPDA data on different crop list. Lower priority than FPDA/IFPRI for PNG given FPDA has local sourcing. |
| Pacific Data Hub / SPC CPI — PNG | https://pacificdata.org/data/dataset?member_countries=pg | 01–12 (CPI index series for PNG) | Regional CPI aggregator | Monthly/annual | No | CSV (portal 403 via WebFetch — access via SPC API or direct dataset browse) | Medium (portal 403) | Likely | No | fetcher | cpi_benchmark | tabular_download | publisher_labeled | Pacific Data Hub (SPC/PRISM) aggregates CPI and socioeconomic data for Pacific Island countries including PNG. HIES 2009/2010 dataset confirmed on portal. CPI time series may be available. Portal returns 403 via WebFetch — try direct dataset URL or SPC API endpoint (stats.pacificdata.org). Lower priority than NSO PNG CPI (direct quarterly XLSX) — use as backfill/cross-check. |

<!-- SKIP list — probed and excluded -->
<!-- brianbell.com.pg: confirmed corporate portal; /product-category/ 404s; homecentres.brianbell.com.pg/shop/ redirects to / with no e-commerce markup. No online store. -->
<!-- shop.cpl.com.pg (Stop & Shop): ECONNREFUSED on direct WebFetch — likely geo-blocked (PNG residential IP only) or server-side CDN restricting non-PNG IPs. CPL is PNG's largest retailer. Revisit with residential-proxy probe before onboarding. -->
<!-- bsp.com.pg (Bank South Pacific): HTTP 403 on WebFetch. BSP fees referenced in press (SME fee reduced from K15→K8/month etc.) but fee schedule PDF location unknown. Revisit with browser UA or search for direct PDF URL. -->
<!-- airniugini.com.pg (Air Niugini flights): booking engine (JS-rendered dynamic fare search). Fares from K236.50 one-way confirmed. Not a static tariff page. Tier 2 at best; low PPP priority vs. tariff sources. Deferred. -->
<!-- sp.com.pg (SP Brewery): B2B brewery; no consumer price list or online shop. -->
<!-- coca-cola.com/pg/en: Brand marketing page; no price list. -->
<!-- steamships.com.pg: Logistics/hospitality/property conglomerate; no grocery retail or online shop. -->
<!-- expatistan.com, livingcost.org, mylifeelsewhere.com: crowd-sourced aggregators — skill says do not onboard. -->
<!-- food_pro spider (existing config): unknown source; inventory entry missing — leave untouched pending identification. -->

## Wave (2026-09-01) -- retail sweep result

Targeted because PNG sits at 2/6 food sources. Corrections and new leads found:

- **shop.cpl.com.pg (Stop & Shop) -- correction to the 2026-06-10 entry above.**
  That entry recorded "ECONNREFUSED, likely geo-fenced" -- re-probed 2026-09-01
  with `curl_cffi impersonate=chrome124/chrome120/safari17_0` per the mandatory
  gate: the hostname does not resolve at all (`Could not resolve host`), including
  against 8.8.8.8 directly. This is **not a WAF or geo-fence, the subdomain has
  been retired/removed** -- `cpl.com.pg` itself resolves fine (200, corporate
  site) and has no "shop"/"store"/"order online" links anywhere in its HTML.
  CPL Group currently has no reachable online storefront. Do not re-try
  `shop.cpl.com.pg` without evidence of a new subdomain.
- **RH Hypermarket (rhtradingpng.com) -- new candidate, genuinely blocked.**
  PNG's largest supermarket (45,000+ SKUs, Vision City/Gordons), confirmed via
  press (thenational.com.pg) to have launched online grocery ordering with
  pickup/delivery. Probed both levers per the skill's mandatory gate:
  `curl_cffi` (chrome124/chrome120/chrome99/edge99/safari17_0) all return
  HTTP 403 with `cf-mitigated: challenge` and a Cloudflare Turnstile CSP: this
  is a **genuine Cloudflare managed challenge**, not a TLS-fingerprint false
  positive. Playwright network-trace confirms the same -- page title stays
  "Just a moment...", the only network call is `challenges.cloudflare.com/turnstile/...`,
  no product/API endpoint is reachable. Per the skill's stop rule ("when
  curl_cffi impersonation AND Playwright both return 403/challenge, stop"),
  this is recorded as a real block, not pursued further this pass. No
  alternate domain found (visioncitypng.com/rh-hypermarket/ is a mall-directory
  page about the store, not a storefront -- confirmed no `shop.*`/`order
  online`/`myrh`/ecommerce links in its HTML). **High-value target for a
  future dedicated anti-bot effort** (would need a captcha-solving stack).
- **Tango Ltd** (tangopng.com) -- checked because Tango was named as a Boroko/
  Tokarara supermarket chain. Site is a bare corporate placeholder ("TangoPNG
  Portal", "Welcome to Tango Ltd Portal! Connecting all Tango Group [staff]")
  -- no e-commerce, looks like an internal staff portal, not a public storefront.
  DEAD END.
- **stopandshop.com.pg** -- returns a generic Apache 403 error page (no
  Cloudflare/WAF headers, no cf-ray) -- looks like a stale/misconfigured
  domain rather than CPL's real site (CPL's actual domain is cpl.com.pg, which
  has no storefront -- see above). Not pursued further.
- `pngmart_pg` and `wikonomi_pg` (already onboarded, `channel: marketplace`)
  were checked for a first-party seller directory per the marketplace-as-
  directory doctrine; both are community/aggregator price-report sites over
  many small informal sellers rather than a directory of onboardable retailers
  with their own catalogs -- not pursued further this pass.

**No new source shipped this wave.** Next agent: RH Hypermarket is the single
highest-value PNG grocery target but needs a captcha-solving/anti-bot budget
this pass didn't have; do not re-attempt with bare curl or plain Playwright,
both are already proven insufficient.
