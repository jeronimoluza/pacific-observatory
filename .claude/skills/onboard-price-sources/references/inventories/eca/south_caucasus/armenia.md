# Armenia

_Inventory written: 2026-09-01_

| Source name | URL | COICOP divisions covered | Source type | Cadence | Auth required? | Machine-readable? | Anti-bot risk | Wayback coverage | Per-SKU IDs? | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Parma | https://parma.am/en/ | 01-13 | Retail / e-commerce | weekly | no | HTML | low | unknown | yes | Already onboarded (`parma_am`), channel=supermarket. Pre-existing, not rebuilt this wave. |
| Vega | https://vega.am/ | 01-13 | Retail / e-commerce | weekly | no | HTML | low | unknown | yes | Already onboarded (`vega_am`), channel=dept-store (electronics-led but spans most divisions). Pre-existing, not rebuilt this wave. |
| SAS Supermarket | https://www.sas.am/ | 01-13 | Retail / e-commerce | weekly | no | HTML | low | yes | yes | **Built this wave** (`sas_am`), channel=supermarket. Custom Bitrix-style storefront, no shared base spider matches. Category list from sitemap-custom-catalog-sections.xml (627 flat categories). Root path (no locale prefix) serves Armenian names — used deliberately over /en/. Offset pagination wraps around past the last page (non-terminating) — spider stops on zero-new-ids. Time-boxed run (900s) covered 287/627 categories, 19,526 rows, ~57% food share by category. Highest-value build of the wave, per brief. |
| Supermarket.am | https://supermarket.am/ | 01-13 (food-led) | Retail / e-commerce | weekly | no | HTML | low | yes | yes | **Built this wave** (`supermarket_am`), channel=supermarket. Also Bitrix-based but a different theme/markup/id-namespace from sas_am — confirmed NOT the same shelf (only 1.7-5.5% exact product-name overlap with sas_am, mostly different prices on shared national brands, consistent with two independent competing retailers). No sitemap.xml (404) — category list scraped from homepage nav (269 links); full run completed naturally in ~12 min, 5,936 rows across 76 distinct categories (heavy parent/child category overlap in nav collapses many labels via URL-dedup), ~98% food share by category. Same offset/PAGEN wraparound trap as sas_am. |
| Food Depot | https://fooddepot.am/ | 01-13 (food+alcohol led) | Retail / e-commerce | weekly | no | JSON-API | low | yes | yes | **Built this wave** (`fooddepot_am`), channel=supermarket. Workbook flagged `SUSPECT` ("category pages did not expose prices in the fetch") because the storefront is a bare create-react-app shell with no server-rendered content — but its JS bundle calls a wide-open, unauthenticated Bagisto REST API at api.fooddepot.am. Full catalog (2,841 products / 29 pages) scraped cleanly via plain HTTP with NO wraparound trap (proper `meta.last_page`). ~84% food/beverage share by category, remainder is bar/kitchen equipment (fits the site's own "Food, Alcohol, Equipment" tagline). **Finding for the next run: a `SUSPECT` verdict from a plain HTML/curl fetch does not rule out an open API behind a JS bundle — always check the bundle before accepting a thin-HTML verdict as dead.** |
| List.am | https://www.list.am/ | n/a | Classifieds marketplace | daily | no | HTML | low | yes | yes | **Evaluated, not built.** 200 on curl_cffi probe. Not pursued: target (>=5 sources / >=2 food) was already cleared by sas_am+supermarket_am+fooddepot_am+parma_am (4 food) + vega_am. Per the workbook gotcha, user-submitted classified prices are not shelf prices and would need live-status/geography/lawful-collection verification before production use — treat as a residual candidate for a future wave if deeper Armenia coverage is wanted, not as coverage now. |
| GeraMarket | https://geramarket.com/ | n/a | Regional (AM/GE/AZ) marketplace | daily | no | HTML | low | yes | unknown | **Evaluated, not built — locality risk confirmed live.** 200 on curl_cffi probe, but the homepage carries zero AMD/֏/GEL/AZN currency signals and mentions Armenia/Georgia/Azerbaijan symmetrically (7x each) — no evidence it actually serves Armenia with AMD prices, exactly the locality risk the workbook flagged. Not pursued further since the country's target was already cleared; would need a deeper per-country page probe before onboarding in a future wave. |

Cross-region aggregators (Numbeo, Expatistan, LivingCost, WB ICP, IMF CPI, Eurostat) are not listed here per policy — see `../_aggregators.md` and the skill's anti-patterns (never count them as coverage).

## Not attempted this wave (candidates for a future pass, non-retail)

Brief-suggested `official_avg` / `tariff` / `cpi_benchmark` leads were not probed this wave because the retail-source target was cleared without them:

- ArmStat (Statistical Committee of Armenia) — CPI + average consumer prices for selected goods.
- Electric Networks of Armenia / PSRC tariff schedule (04.5.1).
- Veolia Djur water tariff (04.4.1).
- Team Telecom / Ucom / Viva-MTS mobile plan pages (tariff).

These are real, cheap coverage (no anti-bot, mostly `pandas.read_html`/PDF/API) and should be the first targets of the next Armenia pass, since they don't overlap with anything built this wave.
