# Mauritius

_Inventory written: 2026-09-01_

Wave 10 pass. Already-covered before this pass: `scotthomedelivery_mu`, `dodomarket_mu`,
`mantrafoods_mu` (all `specialty-food`), `votrepoteage_mu` (`fresh-market`) — 4 sources / 4
food. Target was >=5 sources AND >=2 food-and-beverage sources; this pass needed only 1 more
of any channel, but the brief flagged there was no mainstream supermarket and no non-retail
source at all, so this pass aimed higher: 3 new sources shipped (1 hypermarket, 2 non-retail
fetchers). Final: **7 sources / 5 food**.

| Source name | URL | Channel / role | Status | Notes |
|---|---|---|---|---|
| Winner's | https://www.winners.mu/ | `hypermarket` | **SHIPPED** as `winners_mu` | nopCommerce storefront, server-rendered category pages, no WAF. 268 leaf categories via the mega-menu's `lastLevelCategory` markers. Full unbounded run: 13,124 items, 0 duplicate product_id/url, food share ~51% by row count (general merchandise + full grocery range). |
| Statistics Mauritius — monthly CPI | https://statsmauritius.govmu.org/Pages/Statistics/Monthly/Monthly-CPI.aspx | `cpi_benchmark` | **SHIPPED** as `statsmu_cpi` | 13-division COICOP-2018 sub-indices, clean text-extractable PDF releases. Only the current-year listing page is walked (7 PDFs for 2026); the separate "Archive Collections 2014-2025" page (145+ PDFs) mixes a differently-shaped "Core inflation" bulletin with the main release under inconsistent filenames across a decade — historical backfill from that archive is a documented follow-up, not attempted. |
| CEB (Central Electricity Board) | https://ceb.mu/customer-corner/electricity-tariffs-and-applicable-rates | `tariff`, 04.5.1 | **SHIPPED** as `ceb_electricity_tariff` | Residential block tariff (12 bands), from the clean CEBTARIFFS.pdf (effective Feb 2024). A newer Government Gazette revision (effective 1 May 2026, up to +15%) exists but its PDF has no usable text layer — see `known_blockers.md`. Documented gap, not silently absorbed. |
| CWA (Central Water Authority) | https://cwa.govmu.org/cwa/?page_id=794 | `tariff`, 04.4.1 | **PROBED, DEAD (this pass)** | "Tariffs and Charges" page links only one-off connection-fee regulations (not the recurring consumption tariff) plus a 2026 amendment PDF that is image-only. No machine-readable per-cubic-metre water tariff found. Genuine sourcing gap for a future pass — see `known_blockers.md`. |
| STC (State Trading Corporation) — fuel/LPG | stc.intnet.mu | `tariff`, 07.2.2 | **DEAD — unreachable** | DNS resolves but both HTTP and HTTPS time out with no handshake. No alternate domain found. See `known_blockers.md`. |
| Mauritius Telecom / Emtel / Chili | myt.mu / emtel.com / chilimobile.mu | `tariff` | **NOT PROBED PAST DNS** | myt.mu and emtel.com both resolve/200 and were not probed further this pass (budget went to CEB/CWA/STC/StatsMU first). chilimobile.mu does not resolve (`NXDOMAIN`). Open lead for a future pass. |
| Super U Mauritius | https://www.superu.mu/ | would be `supermarket` | **DEAD — no online catalogue** | Drupal corporate/brochure site (French UI). Every shop-like path tried (`/fr/nos-produits`, `/produits`, `/shop`, `/boutique`) 500s. No e-commerce backend exists. |
| Way Supermarket | https://www.waysupermarket.mu/ | would be `supermarket` | **DEAD — no online catalogue** | WordPress/Yoast site, 200 OK, but WooCommerce Store API (`/wp-json/wc/store/v1/products`) 404s — WooCommerce is not installed/active. No other catalog endpoint found. Brochure-only. |
| King Savers | https://kingsavers.mu/ | would be `supermarket` | **DEAD — site down** | WordPress "undergoing maintenance" placeholder, HTTP 200. Re-check in a future pass — this may be transient. |
| Dreamprice | https://dreamprice.mu/ | would be `supermarket` | **DEAD — Cloudflare challenge** | `cf-mitigated: challenge`, HTTP 403 across `chrome124`/`chrome120`/`safari17_0`. See `known_blockers.md`. |
| Intermart | intermart.mu (and `www.` variant) | — | **DEAD — no domain** | `NXDOMAIN` against both `8.8.8.8` and `1.1.1.1`. No online presence found under this name for Mauritius. |
| Jumbo Score | jumboscore.mu | — | **DEAD — no domain** | `NXDOMAIN` against both `8.8.8.8` and `1.1.1.1`. |
| Way Supermarket variant guesses (wayonline.mu, way-supermarket.mu) | — | — | **DEAD — no domain** | Both `NXDOMAIN`; the real domain is `waysupermarket.mu` (see above, dead for a different reason — no catalog). |

## COICOP / channel gap after this pass

Mauritius now has 5 food sources (4 specialty/fresh-market + 1 hypermarket) plus a CPI
benchmark and one tariff (electricity). Genuine remaining gaps for a future pass:

- **Water tariff (04.4.1)** — CWA's site does not currently publish a machine-readable
  consumption tariff; worth re-checking periodically, or searching for the schedule via
  the Utility Regulatory Authority (URA) instead of CWA directly (URA approves CEB's
  tariff too, per the CEBTARIFFS.pdf header — it may host CWA's schedule the same way).
- **Fuel/LPG tariff (07.2.2)** — STC's own domain is unreachable; worth searching for
  whether the Ministry of Energy or a Government Gazette notice publishes the same
  Schedule-1 retail petroleum prices STC sets, since Gazette notices are how CEB's
  revisions are published too.
- **Telecom tariff** — Mauritius Telecom / Emtel plan pages were not probed this pass
  (myt.mu and emtel.com both resolve and 200); open lead.
- **Historical CPI backfill (2014-2025)** — Statistics Mauritius's archive exists but
  needs a more tolerant filename/format parser (inconsistent month abbreviations, a
  separate "Core inflation" bulletin mixed in) than this pass's current-year-only walker.
