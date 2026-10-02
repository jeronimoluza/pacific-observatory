# Seychelles

_Inventory written: 2026-09-01_

Final F&B sweep, wave (2026-09), agent B. Cold-start (no prior inventory file
existed). Seychelles had **zero** manifests of any kind before this pass (0
food, 0 total).

**Result: 0 sources shipped. No viable online grocery found.**

| Candidate | URL | Status | Notes |
|---|---|---|---|
| koek.sc | https://koek.sc | **DEAD — wrong vertical** | Search surfaced this as "Supermarkets in Seychelles" (a `/merchants/supermarket` directory page), but the live site (200, Next.js) is a **tour/boat-charter booking platform** (boats, tours, livecam) with no grocery or supermarket content at all — a false-positive match from a stale/mislabeled search snippet, not a marketplace directory worth following. |
| WOW Delivery | (contact only: wowdeliverysey@gmail.com, +2482611219) | **NOT PROBED — no domain found** | Described by `insideseychelles.com` as "Seychelles Number 1 Online Supermarket." Guessed domain `wowdeliverysey.com` does not resolve (NXDOMAIN). No working URL found this pass — this is the strongest lead for Seychelles and should be the first thing the next pass runs down (find the real domain, likely Facebook/Instagram-only ordering). |
| SPAR Seychelles (Eden Plaza, Eden Island) | spar-international.com/country/seychelles | **NOT PROBED — no e-commerce found** | SPAR operates physical stores in Seychelles per the SPAR International country page; no online ordering surfaced for the Seychelles operation specifically. |

No delivery marketplace (Jumia/Glovo/Bolt/Yango-style) operates in
Seychelles. Population is small (~100k) but wealthy/tourism-driven, so a
"no online grocery" verdict is less certain here than in Comoros/Eritrea —
record this as **unresolved, not structural absence**: the WOW Delivery lead
is real and worth a dedicated re-check.

---

## UPDATE 2026-09-01 (second pass) — WOW Delivery lead CLOSED as unscrapeable

The pass above named WOW Delivery as "the strongest lead for Seychelles and the
first thing the next pass should run down". It was run down. **It is a real
business with no website.**

A dedicated search returned only: a Facebook page (`/wowdeliverysey`), an
Instagram account (`@wow_delivery`), and a Google Play app
(`com.wowdeliveries.user`). One search result surfaced an indexed
`www.wowdeliverysey.com/about` URL, but that host **does not resolve** — DNS
NXDOMAIN on both `wowdeliverysey.com` and `www.wowdeliverysey.com` via
`curl_cffi` (chrome124 and safari17_0). The indexed URL is stale; the domain the
earlier pass guessed was right, and it is dead. Ordering is app- and
social-only.

Classify under `known_blockers.md` § "App-only / no scrapeable web catalogue".
Do not re-chase this lead without evidence the app's backend is reachable — that
would need an APK teardown, which is out of scope for a discovery pass.

Seychelles remains **0 sources**. The SPAR Seychelles thread from the pass above
is still unchased and is now the best remaining lead.

---

## UPDATE 2026-09-28 (W40 pass) — 3 sources shipped, first real coverage

Country was 0 COICOP divisions / 0 sources / 0 rows before this pass. `ddgs`
sweep (14 queries, backends pinned `duckduckgo, google, brave, mojeek,
startpage, yahoo`, 99 results) plus direct re-probe of the two open leads
below. Shipped:

| Source | slug | scaffolding | analytical_role | coicop | rows (test) |
|---|---|---|---|---|---|
| GOPI Veg. Food & General Merchants (Wix Stores, Shreeji Group) | `gopi_sc` | spider (scrapy_html) | retailer_sku | wide (food/household/health&beauty) | 62 |
| PUC (Public Utilities Corp) electricity + water/sewerage tariffs | `puc_sc` | fetcher (html_scrape) | tariff | 04.5.1, 04.4.1, 04.4.3 | 32 |
| NBS Consumer Price Index Time Series | `nbs_cpi_sc` | fetcher (tabular_download) | cpi_benchmark | 01-12 (legacy COICOP-1999 grouping) | 2,820 (full Feb2007-Aug2026 backfill) |

**koek.sc** — confirmed still the same false-positive tour/boat-charter site
from the 2026-09-01 pass, not re-chased.

**WOW Delivery lead, re-opened and re-closed** — the earlier pass guessed
`wowdeliverysey.com` (NXDOMAIN) and gave up. This pass found the *real*
domain, `www.wow.sc` (site `<title>` is literally "wowdeliverysey"), via a
fresh `ddgs` sweep. It is a 200 OK landing page, but the entire site is a
promo shell with no product/category links at all — the only outbound link
on the page is the Google Play listing (`com.wowdeliveries.user`). Confirms
the 2026-09-01 verdict (app-only, no web catalogue) under the correct
domain; do not re-chase without an APK teardown.

**globuya.com ("GSC Online Store")** — flat 403 on the full `curl_cffi`
ladder (chrome124/chrome120/safari17_0/firefox133). Not re-probed further
this pass; a real Cloudflare/WAF-class block, not a bare-curl artifact.

**seybusiness.com** — a business directory ("Seychelles Directory &
E-Commerce Platform"), not a priced catalogue itself. Lists dozens of named
grocery stores, fish retailers, food & beverage distributors and general
shops under `/guide/<category>/<subcategory>/<id>` and per-business pages
at `/<Business_Name>/<id>/about`. **Not enumerated this pass** (out of
scope / time) — this is the strongest remaining lead for a future pass:
treat as a directory (per the skill's marketplace-is-a-directory rule) and
walk its seller list rather than scraping the directory pages themselves.

**Airtel Seychelles (airtel.sc)** — reachable (200) but a React SPA shell
(~7 KB static body); prepaid-plan pricing is client-rendered. Needs a
Playwright network trace to find the plans API — not chased this pass.
Cable & Wireless Seychelles / Intelvision (`cwseychelles.com`,
`intelvision.sc`) were found but not probed at all. Both are good telecom
(08.x) candidates for a follow-up.

**SEYPEC fuel prices (seypec.com/fuel-prices)** — scaffolded and tested
successfully (static Drupal page, GASOLINE/GASOIL/KEROSENE/LPG, clean
extraction), but the entire national retail fuel schedule is exactly 4 line
items — below the skill's 5-row ship gate. **Not shipped.** Hypothesis:
this is a structural ceiling (SEYPEC is the sole importer/distributor and
this is the complete retail price list), not a scraping shortfall. If the
gate is ever relaxed for single-page institutional tariffs with a small,
complete product universe, this is a ready-to-ship fetcher.

**Untried leads for next pass:** SPAR Seychelles (Eden Plaza / Eden Island)
still has no confirmed online-ordering surface (unchanged since 2026-09-01);
University of Seychelles tuition fee schedule (unisey.ac.sc, PDF, division
10 education) found but not probed; Cat Cocos inter-island ferry fares
(booking.catcocos.com / seyferry.com, division 07.3 transport) found but
not probed; Ministry of Health hospital charges (health.gov.sc) found but
not probed.

_Inventory entries above written: 2026-09-28._

---

## AMENDMENT 2026-09-28 (same W40 pass) — seypec_fuel_sc restored, now shipped

Orchestrator determined the >=5-row ship gate is meant for retailer
catalogs, not official tariff/price schedules -- a sole-importer's complete
4-item national fuel price list (Gasoline, Gasoil, Kerosene, LPG) is full
coverage, not a truncated scrape. `seypec_fuel_sc` (fetcher, tariff,
source_curated, 07.2.2/04.5.2/04.5.3) is restored and shipped at
`src/prices/fetchers/ssa/east_africa/seychelles/seypec_fuel.py` +
`src/prices/configs/ssa/east_africa/seychelles/seypec_fuel_sc.yaml`.
Re-tested clean: 4 rows (SCR24.68/L gasoline, SCR25.19/L gasoil,
SCR30.00/L kerosene normalised from a 5L pack, SCR17.50/kg LPG). The "not
shipped" verdict in the section above is superseded by this one. Seychelles
now stands at 4 shipped sources, not 3.
