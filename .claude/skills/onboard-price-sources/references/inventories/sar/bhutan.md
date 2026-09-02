# Bhutan

_Inventory written: 2026-09-01_

Final F&B sweep (SAR agent A). Baseline: 3 food sources (azha_pasa, sherza,
shoponline_bt — all supermarket-channel Shopify/custom-cart storefronts).
Goal was breadth of retailer type (fresh-market, convenience,
specialty-food, marketplace) rather than a 4th supermarket. Result: **0
built**. Bhutan's online-retail footprint outside the three already-onboarded
supermarkets appears to be essentially nonexistent — this is a small
(~800k population), internet-restricted, single-time-zone market with very
few D2C storefronts of any kind, food or otherwise. No web-search tool was
available this session (session-wide WebSearch budget was already
exhausted by other agents in this sweep), so discovery here was limited to
direct domain probing off plausible naming patterns — a materially weaker
method than a real search pass. **Treat this as under-searched, not
exhausted** — a future pass with WebSearch available should re-run
discovery properly before trusting this null result long-term.

| Source name | URL | Channel | Notes |
|---|---|---|---|
| Bhutan Shop | https://bhutanshop.com/ | — (handicrafts) | Live Shopify store, `/products.json` open — but the catalog is entirely handicrafts/souvenirs (singing bowls, hand-carved masks, dolls), zero food. Not F&B. DEAD for this purpose. |
| Bhutan Post | https://www.bhutanpost.bt/ | — | National postal service corporate site, no e-commerce/shop path. DEAD. |
| Rigsar | https://www.rigsar.bt/ | — | Rigsar Construction Private Limited — unrelated construction company, despite the plausible-sounding domain. DEAD. |
| Tarayana Foundation | https://www.tarayanafoundation.org/ | — | Rural-development NGO; sells handicrafts, not food. DEAD. |
| bhutanmart.bt, drukmart.bt, jigmelingshop.bt, greenpath.bt, freshmart.bt, organicbhutan.bt, bhutanfresh.bt, zomsa.bt, happyshop.bt, bhutanonlinestore.com, thimphutshongkhang.bt, tashimart.bt, norzinmart.bt, 9dnine.bt, 8am.bt | (guessed) | — | All NXDOMAIN (`curl: (6) Could not resolve host`) — plausible names for a convenience/fresh-market/delivery brand, none registered. Guessed without a working search tool; do not treat as a real negative signal, just an unindexed guess. |

No convenience-store chain, fresh-produce delivery, specialty-food
importer, or grocery-delivery marketplace was found operating a web
storefront in Bhutan. The three existing supermarket sources
(azha_pasa, sherza, shoponline_bt) may represent close to the entire
Bhutanese online grocery sector at this time.

**Recommendation for the next pass:** re-run Phase 2 discovery on Bhutan
with WebSearch available (local-language Dzongkha search terms, Facebook
Marketplace / Instagram-based delivery services common in small Himalayan
markets, and a check of whether Druk Air's or a telco's app ecosystem
hosts any grocery mini-app) before concluding the market is truly limited
to 3 sources.
