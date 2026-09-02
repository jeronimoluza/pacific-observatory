# Ethiopia

_Inventory written: 2026-09-01_

Wave 12 pass. Ethiopia had 2 sources / 1 food (`deliver_addis` supermarket, `wfp_prices`
official_avg). Needed >=3 more sources AND >=1 more food, to clear the bar of >=5 sources
AND >=2 food. **Result: 5 sources / 2 food — bar cleared exactly, on the workbook's ACCEPT
candidate (AradaMart) plus two fresh-discovery non-grocery wins.** The other two workbook
candidates (Shoa/Queens, klik Grocery) were both dead ends, and four non-food fetcher
candidates from the brief (ESS CPI, EEU electricity tariff, Ethio Telecom / Safaricom
prepaid bundles, Ethiopian Petroleum Supply Enterprise fuel prices) were all tried and all
hit genuine structural walls — see the dead-ends table below.

## Built this pass

| Source key | Channel / role | URL | Rows (test run) | Notes |
|---|---|---|---|---|
| `aradamart_et` | `supermarket`, retailer_sku | https://www.aradamart.net/ | 396 | Wix Stores grocery delivery, Addis Ababa. JSON-LD PDPs, same pattern as `capelle_nr`. Amharic (Ge'ez) glosses on ~10% of names, verified surviving as raw UTF-8 in the shipped JSONL. |
| `ethiopiapropertycentre_et` | `real-estate`, retailer_sku, `coicop_codes: ["04.1.1"]` | https://ethiopiapropertycentre.com/for-rent | 202 (of a ~2,072-listing full catalogue; `timeout: 3600` set for production) | Addis Ababa residential rentals (flats-apartments + houses only, this pass). JSON-LD RealEstateListing PDPs. Currency is a genuine per-listing mix of USD/ETB (112/90 in the test run) — flagged loudly in the YAML per rule 8, not a diaspora mislabel. |
| `mekina_et` | `marketplace`, retailer_sku | https://www.mekina.net/ | 68 | Dedicated used/new car marketplace. `/cars/search` is client-rendered (no server data); the site's own 5 RSS feeds (`/feed`, `/feed/featured`, `/feed/private`, `/feed/brokers`, `/feed/dealers`) are fully server-rendered XML with a structured `<price>` element — no PDP crawl needed. |

## Candidates tried and rejected (workbook)

| Candidate | URL | Verdict given | Actual result |
|---|---|---|---|
| Queens Supermarket / Shoa | https://shoashopping.com/ | SUSPECT (brief said try anyway) | **DEAD — domain parked.** `shoashopping.com` (bare, no `www`) times out on port 443 entirely; `www.shoashopping.com` resolves to a *different* IP (Namecheap's parking infrastructure) serving a "recently registered domain" upsell page, not the supermarket. `/wp-json/wc/store/v1/products` 404s — there is no WooCommerce install at this domain at all; the brief's platform guess (and the workbook's) was wrong, per rule 23. WebSearch for an alternate Queens/Shoa domain came back empty — both chains have a real physical presence (Yandex Maps, Facebook page `facebook.com/shoashopping`) but no working online storefront was found anywhere. |
| klik Grocery | https://klik.delivery/grocery | ACCEPT | **DEAD — app-only, no web catalogue.** `/grocery` and `/merchants/stores` are both Next.js marketing pages (the latter is a "partner with klik" seller-signup page, not a store directory). No `/api/`, no JSON endpoint found in any of the 6 shared JS chunks pulled from the page. Confirms the workbook's own `AI_NOTES` on this row ("Catalogue is in-app; the web tier shows categories only"). Since the catalogue was never reachable, the rule-19 overlap check against `deliver_addis` was moot — there was nothing to intersect. |

## Non-food fetcher candidates tried (brief's rule-16 list) — all dead ends

| Candidate | URL | Result |
|---|---|---|
| ESS (Ethiopian Statistical Service) monthly CPI | https://ess.gov.et/price/ | **STRUCTURAL — no per-division index table exists to parse.** Found the real download mechanism (`ess.gov.et/download/consumer-price-index-<month>-<year>/` -> WP Download Manager `?wpdmdl=<id>` -> a genuine typeset (not scanned) PDF; pdfplumber extracts clean tables). But the monthly bulletin only ever publishes a 2-way General/Food/Non-food split, and only the *headline* (Overall) series has an index **level** (Table 4, 12-month moving average, base Dec EFY2009=100) — Food and Non-food are published as inflation **rates** only, never as index levels. The skill's own open design question ("Headline CPI has no slot in IndexObservation... fetchers currently drop the headline row") rules out shipping the one level series that does exist without inventing an unapproved `coicop_code: "00"` sentinel. `databank.ess.gov.et/reports` (an 8MB single-page app, likely Power BI) was not pursued further — too costly to reverse-engineer for this pass. |
| EEU (Ethiopian Electric Utility) tariff | https://www.eeu.gov.et/electricity-tariff/latest-electricity-tariff | **STRUCTURAL — no clean numeric table, only prose.** Found the real content route (`electricity-tariff/latest-electricity-tariff`, a Laravel CMS JSON payload of "content" articles). But the actual ETB/kWh figures live only inside long-form, multilingual (Oromo/Amharic) worked-example news posts explaining bill calculations line by line (e.g. "...taarifa haaraa... kaffaltiin anniisaa kWh tokkoo Qarshii 5.0593..."), not a structured rate table. Reliably regex-extracting a current 7-tier residential schedule from prose across two languages was judged too fragile for this pass. |
| Ethio Telecom prepaid bundles | https://www.ethiotelecom.et/mobile-packages/ | **STRUCTURAL — content is client-fetched, not in the served HTML.** Page ships with zero `<table>` elements and zero Birr/ETB price strings in the raw response; the nav menu renders but the package cards do not (no `admin-ajax`/REST call found in the static HTML to follow). WP REST API (`/wp-json/wp/v2/types`) is locked (401). Would need a real headless-browser render to reverse-engineer, out of scope for this pass. |
| Safaricom Ethiopia prepaid bundles | https://www.safaricom.et/ | **DEAD — no bundle/tariff page at all.** Homepage is a Next.js single-page marketing site focused entirely on M-Pesa; there is no linked data/voice bundle or tariff page anywhere in the nav. |
| Ethiopian Petroleum Supply Enterprise fuel prices | https://epse.gov.et/ | **DEAD-ish — wrong agency, no retail price page.** EPSE's own site only publishes corporate/financial reports (monthly/quarterly/half-year/annual financial reports, KPI reports) — it manages import/distribution, not retail pricing. The actual regulator is the Ministry of Trade and Regional Integration (see next row). |
| Ministry of Trade and Regional Integration fuel-price notices | https://www.motri.gov.et/en/announcements (PDFs e.g. `.../announcement/July%20fuel%20price.pdf`) | **STRUCTURAL — scanned PDFs, OCR too unreliable to ship.** Found real monthly fuel-price notice PDFs (found via the announcements listing). Site cert is expired (legitimate Drupal government site, not a sinkhole — content confirmed with `verify=False`, per rule 13's "expired cert + spam/sinkhole" bar not actually met here since there's no spam). The PDFs themselves are scanned images (pdfplumber returns empty text on every page). OCR'd the cover-letter page with `tesseract -l amh` (the `amh` traineddata is installed) and got clean, legible Amharic prose — but the actual per-city retail-price TABLE on the interior pages OCRs to unusable garbage (city names and digits scrambled beyond any plausible cleanup, e.g. digit runs like "4785 «8:5 4854. 557 5244"). Not shippable at any reasonable confidence. Also required routing `pytesseract`, which is referenced by one existing (`american_samoa/doc_bfi.py`) but not actually installed in the shared `.venv` — did not add it, to avoid mutating the shared environment for a source that turned out unusable anyway. |

## Depth-audit note

No commodity/COICOP-leaf depth audit was in scope this pass — this was a source-count task
(5 sources / 2 food), not a leaf-coverage task.

## What's left to try (not exhausted, just not reached this pass)

- An amh-aware OCR pipeline with image preprocessing (deskew/upscale/binarize) might
  recover the motri.gov.et fuel-price tables; not attempted here given the effort/reward
  given the pass was already over its source-count bar.
- `databank.ess.gov.et/reports` — likely a Power BI or similar embed; worth a real
  Playwright network-trace session to find the underlying data API, which could unlock a
  genuine per-division COICOP CPI series for Ethiopia (currently zero `cpi_benchmark`
  coverage).
- Ethiopia Property Centre currently only covers Addis Ababa for-rent (flats + houses).
  The same platform covers Amhara/Oromia/Southern Nations too (seen in nav) and could be
  widened in a follow-up pass without new scaffolding.
- Ethio Telecom's package pages would likely yield to a proper headless-browser
  network-trace session (same "Playwright to discover, plain HTTP to scrape" pattern used
  elsewhere) — not attempted here since text-based (curl_cffi) probing was the priority
  given the WebSearch/time budget.
