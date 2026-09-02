# Congo, Rep. (Congo-Brazzaville)

_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 pass, which ran with **zero** WebSearch budget)

Before this pass: `wfp_prices` only, 0 retail sources. **Result: 1 shipped,
plus three diaspora storefronts deliberately NOT shipped — see the currency
note, which is the important finding in this file.**

## Shipped

| Source name | URL | Channel / role | Status | Notes |
|---|---|---|---|---|
| `mbote_cg` | https://www.mbote.shop/ | marketplace / `retailer_sku` | **SHIPPED** | Congolese marketplace serving Brazzaville and Kinshasa; `sitemap.xml` holds 448 URLs of which **356 are `/p/` product pages**. PDP JSON-LD prices in **XAF** — Congo-Brazzaville's currency (Kinshasa/DRC transacts in CDF), so rows are attributed to `congo_rep`. Test run scraped 7 items: XAF 16,800 handbag (~US$28), XAF 76,000 projector (~US$126). Mostly general merchandise. |

## NOT shipped — diaspora storefronts priced in EUR

**This is the trap to remember for the whole Francophone-Africa sweep.** Three
of the four live candidates a French-language search returns for Congo are
"send groceries home to your family" services aimed at the diaspora. They have
real catalogs, real product names and real prices — and those prices are
**EUR prices paid by a sender in France**, not what a consumer in Brazzaville
pays. Shipping them as Congolese retail sources would corrupt any PPP or
real-exchange-rate comparison built on this corpus.

| Candidate | URL | Platform | Why not shipped |
|---|---|---|---|
| 242 MARKET | https://242market.com/ | PrestaShop-style `/NNNNNNN-slug.html`, 533 sitemap URLs | Genuinely attractive on the surface — it carries **fresh produce**, which is exactly the structural gap retail supermarkets never fill (gombo, ngai ngai, épinard, tomate grappe, bananes plantains). But the PDP prices in EUR: "Tomate Grappe SALADE Le tas" is **€1.99**, `itemprop="price" content="1.99"`, zero XAF/FCFA tokens on the page. Diaspora-facing. |
| Tchitunga | https://tchitunga.com/ | WooCommerce, **Store API open and working** | Store API returns `currency_code: "EUR"`, `currency_minor_unit: 2` (e.g. 8000 → €80.00) with food categories ("Boisson"). Technically the easiest source in this whole run to onboard, and still wrong to attribute to Congo. Its own homepage describes it as a platform "pour la diaspora congolaise". |
| BantuDelice | https://bantudelice.cg/ | Live, no price markup found | Prepared-meal delivery (20–40 min) in Brazzaville/Pointe-Noire, not grocery retail. |

If a future decision is made to track the diaspora-remittance channel as its
own analytical layer, 242market and Tchitunga are both ready to onboard and
Tchitunga needs no HTML parsing at all. They should not land under
`congo_rep` retail.

## Dead ends (carried forward, and one resolved)

| Candidate | Status | Notes |
|---|---|---|
| "Douka" grocery app | **STILL UNRESOLVED** | The 2026-09-01 file flagged this as its biggest open thread. This pass did not resolve it either — no domain and no Play Store listing surfaced in the French-language search. Genuinely unverified, still not disproven. |
| Jumia `jumia.cg` | **DEAD** | Cloudflare challenge on a domain outside Jumia's active market list. |
| Glovo `glovoapp.com/cg/` | **DEAD — 404** | Carried forward. |
| Casino / Score, Park'n'Shop, Regal | **NO ONLINE STORE** | Real physical chains in Brazzaville/Pointe-Noire/Dolisie per trade press; no e-commerce domain found. |

## Next steps

- Park'n'Shop / Regal are the largest physical chains with no domain found —
  a targeted French search for those two brand names is the best shot at a
  genuinely XAF-priced second source.

## Common Crawl coverage

Probed 2026-09-02 by the common_crawl session: 8 crawls spanning 2019-2026,
`max_blocks=40`. Counts are host records in the CC index and, separately, the
subset matching the manifest's `archive_path_re`.

| Source | Crawls with host | Host records | Matching PDP regex | Verdict |
|---|---|---|---|---|
| `mbote_cg` (WooCommerce, sitemap walk) | 4/8 | 575 | 304 | Good. |


`archive_prefix` on `mbote_cg` was shortened to the bare registrable host on
2026-09-02. It is a plain **string** prefix applied to cdx lines *before*
`archive_path_re` is consulted, so a path in the prefix hard-caps what any regex
can see, and a wrong one fails silently — no manifest, no miss record, no error.
Filtering is `archive_path_re`'s job. Over-inclusion is free (`surt_prefix`
rstrips the trailing slash regardless), and a bare host survives the URL-scheme
migrations that break path prefixes.
_Inventory written: 2026-09-01_

SSA sweep, agent A. Country had only `wfp_prices` (shared regional HDX
fetcher) before this pass — 0 retail sources. **Result: 0 sources shipped.**
**This pass ran with zero WebSearch budget** (the session-wide cap was
exhausted before this country's turn) — every candidate below was found via
direct domain probing (`curl_cffi impersonate=chrome124`) and WebFetch on
directory/search-engine pages, not a real search sweep. Treat this inventory
as a weak/partial pass, not an exhaustive one — a future run with search
budget should redo Phase 2 properly before concluding Congo-Brazzaville has
no online grocery sector.

## Dead ends

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Jumia | jumia.cg | **DEAD — Cloudflare challenge / no real storefront** | Returns a Cloudflare "Just a moment…" page (403), consistent with a squatted/reserved domain rather than live Jumia infrastructure — Jumia's current active market list does not include Congo-Brazzaville. |
| Glovo | glovoapp.com/cg/ | **DEAD — 404, no CG route** | |
| "Douka" (grocery-delivery app, named in the task brief as a lead worth checking) | douka.cg, doukacongo.com, douka-congo.com, douka.app, mydouka.com | **NOT CONFIRMED TO EXIST** | None of the guessed domains resolve (NXDOMAIN). A Google Play Store search for "douka congo" surfaced no matching app (returned unrelated results: Congo Travel, Congo Ndaku, Congosa, Congo Easy). This candidate could not be verified without WebSearch and should be re-checked properly next pass rather than assumed real or assumed dead. |
| Congo Easy (delivery app) | congoeasy.com | **UNREACHABLE this pass** | HTTP 509 (bandwidth exceeded) on the one probe attempt; not retried. Play Store listing exists ("Jj Group Company") but scope (courier vs. grocery) not confirmed. |
| Congosa | — | **NOT PURSUED — appears to be a taxi/parcel courier app, not grocery retail** | Surfaced only via the Play Store search snippet above; not independently probed. |
| Simba Supermarché | simbasupermarche.cg, simba.cg | **NOT FOUND** | Neither guessed domain resolves. |

**Conclusion:** No viable food-and-beverage retail source confirmed this
pass. Unlike Chad/Guinea-Bissau/Niger/Gambia/Liberia below, this country's
dead ends are especially weak evidence (zero real search queries ran) — the
"Douka" lead in particular is unresolved, not disproven.
