# Tunisia — price source inventory (menaap/north_africa)

_Inventory written: 2026-09-01_

Cold-start inventory. Final F&B sweep, MENAAP agent B. Tunisia started this
pass at 3 food sources (`carrefour_tn`, `magik_tn`, `otrity_tn` — all
supermarket) out of 6 total. Target: add genuine new food-and-beverage
retail sources, marketplace-first discovery (no WebSearch budget left this
pass — session-wide cap already exhausted by other parallel agents, so
discovery used direct domain guesses off known Tunisian retail brand names
plus platform fingerprinting).

## Onboarded this pass

| Source | Channel | Platform | Notes |
|---|---|---|---|
| `aziza_tn` | supermarket | Bespoke JSON API (`btoc.azizacdn.com`, white-label "Zazome"-style backend but self-hosted, not the Egypt Zazome tenant) | Magasins Aziza, 350+ store chain, no online shop — public site is a weekly promo-flyer viewer. `getProducts` with no date filter returns the ENTIRE historical archive back to 2022 (18,595 items, mostly price=0) — NOT a live catalog; the site's own JS scopes every call to the current week's Wed-Tue window. Verified live: current week = 362 items, 361 priced, food (ALIMENTAIRE) share ~39.6%. `page=`/`per_page=` is the real pagination param — `offset=` is silently ignored (100% id overlap between offset=0/offset=17175 vs 0% overlap between page=1/page=2). Prices are plain TND floats, no minor-unit issue. Cold re-fetch: 3/3 products matched. |
| `geant_drive_tn` | hypermarket | PrestaShop (shared `_prestashop_base.py`, FreshFood theme) | Geant Drive Tunis City — Geant Tunisie's click-and-collect arm (geant.tn itself has no catalog, links out to this separate domain). Full hypermarket taxonomy (~100 leaf categories: epicerie, le-frais incl. fruits/legumes/boucherie/poissonnerie/cremerie, hygiene, maison, high-tech, mode, bebe, animalerie). **TND 3-decimal price trap**: the shared base's `normalize_price` mis-parsed "14,100 DT" (=14.100 TND) as 14100 TND (a 1000x error) because its heuristic treats a lone-separator + 3-digit trailing group as thousands, not decimal — correct for 2-decimal currencies, wrong for TND. Fixed via a spider-local `_items()`/`_normalize_tnd_price()` override, NOT a change to the shared base. Also fixed: the homepage root URL (`/tunis-city/`) is itself treated as a paginating "category" by the shared base's generic crawl logic, but it's actually a non-paginating featured-products widget (`?page=2/3/4` all return the identical 107-108 products) — wasted ~60 duplicate requests per run but does NOT corrupt data (DuplicationPipeline dedups on `url`, confirmed 0% overlap on REAL categories' pagination). Also fixed a `category` field bug: this theme's non-category pages (brand/manufacturer listings, the homepage) fall through `h1::text` to a shared footer "Abonnez-vous a notre newsletter" element — filtered via a junk-H1 regex, falling back to the product's own URL-slug category segment. TLS cert note: homepage cert (Sectigo DV, valid) fails curl_cffi verification because the server serves only the leaf cert, no intermediate — vendored the missing intermediate (`_geant_drive_tn_chain.pem`, fetched from the leaf's own AIA URI) rather than `verify=False`, injected via a spider-scoped downloader middleware (not a settings.py or shared-base change). Single-store scope (Tunis City only; an "Azur City" pickup point also exists on the same PrestaShop tenant, not diffed against this pass). |

## Candidates probed and rejected

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| Monoprix Tunisie | monoprix.tn / courses.monoprix.tn | DEAD — country geo-fence | `www.monoprix.tn` itself is a corporate/loyalty shell (no catalog, just a "Monoprix Smiles" loyalty widget + video). The real shop is `courses.monoprix.tn`, which returns a custom `403 Access blocked for test2` (Cloudflare-fronted) on all 3 curl_cffi profiles AND headless Playwright — genuine block per the mandatory gate, reads as an app-level geo-fence given the non-standard body text. Highest-value remaining Tunisia target given Monoprix's chain size — see `known_blockers.md`. |
| Geant Tunisie corporate site | geant.tn | Non-actionable directly, but led to the win | 200 OK once a cert-verification workaround (`verify=False`) was used — real hypermarket corporate/flyer site, but no catalog of its own. Its nav links to `geantdrive.tn`, the actual online-ordering platform — see `geant_drive_tn` above. |

## Dead ends worth remembering

- **Tunisia's real e-commerce leader (Monoprix) is the hard one** — same inverse-correlation pattern documented in Morocco's inventory: the market leader is geo-fenced/WAF-hardened, while a mid-tier operator's dedicated e-commerce arm (Geant's "Drive" click-and-collect brand, not the parent corporate domain) verified cleanly on the first probe.
- **A promo/flyer API that returns "everything ever published" by default is a trap, not a catalog.** Aziza's `getProducts` endpoint looks like a full-catalog walk (18,595 items) but is actually a historical archive of weekly circulars going back to 2022; only the current week's `oc_debut`/`oc_fin` window represents real, currently-charged prices. Always check whether a promo-style API's date parameters are FILTERS (as they were here) before assuming an unfiltered call gives you "the whole catalog."
- **TND (and LYD/JOD) 3-decimal pricing breaks 2-decimal-currency price-parsing heuristics silently, without an error.** A shared spider base's generic comma/dot decimal-vs-thousands heuristic produced a plausible-looking but wrong price (1000x too high) with zero exceptions raised — always eyeball the first extracted price against the rendered page for any 3-decimal currency (LYD, JOD, TND, BHD, KWD, OMR), even when reusing an already-proven shared base class.
- **A corporate parent domain's own homepage nav is worth checking for a separate, unrelated-looking e-commerce subdomain** (geant.tn → geantdrive.tn) even when the parent itself has zero catalog — this pattern (corporate site + separate branded ordering platform) recurs across MENAAP retailers.
