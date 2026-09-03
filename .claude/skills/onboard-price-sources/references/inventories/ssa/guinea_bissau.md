# Guinea-Bissau

_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 zero-budget pass)

Before this pass: `wfp_prices` only, 0 retail sources. **Result: 1 shipped.**
The prior pass ran with zero WebSearch budget and explicitly asked for a
Portuguese-language search; that search immediately found the country's own
self-described first online supermarket.

## Shipped

| Source name | URL | Channel / role | Status | Notes |
|---|---|---|---|---|
| `ikuma_gw` | https://www.ikuma.online/ | supermarket / `retailer_sku` | **SHIPPED** | "1º Supermercado Online da Guiné Bissau". WooCommerce with **761 product URLs** in `product-sitemap.xml`. Test run scraped 7 items; prices sane against XOF (Água com Gás 250, aftershave 2,250, an upright freezer 375,000 ≈ US$620). Groceries and general merchandise both present, so `coicop_codes` is left unset for the classifier. |

### Two traps this source carries

1. **Store API is half-broken.** `/wp-json/wc/store/v1/products` returns
   **HTTP 500** on every variant tried (`per_page`, `page`, the older
   `wc/store` namespace), while `/products/categories` returns 200 with 140
   categories. A Store-API probe that only checks the categories route would
   wrongly conclude the API works. The spider uses the sitemap instead.
2. **JSON-LD emits a placeholder currency.** PDP JSON-LD carries
   `priceCurrency: "ABC"`, which is not a currency at all. The manifest forces
   `XOF` via the spider's `FORCE_CURRENCY`. Anything trusting the page's own
   currency code here would emit garbage.
_Inventory written: 2026-09-01_

SSA sweep, agent A. Country had only `wfp_prices` (shared regional HDX
fetcher) before this pass — 0 retail sources. **Result: 0 sources shipped.**
**This pass ran with zero WebSearch budget** (session-wide cap exhausted
before this country's turn) — every candidate below came from direct domain
probing and one WebFetch on a directory page, not a real search sweep.
Treat as a weak/partial pass; re-run Phase 2 with search access before
concluding Guinea-Bissau has no online grocery sector.

## Dead ends

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Bissau Online Market | https://bissauonlinemarket.com/ | **NO CATALOG API** | Live 232KB WordPress/WooCommerce-flavoured page but the Store API 404s and no price markup was detected on the homepage. Described in search results as a free classifieds/advertising platform rather than a retailer — likely seller-authored listings even if a catalog is found. Low priority. |
| SPAR Guiné (Bissau) | facebook.com/sparguine | **FACEBOOK-ONLY** | Real SPAR franchise presence in Bissau with no independent domain found. |
| Jumia | jumia.gw | **DEAD** | Carried forward: Cloudflare "Just a moment…" on a domain not in Jumia's active market list. |
| Casa Alberto | casaalberto.com | **PARKED** | Carried forward. |
| Kalliste Bissau | kalliste.gw | **NXDOMAIN** | Carried forward. |

## Next steps

- Re-check whether Ikuma's Store API 500 is ever fixed; a working API would be
  much cheaper than 761 PDP fetches.

## Common Crawl coverage

Probed 2026-09-02 by the common_crawl session: 8 crawls spanning 2019-2026,
`max_blocks=40`. Counts are host records in the CC index and, separately, the
subset matching the manifest's `archive_path_re`.

| Source | Crawls with host | Host records | Matching PDP regex | Verdict |
|---|---|---|---|---|
| `ikuma_gw` (WooCommerce, sitemap walk) | 5/8 | 1017 | 797 | Good. |


`archive_prefix` on `ikuma_gw` was shortened to the bare registrable host on
2026-09-02. It is a plain **string** prefix applied to cdx lines *before*
`archive_path_re` is consulted, so a path in the prefix hard-caps what any regex
can see, and a wrong one fails silently — no manifest, no miss record, no error.
Filtering is `archive_path_re`'s job. Over-inclusion is free (`surt_prefix`
rstrips the trailing slash regardless), and a bare host survives the URL-scheme
migrations that break path prefixes.
| Jumia | jumia.gw | **DEAD — Cloudflare challenge / no real storefront** | Same "Just a moment…" 403 pattern as jumia.td/jumia.cg; Jumia's active market list does not include Guinea-Bissau. |
| Casa Alberto (Bissau) | casaalberto.com | **DEAD — parked domain** | Resolves 200 but is a bare client-side redirect stub (`window.location.href="/lander"`), no content. |
| Kalliste Bissau | kalliste.gw | **NOT FOUND — NXDOMAIN** | |
| goafricaonline.com Guinea-Bissau directory | goafricaonline.com/gw, /gw/annuaire | **INCONCLUSIVE** | Both pages return HTTP 200 but the category/listing structure appears to be client-side rendered — no supermarket/food category links were recoverable from the static HTML via regex. Would need a JS-capable fetch to actually browse this directory; not attempted this pass. |
| Le Ninho Bissau, Bijagos supermercado | — | **NOT FOUND** | No resolvable domain found for either name; not chased via search (budget exhausted). |

**Conclusion:** No viable food-and-beverage retail source confirmed this
pass, but confidence is low given no real search ran. Re-check with fresh
WebSearch budget, particularly for Portuguese-language local terms
("supermercado Bissau online", "compras online Guiné-Bissau") which this
pass could not run.
