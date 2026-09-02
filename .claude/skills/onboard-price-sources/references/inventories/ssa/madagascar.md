# Madagascar

_Inventory written: 2026-09-01_

Wave 10 pass. Already-covered before this pass: `wfp_prices` (shared regional `official_avg`,
non-food), `leaderprice_mg` (`supermarket`, food), `mescourses` (`supermarket`, food) — 3
sources / 2 food. Target was >=5 sources AND >=2 food-and-beverage sources; food was already
satisfied, so this pass only needed 2 more sources of any channel. Entered the skill at Phase
3 with 4 pre-scouted workbook candidates (3 ACCEPT); 2 of the 3 ACCEPTs turned out to be dead
on live re-verification (see below), so the run supplemented with one cheap non-retail fetcher
build instead of chasing a 4th grocery candidate. Final: **5 sources / 3 food**.

| Source name | URL | Channel / role | Status | Notes |
|---|---|---|---|---|
| KIBO Madagascar (Tananarive) | https://www.kibo.mg/tananarive/ | `supermarket` | **SHIPPED** as `kibo_mg` | Custom PrestaShop install ("AngarTheme"), 4-store multi-boutique (only Tananarive scraped). Theme emits no schema.org microdata, so a bespoke regex-over-raw-HTML spider was written (not `_prestashop_base.py`) after CSS-selector extraction silently returned zero items on several real, card-filled pages (a parser quirk on the theme's ~700-900KB pages, not a real absence of data). Full unbounded run: 4,335 rows, 4,335 distinct product_id, 4,335 distinct url, 0 zero/negative prices, 0 blank names, 100% MGA. Food-adjacent categories (produits de grandes consommations, epicerie salee/sucree, liquide, bebe, laits) are roughly half of rows by volume; the rest is household/hygiene/stationery/small-appliance — a genuine general "cash and carry" grocery+household store, same shape as the two existing Malagasy grocers. Cold re-fetch of 3 sampled URLs confirmed identical name+price. Confirmed distinct operator from mescourses/leaderprice_mg (own PrestaShop session/token, "KIBO Tananarive" footer copyright, own TOP BUDGET private label) — no shared-backend evidence found (rule 19 check). |
| OMH (Office Malgache des Hydrocarbures) — pump fuel prices | https://www.omh.mg/index.php?page=prixpompe | `tariff`, 07.2.2 + 04.5.4 | **SHIPPED** as `omh_fuel` (`mg_omh_fuel`) | The regulator's own price-history page is JS-populated from a plain, unauthenticated JSON endpoint (`omh.mg/codes/page/prix-pompe/fetch_prices.php`) — no scraping/Playwright needed at all. 502 rows on first run, back to 2006-07-10 (141 schedule-change dates x up to 4 fuel grades), 0 duplicate `observation_hash`, 0 zero/negative prices, plausible MGA/L magnitudes (1,450-5,900). SC/GO -> 07.2.2 (petrol/diesel), PL -> 04.5.4 (kerosene); ET (a since-discontinued petrol grade) is sentinel-valued at literal `1` from 2026-01 onward and those rows are dropped rather than emitted as fake prices. |
| Supermarche.mg | https://supermarche.mg/ | would be `supermarket` | **DEAD — same backend as `mescourses`** | Workbook ACCEPT, but rule 19 applies directly: the TLS certificate served on `supermarche.mg:443` is issued for CN=`mescourses.mg` (curl fails with a cert-mismatch error on every request). This is the exact same fact the existing `mescourses.yaml` notes already recorded (supermarche.mg is the pre-rebrand domain, redirects once a matching cert/Host is presented) — re-confirmed live, not a new source. See `known_blockers.md`. |
| Bazariko.mg | https://bazariko.mg/ | would be `supermarket` | **DEAD — freelancer portfolio template, no real catalog** | Workbook ACCEPT with `AI_NOTES` claiming "STRONG: Ar prices with strike-through promotions, full supermarket taxonomy, 24/7" — does not match the live site. 200 OK but the whole domain is a static, unmodified Bootstrap e-commerce template (`single.html`/`offer.html`/`hold.html` demo filenames), zero product cards, zero prices, zero `Ar`/`MGA` text anywhere. Footer links to `fanoela.mg`, a freelance developer's portfolio listing dozens of near-identical demo storefronts — this is one of that developer's unlaunched template builds, not an operating grocery store. See `known_blockers.md`. |
| GOPLUS Madagascar | https://goplus.arato.mg/ | — | **NOT PROBED (not needed)** | P4 surplus / `SUSPECT` in the workbook — catalogue reported to skew electronics/school-supplies, and the `arato.mg` parent domain is a possible shared-tenant platform (same rule-19 risk class as the two dead candidates above). Target was already reached without it; left for a future pass if non-food coverage is wanted. |
| INSTAT Madagascar (IPC/CPI + market bulletins) | instat.mg | `cpi_benchmark` / possible `official_avg` | **NOT PROBED (not needed)** | Brief-suggested non-retail lead (Madagascar has zero CPI coverage today). Homepage confirmed live (5.4MB, heavy). Not investigated this pass — target was reached via KIBO + OMH first. Real gap for a future pass. |
| JIRAMA (water + electricity utility) | https://www.jirama.mg/ | `tariff`, 04.4.1 + 04.5.1 | **PROBED, NO TARIFF PAGE FOUND (this pass)** | WordPress site, mostly procurement notices (appels d'offres) and financial/environmental-audit PDFs under `/documents/`. No tariff schedule (grille tarifaire) found in the nav or the documents listing within the budget spent. Genuine sourcing gap, not a wall — worth a second look with a more targeted search (e.g. a Décret/Arrêté gazette notice) rather than the site's own document library. |
| Telma / Orange Madagascar / Airtel plan pages | — | `tariff` | **NOT PROBED (not needed)** | Brief-suggested non-retail lead; not investigated this pass. |

## COICOP / channel gap after this pass

Madagascar now has 3 food sources (all `supermarket`) plus one `official_avg` (WFP food
prices) and one `tariff` (OMH fuel: petrol/diesel/kerosene). Genuine remaining gaps for a
future pass:

- **CPI benchmark (all divisions)** — INSTAT's site is live but unprobed; Madagascar has
  zero `cpi_benchmark` coverage.
- **Electricity + water tariff (04.5.1 / 04.4.1)** — JIRAMA's own WordPress site does not
  publish a tariff schedule in an easily discoverable location; try a Malagasy government
  gazette (Journal Officiel) search for the rate-setting Décret/Arrêté instead.
- **Telecom tariff** — Telma/Orange/Airtel plan pages not probed this pass.
- **GOPLUS Madagascar** (goplus.arato.mg) — spare P4 lead, not probed; possible rule-19
  sibling risk with the `arato.mg` parent tenant if pursued later.
