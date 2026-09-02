# Chad

_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 partial pass)

Before this pass: `wfp_prices` only, 0 retail sources. **Result: 1 shipped.**
The source was already identified by the previous pass but rejected for being
non-food; it is onboarded now that non-food sources are in scope.

## Shipped

| Source name | URL | Channel / role | Status | Notes |
|---|---|---|---|---|
| `tchadcommerce_td` | https://tchadcommerce.com/ | marketplace / `retailer_sku` | **SHIPPED** | General vendor marketplace in N'Djamena on WooCommerce. **Store API is open and healthy** — `per_page`/`page` both work, reports `currency_code: XAF` with `currency_minor_unit: 0` (prices need no division). Test run scraped the **whole catalog: 28 items** in one request; XAF 12,500 backpack (~US$20), XAF 10,000 furniture-moving tool — sane. 28 categories led by fashion, solar equipment, home goods and vehicles; "AgroAlimentaire" holds only a handful of items. Small but real, and it is the first retail source of any kind for Chad. |

## French-language search: run, and it came back empty for grocery

A proper French-language search (`supermarché en ligne livraison courses
N'Djamena`) was run this pass — the lever the 2026-09-01 file asked for. It
returned **only directory listings and Facebook pages**: Modern Market, Dembé
Market, Le Grand Marché, Marché de Diguel, Alimentation "La Tchadienne", Le
Bon Marché, Moursal Market. No e-commerce storefront for any of them. This
converts Chad's grocery gap from "unexamined" to a **searched negative**: the
online grocery sector, if any, is Facebook-page storefronts with no
independent catalog or checkout.

## Dead ends (carried forward)

| Candidate | URL | Status |
|---|---|---|
| Modern Market Tchad | facebook.com/Modernmarkettchad | **FACEBOOK-ONLY** (`modernmarkettchad.com` NXDOMAIN) |
| Le Bon Marché | facebook.com/lebonmarcheNDJ | **FACEBOOK-ONLY** (`lebonmarche.td` NXDOMAIN) |
| N'Djamena Mall | ndjamenamall.com | **PARKED** |
| Jumia | jumia.td | **DEAD** — Cloudflare challenge, Chad not in Jumia's market list |
| Sahil Express | sahil-express.com | **RESTAURANT DELIVERY**, not grocery |
| Score Tchad, Casino N'Djamena, Alwatanya, Ramco, SODEA, Sonasut | — | **NO DOMAIN FOUND** |

## Next steps

- Chad's grocery gap now looks structural rather than search-limited. Treat a
  future grocery pass as low-yield; re-check only on the standard ~6-month
  staleness window.

## Common Crawl coverage

Probed 2026-09-02 by the common_crawl session: 8 crawls spanning 2019-2026,
`max_blocks=40`. Counts are host records in the CC index and, separately, the
subset matching the manifest's `archive_path_re`.

| Source | Crawls with host | Host records | Matching PDP regex | Verdict |
|---|---|---|---|---|
| `tchadcommerce_td` (WooCommerce Store API) | 4/8 | 256 | 47 | Thin but real. |


`archive_prefix` on `tchadcommerce_td` was shortened to the bare registrable host on
2026-09-02. It is a plain **string** prefix applied to cdx lines *before*
`archive_path_re` is consulted, so a path in the prefix hard-caps what any regex
can see, and a wrong one fails silently — no manifest, no miss record, no error.
Filtering is `archive_path_re`'s job. Over-inclusion is free (`surt_prefix`
rstrips the trailing slash regardless), and a bare host survives the URL-scheme
migrations that break path prefixes.
