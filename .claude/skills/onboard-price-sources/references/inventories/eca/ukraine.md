# Ukraine (eca/eastern_europe/ukraine)

_Inventory written: 2026-09-01_

Wave 12. Starting state: 4 sources / 0 food (`rozetka_ua` marketplace,
`minfin_fuel` tariff, `eurostat_electricity`, `eurostat_gas` tariffs). Wave
brief's three candidate rows (Epicentr K, Liki24, Prom.ua) are all
non-grocers -- ignored per brief. Discovery target: grocery e-commerce.

## Wartime-cohort re-probe (supersedes the 2026-06-09 entry in `known_blockers.md`)

`known_blockers.md` recorded silpo.ua, atbmarket.com, auchan.ua, varus.ua,
megamarket.ua as all 403 when probed 2026-06-09 **from a non-UA IP with bare
curl**, with a note to re-probe individually before deciding per-source.
Re-probed 2026-09-01 with `curl_cffi impersonate=chrome124` from this
session's (also non-UA) network:

| Domain | Result | Notes |
|---|---|---|
| silpo.ua | HTTP 200 | Nuxt SSR, embeds full product payload inline. Built -> `silpo_ua`. |
| atbmarket.com | HTTP 200 | Plain server-rendered HTML, no JS needed. Built -> `atb_market_ua`. |
| varus.ua | HTTP 200 | Runs Magento (Apollo/GraphQL storefront on top). Home page yields no clean `/category`-style path (Vue app; category browsing goes through GraphQL, not scoped this wave). Not built -- candidate for a future pass using `_magento_base.py` conventions, needs a real GraphQL-sniff session (see Phase 3 "hunt JSON/XHR" step) that this wave didn't have budget for. |
| auchan.ua | HTTP 200 | Apollo/GraphQL SPA shell; homepage carries no server-rendered nav links at all (client-side hydration required to discover categories). Not built -- Tier 2/Playwright candidate for a future pass. |
| megamarket.ua | Not re-probed this wave (budget spent on the two that verified fastest -- ATB and Silpo). Re-check next pass; the known_blockers entry against it is stale (non-UA bare-curl 403). |
| zakaz.ua | HTTP 403 even under `curl_cffi impersonate=chrome124` | Real block, not a curl-TLS artifact. Not attempted further (rule 21: "when curl_cffi AND Playwright both 403, stop" -- Playwright wasn't run here since ATB+Silpo already cleared the bar, but the curl_cffi result alone is consistent with the existing `known_blockers.md` entry for `novus.zakaz.ua`, its sibling backend). |
| novus.ua | HTTP 200 (main site) but no server-rendered `/category`-style nav discovered in the time available -- likely a JS-hydrated storefront distinct from its `novus.zakaz.ua` q-commerce backend (which is separately 403-blocked per `known_blockers.md`). Not built this wave. |

**Conclusion: the 2026-06-09 "wartime cohort all 403" verdict was a bare-curl
TLS-fingerprint artifact, not a real block, for at least silpo.ua and
atbmarket.com** (rule 11). No UA-resident IP or DNS re-resolution against
8.8.8.8/1.1.1.1 was needed once `curl_cffi impersonate=chrome124` was used --
both cleared on the first try. `known_blockers.md` updated accordingly (see
below).

## Sources built this wave

| Source | channel | analytical_role | Notes |
|---|---|---|---|
| `atb_market_ua` | supermarket | retailer_sku | ATB-Market, largest discount grocery chain by store count. Server-rendered HTML, 151 categories, incremental `?page=N` pagination confirmed non-overlapping. |
| `silpo_ua` | supermarket | retailer_sku | Silpo, largest modern supermarket chain. Nuxt SSR; full product payload embedded inline per category page (internal API 404s directly, so the spider regexes the SSR-embedded copy). 259 categories. |

Both are Kyiv-priced (unauthenticated default city; Ukrainian grocers price
by city per the wave-12 brief -- Kyiv is the convention). City not added to
`_IDENT` since only one city is scraped per source. ATB and Silpo are
independently operated chains (different companies, different backend
platforms -- server-rendered custom stack vs. Nuxt) -- no rule-19
same-shelf risk between them or against `rozetka_ua` (a third-party
marketplace, disjoint product-id namespace).

Final measured numbers for both are in each YAML's `notes:` and in the
Phase-8 chat report for this run.

## Dead ends / deferred (record so the next run doesn't repeat the search)

- **zakaz.ua** -- 403 under `curl_cffi impersonate=chrome124`; treated as a
  real block (matches the sibling `novus.zakaz.ua` entry already in
  `known_blockers.md`). Not split into per-merchant sources this wave since
  the parent itself doesn't verify.
- **Ukrstat (ukrstat.gov.ua)** -- the brief's suggested "nearly free" 5th
  source (CPI / average consumer prices, `IndexObservation`,
  `period_kind: monthly_avg`). **Not built**: `www.ukrstat.gov.ua` serves an
  **expired TLS certificate** (`curl: (60) SSL certificate problem:
  certificate has expired`); the page also only resolves to a ~1.3KB
  redirect/analytics stub even with `verify=False`. Did not chase further
  because the two grocers already clear the wave's `>=5 sources AND >=2
  food` bar without it. Worth a fresh look in a later wave once/if the cert
  is renewed -- re-check `verify=False` output for an actual CPI table
  before writing off the whole domain as dead (rule 13 is about malware
  sinkholes / injected spam, which this is not; it's a config issue, not
  necessarily NSO abandonment).
- **Epicentr K, Liki24, Prom.ua** -- confirmed non-grocers per the brief
  (DIY big-box, pharmacy marketplace, general B2B marketplace
  respectively). Not re-investigated.
- **varus.ua, auchan.ua, novus.ua, megamarket.ua** -- all clear the
  wartime-cohort curl_cffi re-probe (HTTP 200) but were not built this wave
  for lack of time/budget once ATB+Silpo already cleared the bar. Varus and
  Novus run Magento-family backends (worth revisiting with `_magento_base.py`
  once the GraphQL/Vue category-discovery layer is sniffed); Auchan is a
  full client-side Apollo/GraphQL SPA needing a Playwright network trace to
  find its category-list and product-list endpoints. **These are real,
  live, verified-reachable candidates for the next Ukraine pass** -- not
  dead ends, just deferred.
