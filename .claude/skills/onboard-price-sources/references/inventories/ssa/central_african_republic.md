# Central African Republic — price source inventory

_Inventory written: 2026-09-01_

Wave 13 pass. Started at 2 sources / 0 food (`fews_net`, `wfp_prices`, both
`official_avg` humanitarian-survey fetchers — CAR has zero online retail
coverage). Brief supplied 3 candidate rows, one of which (`Fallback - WFP
VAM`) is a straight duplicate of the already-onboarded `wfp_prices` and was
not rebuilt. The other two (Bangui Mall, Supermarché Prima/`warani.cf`) were
both probed and found DEAD. Built 2 new non-food fetchers this pass
(`orange_tariffs_caf`, `faostat_cpi_caf`). **Ends this pass at 4 sources / 0
food** — short of the >=5 sources AND >=2 food bar. Every avenue tried is
recorded below, including the ones that came back empty, per rule 20/the
skill's own "record dead ends as rows" instruction.

## Already covered (unchanged this pass)

| Source key | analytical_role | channel | Notes |
|---|---|---|---|
| `fews_net` (`fews_caf`) | official_avg | null | USAID FEWS NET market-price facts, shared `_shared.ssa.fews_net` |
| `wfp_prices` (`wfp_caf`) | official_avg | null | WFP food prices via HDX, shared `_shared.ssa.wfp_food_prices` |

## New this pass — both verified, both non-food

| Source key | analytical_role | channel | Rows | Notes |
|---|---|---|---|---|
| `orange_tariffs_caf` | tariff | null | 27 | Orange Centrafrique (orangerca.com) prepaid plan catalog — Sakpa/internet, Songo/national calls, international passes, recharge bonuses. Tier 1B JSON endpoint `/2/calls/getvariantprices.jsp` found via Playwright network-capture, then hit with plain `requests`. XAF, price range 50–25,000. |
| `faostat_cpi_caf` | cpi_benchmark | null | 75 | FAO's Consumer Prices, Food Indices (2015=100) for CAR, republished on HDX (`caf-faostat-food-prices`), resolved via CKAN. Monthly 2020-01–2026-03. coicop_code "01" only (General/all-items and the inflation-rate row dropped, no sentinel/not a level). |

## The 2 brief-supplied SUSPECT candidates — both DEAD

| Candidate | URL given | What's actually there | Verdict |
|---|---|---|---|
| Bangui Mall | https://www.banguimall.net/ | Resolves (200, Bootstrap template). It's a physical multi-service mall — car repair/wash, IT repair, "electricity services", "home services" verticals — not a retailer. Grepped the full site (index/about/services/car-services/I-T-services/electricity-service/home-services pages): zero occurrences of FCFA/XAF/produit/panier/catalog anywhere. No prices, no catalogue, no e-commerce — only a WhatsApp number and Facebook/Instagram links. | **DEAD — services-mall brochure site, no catalogue, no prices** |
| Supermarché Prima | https://warani.cf/ | `warani.cf` does not resolve on either 8.8.8.8 or 1.1.1.1 (NXDOMAIN). Matches the brief's own expectation for a `.cf` free-TLD domain. | **DEAD — domain does not resolve (NXDOMAIN)** |

## Non-food DISCOVER targets from the brief

| Target | What was tried | Verdict |
|---|---|---|
| **ICASEES** (national statistics office) | icasees.org resolves and is a real, substantial Joomla site (education annuaires, VBG incident reports — all genuine, human-authored `.xlsx`/`.pdf` documents with real creator names in `docProps/core.xml`, e.g. "Jean Bosco Ki"). It DOES list a monthly "IHPC Bulletin mensuel des prix des ménages" series with per-month download links going back to 2022. BUT: every individual monthly bulletin PDF checked (Jan/Apr/Jun/Jul 2025, multiple 2022–2024 months, via both URL path variants the site exposes) returns HTTP 200 with **0 bytes** — the underlying files are missing from the document manager. The site's ONE populated "master" download — `indice-des-prix-a-la-consommation-ihpc-mensuel-de-2015-2026` (plus its sibling `-annuel-par-localite-` and `-mensuel-par-localite-` files) — is **not a genuine ICASEES publication**: its `docProps/core.xml` shows `dc:creator: openpyxl`, `lastModifiedBy: hp`, created 2026-08-12T11:02Z (all 3 files share this exact signature/timestamp cluster), and its own embedded "Notes_Methodologiques" sheet narrates, in the first person, a price-index "RECONCILIATION APPLIQUEE (mise a jour) ... a la demande de l'utilisateur" ("at the user's request") — language no national statistics office would ever publish about its own official series. This reads as a script-generated reconstruction (very possibly AI-assisted) that ended up hosted where the real bulletin file should be. **Not used as a source and not used as a basis for any number in this pass** — flagging this prominently for whoever reads this file next, since it could easily be mistaken for genuine ICASEES data on a future pass. | **DEAD for this pass — real bulletins are broken (0-byte); the one populated file is untrustworthy, not government output.** Superseded by `faostat_cpi_caf` (FAO's own bulk CPI product, independently verified, food-only). |
| **ENERCA** (electricity utility) | Tried `enerca.org` (resolves via Cloudflare but 301s to `angeledenblog.com`, an unrelated spam/content-farm blog — domain has been hijacked/lapsed and repointed), `enerca.net` (resolves but is an unrelated Spanish company, "ENERCA High Tech, S.L.", solar installations in Sabadell/Catalonia — a homonym, not the CAR utility), `enerca-rca.org` (resolves to a Gandi.net parking page, "this domain name is currently parked by the owner"). No working ENERCA domain found. | **DEAD — no live ENERCA website found under any of 3 plausible domains; two are hijacked/homonym, one is parked** |
| **Orange Centrafrique** | `orange.cf` resolves but every path (including `/car`, `/cf`, `/fr`, `boutique.orange.cf`) 301-redirects to the Orange **Group** corporate site `orange.com/en` — it is NOT the CAR operator despite the ccTLD. The real operator site is **`orangerca.com`** (found via one targeted WebSearch) — live, built, onboarded as `orange_tariffs_caf` (see above). | **LIVE — onboarded as `orange_tariffs_caf`** |
| **Telecel Centrafrique** | Real domain found via WebSearch: `telecel-rca.com` (WordPress, live, `/mobile` and `/fr/mobile` pages exist with "Mobile Internet / Daily plans / Weekly plans / Monthly plans / Unlimited plans" section headers). Checked both language versions in full: **zero** occurrences of "FCFA" or "XAF" anywhere on the site — the plan pages are generic marketing copy with no prices, no PDF catalogue, no tariff table anywhere linked from the site. | **DEAD — live brochure site, but publishes no prices anywhere** |
| **Moov Africa Centrafrique** | `moov-africa.cf` (bare domain) returns HTTP 403 "Interdit: accès refusé" (an IIS default-forbidden page, not a WAF challenge — same 403 on every path tried including `/index.html`, `/fr`, `/forfaits`) on all 3 curl_cffi browser impersonations; HTTPS on the bare domain fails with `SSL certificate problem: unable to get local issuer certificate` (invalid/broken cert); the `www.` subdomain resolves to a different IP that times out entirely. `moov-africa.com` (the obvious group domain) is a Hover-parked "coming soon" placeholder, unrelated. | **DEAD — misconfigured/decommissioned server (bad cert + blanket 403) under the country domain; group domain is parked** |
| **ARCEP** (telecom regulator — checked as a possible source of a regulator-mandated tariff-catalog PDF, the pattern that worked for Orange Burkina Faso) | `arcep.cf` resolves and loads — but is an explicit "Site web en construction" (site under construction) placeholder with no content beyond a contact email. | **DEAD — regulator site is a construction placeholder** |
| **SOCASP / Ministry of Commerce** (administered fuel prices) | `commerce.gouv.cf` and `energies.gouv.cf` both resolve via the real government portal (`gouv.cf`, live Drupal 8 site, confirmed genuine — links to `administration-territoire.gouv.cf`, `mines.gouv.cf` etc. all real ministry subdomains) but both are abandoned "hosting-page-builder" **placeholder pages** with `og:updated_time` timestamps from 2018/2019 — never built out. `mines.gouv.cf` (Ministère des Mines et de la Géologie) IS a real, populated Drupal site with a "Direction Générale du Pétrole" page, but that page is pure policy/mission text (decree references, org-chart descriptions) with zero FCFA/price content — it covers petroleum-sector *policy*, not retail fuel prices. No SOCASP website found at all (no resolving domain under any plausible guess). News search (1 WebSearch call) surfaced only journalistic coverage of periodic ministerial fuel-price decrees (ecomatin.net, journaldebangui.com) — no machine-readable table, no PDF decree link surfaced in the results. | **DEAD — no online, machine-readable fuel-price table exists; only news coverage of decree announcements** |

## Other avenues tried and closed

| Avenue | What was tried | Verdict |
|---|---|---|
| Bangui supermarkets (general) | One French-language WebSearch ("supermarche Bangui achat en ligne livraison Centrafrique") surfaced 4 real physical supermarkets (Supermarché Rayan, BAMAG, CORAIL, MINI PRIX) — every one is Facebook-page-only or directory-listed (Petit Futé, mapsme.fr), no independent website for any of them. | **DEAD — no online supermarket found; matches the brief's own expectation** |
| AFRISTAT / Open Data Portal | `afristat.org` is live; its `/statistiques-des-prix/` page only links IHPC *methodology* PDFs (guides, nomenclature), no data. Its Knoema-powered data portal (`afristat.opendataforafrica.org`) does have a dedicated `/Centrafrique` country page and a "profil-centrafrique" dashboard with a demographic-indicators gadget, but the page structure suggests actual indicator values are gated behind a Knoema account (`sys/login` links present; page returns "An error occurred" in the no-JS render). Not pursued further under this pass's time-box — flagged as a possible future lead if someone wants to reverse-engineer the Knoema gadget API and confirm price/CPI indicators (not just demographic ones) are actually present and public. | **NOT PURSUED — time-boxed; possible future lead, unconfirmed whether price data is even present or public** |
| BEAC (CEMAC central bank) | `beac.int` is live. Checked the July-2026 "Statistiques mensuelles" PDF (monetary/securities-market statistics only, no IHPC/price table) and the `depief_rca.xlsx` file linked from `/economie-stats/statistiques-economiques/` (a real "RCA: Principaux indicateurs économiques" annual table — GDP growth, **annual inflation %** (a rate, not an index level), public finances). The file's `Last-Modified` header is 2019-06-18 — stale, not maintained since 2019, and inflation is reported as a % rate rather than an index level (same "not an IndexObservation row" problem as the FAOSTAT/ICASEES inflation series). | **DEAD — stale (last updated 2019), and the one price-adjacent field is a rate, not a level** |
| CoinAfrique / Jumia (marketplace-as-directory angle, rule 14) | `jumia.com/cf/` returns 403 with no real CAR storefront; CoinAfrique's CAR subdomain does not resolve. | **DEAD — neither marketplace operates a CAR storefront** |

## What this means for the food bar specifically

Every food-adjacent avenue this pass surfaced was either a Facebook-only
physical business (Bangui supermarkets) or a dead domain (Bangui Mall,
Warani). **No candidate with a `channel` in
{supermarket, hypermarket, convenience, fresh-market, specialty-food} was
found to have any web presence at all.** This matches the brief's own
framing (CAR has among the world's lowest internet penetration, effectively
no e-commerce sector) and is consistent with the Gabon wave-11 finding in
the same subregion (`gabon.md`: 5 sources / 1 food, food bar also unmet,
same pattern of Facebook-only or lapsed-domain food businesses).

## Priority order for a future pass (~6 months out)

1. Re-check `orangerca.com`'s `catalogs/forfaits-roaming.html` — uses a
   different, unwalked pricing mechanism (no `product_id` found); could be
   a quick incremental add to `orange_tariffs_caf` if it turns out to be
   the same `getvariantprices.jsp` pattern under a different catalog_id.
### ORCHESTRATOR RE-VERIFICATION 2026-09-01 — the ICASEES finding is CONFIRMED

Independently re-fetched, not taken on the agent's word. Exact URLs, so the
next pass can re-check in one command instead of rediscovering them:

- Real monthly bulletin (example): `https://icasees.org/index.php/component/edocman/ihpc-bulletin-mensuel-des-prix-des-menages-n-01-janvier-2025/download?Itemid=0`
  -> **HTTP 200, Content-Length 0, content-type text/html**. The file is gone
  from the CMS; the 200 makes it look alive to any naive checker.
- The populated "master" workbook: `https://icasees.org/index.php/publications/tableau-de-bord/indice-des-prix-a-la-consommation-ihpc-annuel-par-localite-de-2015-2026/download`
  -> HTTP 200, 23,376 bytes, and its `docProps/core.xml` reads:
      dc:creator          = openpyxl
      cp:lastModifiedBy   = hp
      dcterms:created     = 2026-08-12T11:02:05Z
  A national statistics office does not publish its official CPI series as a
  file authored by a Python library and last saved by "hp". Combined with the
  first-person "reconciliation ... a la demande de l'utilisateur" note in its
  own methodology sheet, this is a script-generated reconstruction occupying
  the slot where the genuine series should be.

**DO NOT INGEST IT.** A 200 response and a plausible-looking index series are
exactly what an automated pass would accept. CAR's CPI coverage comes from
`faostat_cpi` instead (FAO's own product, independently verified).

2. Re-check whether ICASEES has fixed its document-manager (real bulletin
   PDFs currently 0 bytes) — if the real bulletins become downloadable,
   build the genuine `icasees_ihpc_cpi_caf` fetcher then, and do NOT reuse
   the fabricated master workbook described above even if it is still the
   only thing that appears to "work."
3. Reverse-engineer the AFRISTAT/Knoema `afristat.opendataforafrica.org`
   gadget API to confirm whether CAR price/CPI indicators are present and
   public (unconfirmed this pass).
4. Re-check `moov-africa.cf` and `telecel-rca.com` for a published price
   catalogue — both are live-but-empty-of-prices today; either publishing
   a tariff PDF/page in the future would be a straightforward Bucket-1
   fetcher matching the `orange_tariffs_caf` pattern.
5. Re-check Bangui's 4 known physical supermarkets (Rayan, BAMAG, CORAIL,
   MINI PRIX) for an independent website — all are Facebook-only today.
