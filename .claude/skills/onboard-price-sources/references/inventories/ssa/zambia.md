# Zambia

_Inventory written: 2026-09-01_

Wave 12 pass. Already-covered before this pass: `lusakadelivery` (supermarket, Shopify),
`wfp_prices` (official_avg) — 2 sources / 1 food. Brief needed 3 more sources AND 1 more
food; target was >=5 sources AND >=2 food.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| Shoprite Zambia | https://www.shoprite.co.zm/ | — | **DEAD — no online store** | Same pan-African AEM `shopriteafrica` corporate-portal tenant already logged dead for `shoprite.co.mz` and `shoprite.co.ls` (identical clientlibs, identical `/content/shopriteafrica/<cc>/en/...` path shape) — see known_blockers.md. `curl_cffi impersonate=chrome124` clears fine (200, no WAF); the 140-entry sitemap is entirely recipes (98), `explore-shoprite/*` category-description pages, competitions, and store-locator. No `/shop`, `/products`, `/catalogo` path exists; `specials.html` links only to privacy/cookie-policy PDFs, no specials leaflet with prices. No shelf-collision risk to worry about (there simply is no catalogue) — rule 19 moot here. |
| TigmooEats | https://tigmooeats.com/ | — | **DEAD — app-only, no web catalogue** | Web root is a static Bootstrap marketing template (owl-carousel, mailchimp signup, app-store badges), not a SPA: no framework markers (`ng-app`/`id="app"`/`data-reactroot`/`__NUXT__`/`__NEXT_DATA__`) anywhere. Full Playwright render (networkidle + wait) fires zero listing/vendor/product API calls — only Maps/Analytics/chat-widget pings. Client route `home/listing/<lat>/<lng>` serves identical landing-page bytes (no client router). No web ordering surface exists at all; would have needed rule-19 intersection against `lusakadelivery` if it had one, but it never got that far. |
| AfriDelivery | https://afridelivery.app/ | specialty-food (Premuni Stores merchant only) | **SHIPPED** as `afridelivery_premuni_zm` | Multi-vendor delivery platform (Ionic/Cordova hybrid app served as a web PWA; backend `api.afrideliverymall.com`, shared with a "250taxi" white-label courier template). Walked `task=list` across all ~109 Lusaka delivery zones under `stype21=groceries`: only 9 distinct grocery/food vendor ids surfaced total (Premuni Stores x2, Zambeef x2, Eliado Meat Supplies, Yalelo, The Paches Store, Dew Fresh, Trefo Zambia) — not a homogeneous catalog, so the blended platform itself is only honest as `channel: marketplace` (would not count as food). Split out Premuni Stores (a genuine South-Asian-import specialty grocer) as its own first-party-merchant source per rule 14, both Lusaka branches (vendor ids 527, 532; disjoint item-id ranges, no collision). 525 rows, 525 distinct product_id/url, 0 zero-price, 100% ZMW, price range 6.30-378.00, median ~40.32, 100% food (Biscuits/Spices/Tea/Pulses/Papad/Flour/Dairy/Frozen/Condiments/Nuts/Sweets/Confectionery/Snacks/Starches). No overlap with `lusakadelivery` (different company/backend; Premuni Stores does not appear in lusakadelivery's Shopify catalog) — rule 19 clear. The other 8 vendors (Zambeef mostly weighed/zero-priced meat, a fishmonger, a produce store, etc.) are a residual lead for a future pass if more AfriDelivery merchants are wanted; each would need its own single-vendor manifest with an honestly-assigned channel, same pattern as Premuni. |
| ZamStats — Table 7 average prices | https://www.zamstats.gov.zm/ | null (official_avg) | **SHIPPED** as `zamstats_avg_prices` | "The Monthly" bulletin (WordPress; latest post discovered via open WP REST API search, NOT a hardcoded URL — bulletin slugs are irregular, e.g. `monthly-inflation-august-2026` vs double-barrelled `monthly-inflation-april-2024-april-2025`). Table 7 "National Average Prices for Selected Products": ~25-item basket (mealie meal, meat cuts, produce, fuel, cement, medicine, a vehicle), ZMW. The brief's "food basket BY PROVINCE" framing does not match what's actually published — Table 7 is a NATIONAL aggregate only (Table 1.4 nearby is CPI by province, an index, not average prices); no provincial average-price table was found. 25 rows verified, 0 zero/neg, food share 16/25 items. |
| ZamStats — Table 1.2 CPI by division | https://www.zamstats.gov.zm/ | null (cpi_benchmark) | **SHIPPED** as `zamstats_cpi` | Same bulletin, second table (kept as a separate fetcher — PriceObservation/IndexObservation split rule). 12-division pre-2018 COICOP scheme, 2009=100, back to Jan 2023 in one PDF but only the latest row is parsed per run (the PDF's year label is a rotated axis marker pdfplumber can't reliably attach to one row — see fetcher docstring). 12 rows verified, index 158.72-662.92. |
| ERB — uniform pump fuel prices | https://www.erb.org.zm/ | null (tariff) | **SHIPPED** as `erb_fuel` | Monthly "Petroleum Pump Prices, Press Statement and Price Build-ups" post. The press-statement PDF and its "Current...PumpPrices.pdf" alias are BOTH image-only (0 extractable chars via pdfplumber) — manually OCR'd once for cross-verification only (tesseract CLI available, but no `pytesseract` package in this venv or anywhere else in the corpus per `doc_bfi.py`'s own docstring, so OCR is not wired into the fetcher). Instead uses the sibling "PUMP-PRICE-BUILD-UP.pdf", which IS text-native, and reads its "Uniform Pump Price" row (ZMW/M3, /1000 for ZMW/L). 3 rows (Petrol/Diesel/Kerosene) verified live 2026-09-01, cross-checked against both the OCR'd press release text (exact match to 2dp) and ZamStats' independently-published Table 7 for the same period (also exact match) — high confidence. `coicop_codes: ["07.2.2"]` narrow. |
| ERB — ZESCO electricity tariffs | https://www.erb.org.zm/ | — | **NOT PURSUED THIS PASS** | Brief named this as a candidate; not probed given the bar was already cleared by the sources above (6 total / 2 food). Real lead for a future pass — ERB is a clean, no-anti-bot WordPress site. |
| MTN / Airtel / Zamtel prepaid bundle pages | (various) | — | **NOT PURSUED THIS PASS** | Brief named these as candidates (static HTML, cheap); not probed given the bar was already cleared. Real leads for a future pass wanting more `tariff` coverage. |

## Result

Zambia ends this pass at **6 sources / 2 food** (excluding `aggregate_proxy` and
`active: false`, of which there are none for this country):

- `lusakadelivery` — supermarket (food) — pre-existing
- `wfp_prices` — official_avg, channel null — pre-existing
- `afridelivery_premuni_zm` — specialty-food (food) — **new**
- `zamstats_avg_prices` — official_avg, channel null — **new**
- `zamstats_cpi` — cpi_benchmark, channel null — **new**
- `erb_fuel` — tariff, channel null — **new**

Clears the wave-12 brief's ">=5 sources AND >=2 food" bar with one source of margin.

## COICOP / channel gap after this pass

Food-channel coverage is now 2 sources (`lusakadelivery` supermarket +
`afridelivery_premuni_zm` specialty-food), both Lusaka-only. No `fresh-market` or
`convenience` channel source exists yet — The Paches Store (fresh produce) and Dew
Fresh on the AfriDelivery platform are untapped leads for that gap (see table above).
ZESCO electricity tariffs and MTN/Airtel/Zamtel telecom tariffs remain real,
easy `tariff`-channel leads for a future pass wanting more non-food coverage
depth (does not move the food bar, but is "real coverage" per rule 16).
