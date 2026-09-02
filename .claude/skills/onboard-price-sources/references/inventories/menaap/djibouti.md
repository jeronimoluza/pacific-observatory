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
