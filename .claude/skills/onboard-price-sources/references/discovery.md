# Discovery — finding price sources worth probing

Load this when the scope is "find sources" rather than "onboard this specific URL."

## The unit of discovery is a platform, not a country

Scaffolding is per-source and probing is per-site, but **discovery is not per-country**. Anti-bot infrastructure clusters by *tenant* (every AS-Watson property, every Lazada TLD, every Cloudflare-strict account), and storefront software clusters by *platform* (every Shopify store answers `/products.json`). Both cut across borders. Working country-by-country means rediscovering the same platform twenty times and re-probing the same WAF twenty times.

Practical consequence: when the ask is "expand coverage," resolve it into **platform sweeps and marketplace enumerations first**, and only fall back to per-country search for what those don't reach.

## Discovery-method ladder

Measured across the 2026-07-30 and 2026-07-31 EAP expansion passes, best to worst:

| Rank | Method | Why it wins |
|---|---|---|
| 1 | **Aggregator / marketplace enumeration** | One API surfaces 5–20 retailers at once. Highest yield per unit of effort by a wide margin. |
| 2 | **Platform fingerprinting** | Identify the storefront software, then the endpoint is already known — see `platform_fingerprints.md`. Scaffolding is near-free. |
| 3 | **Local-language search** | Native-language queries surface national chains that English queries never return. |
| 4 | **Wikipedia / listicle** ("list of supermarket chains in X") | Decent recall, poor signal on whether anything is scrapeable. |
| 5 | **App-store charts** | Finds the market leaders, which are usually the *least* scrapeable — see below. |
| — | **Generic English search** ("grocery in X") | **Worst.** This is what the per-country 17-category sweep degenerates into. Use it only as cold-start fallback. |

## The inverse-correlation law

**In EAP, aggregator size and scrapeability are inversely correlated.** Market leaders are WAF-hardened; mid-tier and small-market grocers running off-the-shelf platforms verify clean on the first try.

Confirmed hardened (do not spend probe budget here without a dedicated anti-bot effort): Korea Naver / 11st / Gmarket / Coupang, China JD / Tmall, HK HKTVmall and the whole AS-Watson family, SG sheng_siong / redmart, ID segari, VN aeon / lottemart, TH villamarket, PH landers, plus foodpanda / GrabMart / Shopee across every market.

So: **budget probe time toward mid-tier and regional players**, and treat the market leaders as a separate, explicitly-scoped Playwright/stealth project. A run that spends its afternoon losing to Cloudflare on Coupang and never probes the four mid-tier chains has inverted its own returns.

## Cold-start: the 17-category per-country sweep

Use this only when a country has no inventory file and the platform/marketplace angles came up empty. It is the lowest-ranked method on the ladder — it is a completeness net, not a first move.

| Default scaffolding | Category | Probe these |
|---|---|---|
| spider | Online supermarket / hypermarket / fresh-grocery | National grocery chains, hypermarkets, q-commerce |
| spider | Online pharmacy | Pharmacy chains with browseable PDPs |
| spider | E-commerce / marketplace | National general-merchandise sites (clothing, appliances, electronics) |
| spider | Personal-care / beauty retailers | National drugstore-style chains |
| spider | Streaming / app-store country pricing | Netflix, Spotify, Apple, Google country pages |
| fetcher | Official food / commodity price tracker | Central bank or trade-ministry daily/weekly trackers |
| fetcher | Fuel pump-price tracker | Regulator / state oil-company monthly/weekly retail fuel |
| fetcher | National statistics office datasets | Average-price tables, retail-price surveys, HBS unit-value tables |
| fetcher | Customs / trade unit-value tables | Wholesale or import unit values where published |
| fetcher | Utility tariff pages | Electricity, water, gas — regulator or operator |
| fetcher | Telco / ISP tariff pages | Mobile and fixed-broadband plans |
| fetcher | Public-transport fare schedules | National rail, urban transit, ferry |
| fetcher | Airline / car / motorcycle list prices | National carrier flight prices; dealer list prices |
| fetcher | University tuition pages | Per-program annual tuition, major national universities |
| fetcher | Bank fee schedules / FX boards | Retail bank fee PDFs; central bank FX tables |
| spider | Real-estate / rental portal | Per-city rental listings with median rent by bedrooms |
| spider | Classifieds | National classifieds covering vehicles, electronics, household |
| fetcher | NSO CPI division indexes | Monthly/quarterly CPI by COICOP division — `analytical_role: cpi_benchmark` |

Plus, where they cover the country: restaurant-delivery aggregators, hotel booking sites, insurance comparison sites.

Aim for 12–25 candidates across `analytical_role` values. Cast wide for `retailer_sku` / `official_avg` / `tariff`; for `cpi_benchmark`, **one strong CPI source is enough** — it's the benchmark, not a coverage axis.

Prefer English-translated landing pages where they exist (`global.oliveyoung.com` over `oliveyoung.co.kr`) — usually easier to scrape. Same for stats-office portals.

## Wholesale and official-average feeds

Consistently the highest-yield sources for the hard COICOP leaves — live animals, fresh fish, tubers, dried seafood — which retail supermarkets structurally do not carry. Only a handful of `official_avg` manifests exist against 140+ retailer ones, so this is where the marginal source is worth most.

What to look for: agriculture-ministry and wholesale-market daily price feeds.

**Already shipped in EAP** (check before rediscovering): Taiwan MOA `data.moa.gov.tw` — JSON API family, one endpoint per commodity class, unauthenticated; Hong Kong AFCD `Wholesale_Prices.csv` — one daily CSV covering live cattle/pig/chicken plus fish/veg/fruit; Thailand Talaad Thai — ~2,000 commodities via numeric-id walk. Between them the live-animal leaves retail structurally cannot reach are covered.

**Verified candidates, not yet built:** PH Bantay Presyo (`bantaypresyo.da.gov.ph`, DataTables fed by POST AJAX per category), MY FAMA (`fama.gov.my`, Malay path only — `/en/` 404s), KR KAMIS (`kamis.or.kr`, 17 sub-APIs, broadest EAP ag+fishery catalog, gated on a free key signup), JP MAFF (best route to persimmons), ID panelharga (national daily panel, Angular SPA — needs a network-trace pass first).

**Build these as general catalog walkers, not targeted extractors.** When you find a wholesale feed, take its *whole* catalog rather than only the commodities that motivated the search. The marginal cost of the other 1,900 commodities is near zero and they fill leaves you haven't audited yet. Set `analytical_role: official_avg`, **`channel: wholesale`** (the enum value shipped 2026-08-04 alongside the Taiwan MOA and HK AFCD fetchers), and `coicop_classification: deferred_gemini` when the catalog is too broad to hand-map. Older wholesale manifests predating the enum value use `channel: null` — migrate them when you touch them.

## Do not onboard as "coverage"

Cost-of-living survey aggregators — Numbeo, LivingCost, Expatistan, MyLifeElsewhere, Nomad List — are already present for most countries and are **not** price-level sources. They inflate source counts and coverage tables without adding a single real SKU. Exclude them from candidate lists and from any coverage statistic meant to show retail breadth.
