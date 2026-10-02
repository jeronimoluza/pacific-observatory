# Djibouti — price source inventory (menaap/north_africa)

_Inventory written: 2026-09-01_

Cold-start inventory. Final F&B sweep, MENAAP agent B. Djibouti started
this pass at 3 food sources (`ahado_express_dj`, `djibonline_dj`,
`nirigs_dj` — all supermarket, WooCommerce, re-verified live as recently
as 2026-08-06/07) out of 5 total, with **zero other-retail sources** —
Djibouti is a genuinely thin market (population ~1M). All three existing
food sources are already well-documented (see their own YAML `notes:`
fields, updated within the last month). **No new food-and-beverage source
was shipped this pass.**

## Onboarded this pass

None.

## Candidates probed and rejected

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| LIMO Djibouti | limoo.online / limodjibouti.com | Investigated, no split taken this pass | A real, live delivery marketplace ("the largest marketplace in Djibouti") running on **Hyperzod**, a hosted multi-tenant delivery-marketplace SaaS platform (same category as Sixam-Mart/6amMart — new platform name for this repo, not yet in `platform_fingerprints.md`). Open unauthenticated JSON API found via Playwright network trace: `api.hyperzod.app/store/v1/*` with `x-tenant: 6966` header (tenant id embedded in CDN image paths, e.g. `cdn-upload.hyperzod.app/public/6966/...`). `POST /store/v1/home` with a Djibouti-city lat/lng returns a real merchant list (confirmed via curl_cffi, no auth needed) filterable by `merchant_category_ids`. The one food-and-beverage category — "Supermarché & Alimentaire" (id `692d82ebe77942b6f60a1be7`) — has only 2 merchants in the ~20-merchant "nearby" listing captured: a genuine fresh-fish shop ("Poissonnerie de Machallah") and a wellness/detox store ("DJIB-NATURE DETOX"), no actual supermarket. Per-merchant product-listing endpoint was not found within budget (guessed REST paths all 404'd; SPA client-side routing bounces direct deep-links back to `/fr/home`, and simulated card clicks were blocked by a location-confirmation overlay that didn't dismiss cleanly). Likely too thin to clear the >=5-rows bar even if the endpoint were found (a single fishmonger's catalog). Worth a future pass with more Playwright-interaction budget if Djibouti's food gap is revisited, but not a strong lead. |

## Dead ends worth remembering

- **Djibouti's grocery e-commerce sector may genuinely be exhausted at 3 supermarket sources** — the three existing sources (Ahado Express, Djibonline, Nirigs) were all re-verified live within the last month by a prior pass, and this pass's one fresh lead (LIMO/Hyperzod) turned up a food category with essentially one real merchant (a fishmonger). Given the country's tiny population, this may be a genuine structural ceiling rather than a search-phrasing miss — but has not yet been verified with two independent passes the way Libya has, so don't yet treat it as fully settled.
- **A "largest marketplace in Djibouti" claim does not mean deep food coverage** — LIMO's own food category is thinner than a single WooCommerce grocery site; the marketplace-directory technique (split into first-party merchants) only pays off when the category actually HAS multiple real food merchants, which it does not here.
- **Hyperzod is a new platform fingerprint for this repo** — a hosted delivery-marketplace SaaS with a consistent `api.hyperzod.app/store/v1/*` REST surface keyed by an `x-tenant` header (tenant id findable in any `cdn-upload.hyperzod.app/public/<tenant_id>/...` asset URL) and a Wed-Tue-unrelated but similarly structured `POST /store/v1/home` merchant-discovery call gated on `user_location`. Worth adding to `platform_fingerprints.md` if a second Hyperzod tenant turns up elsewhere in a future MENAAP/SSA pass.

## Pass 2 (2026-09-28, w40)

w40 brief: Djibouti started this pass at 1 COICOP division (01, food-and-
beverage/staples) across 5 manifests / 6 covered domains (ahado_express_dj,
djibonline_dj, nirigs_dj retailer_sku; instad_ipc_bulletin official_avg;
wfp_prices official_avg — `second_surface_check.py` counts 6 domains because
`instad_ipc_bulletin`'s notes reference `docs.google.com` and
`wfp_prices` references `data.humdata.org` alongside their primary hosts).
Ran `second_surface_check.py --config-dir src/prices/configs/menaap/
north_africa/djibouti`: 0 second-surface hits, 1 same-surface re-find
(djibonline.com), 5 domains with no platform fingerprint — no free lead
there this pass.

Retail/food discovery was **not** re-attempted: the prior pass's Hyperzod/
LIMO lead (one real fishmonger, no supermarket, in the food category) is
only 27 days old and the "genuine structural ceiling at 3 supermarket
sources" hypothesis from that pass was not re-tested. Given the brief's
explicit division-ordering ("food 01 first if missing, then 02, 04, 07,
08...") and 01 already covered, this pass went straight to institutional
verticals (utility / telecom / education), per discover.md Phase 2 generator
5, since Djibouti's tiny population makes these disproportionately likely to
matter (cf. American Samoa: 15 of 21 shipped sources were institutional).

**Onboarded this pass (3 sources, opening divisions 04, 08, 10):**

| Source | URL | analytical_role | Verified |
|---|---|---|---|
| `onead_water_dji` | journalofficiel.dj (Arrete n2014-738/PR/MAEPE-RH) | tariff | 42 rows, all numeric, 0 hash collisions. 3 subscriber classes (Domestique/Etat, Commercial, Industriel) x 7 consumption tranches x 2 columns (eau seule / eau+assainissement). coicop 04.4.1 / 04.4.3. |
| `djtelecom_fixed_dji` | djiboutitelecom.dj/internet/ | tariff | 5 rows (exactly at the ≥5-rows gate), 0 hash collisions after a fix (see below). Fixed-line install fees (3 tiers) + prepaid package (2 tiers). coicop 08.3.1. |
| `lfd_tuition_dji` | lfdjibouti.org (Reglement financier 2025-26, PDF) | tariff | 16 rows, all numeric, 0 hash collisions. 12 tuition rows (4 grades x 3 nationality tiers) + 4 flat admin/SIA fees. coicop 10.1 / 10.2 / 10.6. |

**Bug found and fixed during scaffolding:** `djtelecom_fixed_dji`'s two
"RÉGIONS"-labelled price tables (one under the installation-fee section, one
under the prepaid-package section, different prices) produced an identical
`item_name` and therefore an identical `observation_hash` despite carrying
different prices — a silent future-dedup collision. Fixed by prefixing
`item_name` with the price table's preceding `<h2>` section title before
shipping. Worth generalizing as a lint: **any HTML-scrape fetcher building
`item_name` from a repeated per-tier label (RÉGIONS/DJIBOUTI-VILLE-style
tiering across multiple sections) needs the section disambiguated in, not
just the tier label.**

## Dead ends found this pass (record so the next run doesn't repeat them)

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| Électricité de Djibouti (EDD) | edd.dj | DEAD — TCP-level unreachable | Both `curl_cffi` (chrome124, firefox133) and a raw IP `curl -4` to `196.201.197.226:443` time out after 10-45s — a real TCP connect timeout, not a TLS/WAF fingerprint block (confirmed via the mandatory two-lever gate). DNS resolves fine. This is the natural next division-04 electricity-tariff source if it ever comes back; ddgs found the exact arrete text (`arrete-n83-0208-pr-edd...`) is also indexed on journalofficiel.dj, same platform as the ONEAD source shipped this pass — worth trying that route directly in a future pass instead of edd.dj itself. |
| ONEAD (own domain) | onead.dj | DEAD — parked/misconfigured | Resolves, but SSL cert doesn't match the hostname and (with verify disabled) the page served is a bare Plesk hosting-panel default page ("Maroc Cloud Plesk Hosting"), not the real site. The ONEAD water tariff was recovered instead via the government gazette (journalofficiel.dj) — see onboarded sources above. |
| Djibouti Port Authority | portdedjibouti.com | DEAD — DNS NXDOMAIN | `Could not resolve host`. Port cargo/vessel tariffs are also arguably out-of-scope for a household PPP basket (commercial freight, not consumer transport) even if reachable. |
| Hopital Al Shifa (private hospital) | hopital-alshifa.dj | DEAD — no published prices | Live marketing site (about/charter/contact/leadership/patients/specialties), no tariff/consultation-fee page in the nav and no DJF/FDJ figures anywhere in the HTML. |
| ESIG (private business school) | esig-djibouti.com/index.php/inscription/frais-de-scolarite/ | DEAD — template placeholder | Live 200 page at exactly the right URL ("frais-de-scolarite"), but the fee section is still unfilled template text ("Lorem et Lorem, est offert a tous les etudiants..."), no real DJF figures anywhere. Worth a re-check in a future pass in case the template gets filled in. |
| Universite de Djibouti (public university) | univ.edu.dj/?page_id=6289 | DEAD — no fee table | Live page, but it is a BAC-2025 admissions-calendar announcement (dates only), not a tuition schedule. Public university tuition may simply not be published this way (subsidized/nominal fees are common for public universities in the region) — not yet confirmed either way. |
| Djibouti Telecom — mobile plans | djiboutitelecom.dj/mobile/, /pro/ | Not pursued — no scrapeable prices | Both pages return HTTP 200 but contain zero `.elementor-price-table` widgets and zero DJF/FDJ price text anywhere in the raw HTML (checked directly, not just visually) — pricing is presumably image-based or app-only. Only `/internet/` (fixed-line) had real priced tables. |

**Discovery-tooling note:** `ddgs` on a8 was rate-limited mid-pass (shared
IP with concurrent workers) — `duckduckgo`/`google`/`brave`/`mojeek`/
`startpage` all returned connection errors or 0 results for several
queries; pinning `backend="yahoo"` alone got real results again
(e.g. the LFD tuition lead). Treat any 0-result query from this pass's
early queries (water/hospital/university, first attempt) as **inconclusive
from rate-limiting, not confirmed absence** — they were successfully
re-queried later with a narrower backend list.
