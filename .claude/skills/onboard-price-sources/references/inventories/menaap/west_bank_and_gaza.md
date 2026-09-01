# West Bank and Gaza — price source inventory (menaap/middle_east)

_Inventory written: 2026-09-01_

Cold-start inventory (no prior file existed for this country). Wave-8 brief:
started at 3 sources / 2 food (`bravosupermarket_ps`, `karaz_ps`,
`wfp_prices`), no workbook candidates supplied ("DISCOVER"). Target was
>=5 sources AND >=2 food. No West Bank and Gaza rows exist in
`outputs/sources_pending_jero.xlsx` except the "NO CANDIDATES - discovery"
sheet, confirming the brief.

Context that shapes this market: Gaza's commercial internet is largely
destroyed since October 2023 and Gaza-based e-commerce is effectively gone
— every retail candidate found this pass is West-Bank-based. Government and
telecom infrastructure is also fragile: several `.ps` domains carry broken
or self-signed TLS certs, and both major mobile carriers run PerimeterX.

## Onboarded this pass

| Source | Channel | Platform | Notes |
|---|---|---|---|
| `pcbs_avg_prices_ps` | null (official_avg) | Plotly Dash SPA at pcbs.gov.ps/CPIDashBoard, POST to `/CPIDashBoard/_dash-update-component` (no auth) | PCBS's own "Average Price" series by item (not the CPI index) — 74 categories, 263 distinct items, 2019-01 through 2026-01, natively ILS. `commodity_item=["__ALL__"]` bypasses category/item filters and returns the whole table in one call. 21,347 monthly rows after collapsing ~1.2% same-month duplicate quotes (WFP-style mean + count). Heavily food-weighted (fresh veg/fruit/dairy/oils/legumes/fish dominate the category breakdown) but `channel: null` since it's an official average, not a retailer. |
| `ooredoo_devices_ps` | electronics | Server-rendered Tier 1A, `.products-list__item__inner` cards | Ooredoo Palestine (mobile carrier) device store, https://www.ooredoo.ps/handsets/. Whole catalog (27 SKUs: smartphones, accessories, gaming consoles, one tablet) lives on a single page across 4 tab panels — no pagination, no separate listing endpoint. Confirmed complete (not a homepage-carousel undercount) via a sparse-ID probe and JS-bundle grep for a hidden catalog API — found neither. |

## Candidates probed and rejected

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| Jerusalem District Electricity Co. | jdeco.net | DEAD — WAF, survives all TLS profiles | 403 on curl_cffi chrome124, chrome120, AND safari17_0 — genuine block, not a TLS-fingerprint false positive. |
| Jawwal (mobile carrier) | jawwal.ps | DEAD — PerimeterX | `TSPD` cookie challenge page returned even with chrome124 impersonation; real content never reached. |
| Paltel (fixed-line/ISP) | paltel.ps | DEAD — PerimeterX | Same TSPD signature as jawwal.ps — both carriers share the PerimeterX tenant. |
| Northern Electricity Distribution Co. (NEDCO) | nedco.ps | DEAD — unreachable | Connection timeout (30s) on every protocol/path tried; not a WAF signature, the host itself did not respond. |
| Palestinian Energy Regulatory Council (PERC) | perc.ps | DEAD — parked/abandoned | Self-signed cert; body is a 2019 `Last-Modified` placeholder redirect stub referencing a generic "your-domain.fi" hosting template — classic parked-domain artifact, not a live regulator site. |
| Ministry of Finance and Planning | pmof.ps | SKIPPED — broken TLS | `unable to get local issuer certificate` even with curl_cffi; matches a pattern of broken certs on `.ps` government domains this pass. Not chased further with `verify=False` given the General Petroleum Authority's fuel-price bulletins live inside this ministry with no stable URL (monthly news-article format), and PCBS's own commodity table already carries a fuel/diesel item. |
| Palestine Monetary Authority | pma.ps | INCONCLUSIVE — thin SPA shell | Homepage is a ~6KB shell with no discoverable publication/rate links in the raw HTML; likely JS-hydrated. Not pursued with Playwright given a working PCBS win already in hand — revisit if FX/rate coverage becomes the specific ask. |
| Al Zahraa Foods | alzahra.ps | NOT A RETAILER | 200 OK, real product catalog page (`?page=products`), but zero prices anywhere on the page — this is a food *manufacturer's* B2B showcase site, not a consumer storefront. |
| Sanabel Al-Salam / Sanabel Al-Baraka | sanabel.sa, sanabel-albaraka.com | REJECTED — wrong country | Both resolve to Saudi Arabia-based hypermarket apps with the same/similar Arabic name as candidates suggested by the brief; no West Bank or Gaza presence found. Locality rule: do not build. |
| Mishwar | mishwar.ps | NOT A PRICE SOURCE | Intercity ride-share app landing page ("coming soon" on app stores) — no product/price data of any kind. |
| Talabat / Wolt | talabat.com, wolt.com | NOT OPERATING HERE | Talabat's homepage carries no mention of Palestine/West Bank cities; Wolt's country list returned 404. Neither delivery platform appears to operate in this market — not pursued further. |
| Falafel.ps / souq.ps / jawwalstore.ps / ratebplus.com | (brief-suggested leads) | DEAD — DNS | All four domains fail to resolve (`Could not resolve host`) — likely renamed, defunct, or never-existed brand guesses. |

## Dead ends worth remembering

- **Government/utility/telecom infrastructure in this market is unusually fragile for discovery purposes.** Of 6 government/utility/regulator domains tried, one was a genuine hardened WAF (JDECO), one was completely unreachable (NEDCO), one was a parked domain from 2019 (PERC), and one had a broken TLS chain (pmof.ps) — none of these are the "hardened market leader" pattern the skill's inverse-correlation law describes; they read more like under-maintained public infrastructure. Don't assume a `.ps` government 403/timeout is a WAF worth cracking — check for parked-domain and broken-cert signatures first.
- **Both Palestinian mobile carriers (Jawwal, Paltel) share one PerimeterX tenant** — cracking one likely doesn't unlock the other without real PerimeterX-grade tooling (residential proxy + browser automation), which this pass judged not worth it once a devices-store alternative (Ooredoo) was found on the SAME `curl_cffi` pass with zero blocking.
- **Ooredoo Palestine's device store is genuinely small (27 SKUs) — this is normal for a carrier handset shop, not an undercount.** Verified via ID-sparsity probe (21 IDs outside the known-good ~27, all 404) and a JS-bundle grep for a hidden catalog API (none found) before accepting the homepage tabs as the complete catalog. Worth remembering as a general check before writing off a small single-page catalog as "just the homepage carousel."
- **PCBS's CPI Dashboard is a Plotly Dash SPA whose introspection endpoints (`_dash-layout`, `_dash-dependencies`) leak the entire component tree and callback graph with no auth** — this is how the 74-category, per-item `commodity_view: "Average price"` field was found without ever touching Playwright. Worth checking for on ANY Dash-based government dashboard (`dash_renderer` in a `<script src>` is the tell) before assuming a chart-only dashboard has no queryable backend.
- **Brief-suggested brand-name leads (Sanabel, Al-Salam) can collide with same-named businesses in a different country.** Always verify the ccTLD/domain and an in-country signal before building — Sanabel Al-Salam turned out to be Saudi, not Palestinian, despite an exact name match to the brief's lead.
