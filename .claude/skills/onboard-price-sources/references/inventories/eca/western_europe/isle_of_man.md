# Isle of Man — price source inventory (eca/western_europe/isle_of_man)

_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 zero-budget pass)

Before this pass: 0 sources of any kind. **Result: 1 shipped.** The previous
file's negative result was a tooling artefact, exactly as it warned — a single
WebSearch found a live online-grocery sector the domain-guessing pass missed
entirely.

## Shipped

| Source name | URL | Channel / role | Status | Notes |
|---|---|---|---|---|
| `newbys_im` | https://newbys.im/ | convenience / `retailer_sku` | **SHIPPED** | Newby's Convenience, two Douglas stores. Shopify; `/products.json` open, and page 2 returns a different set (enumerability confirmed, not just access). Test run scraped **292 items**, GBP decimals eyeballed against the rendered page (£11.99 Rioja, £8.25 Peroni 4pk, £3.80 sandwich). Real food categories (Alcohol; Biscuits, Cakes Crisps & Snacks). Note the site has corrupted some of its own titles with a find/replace ("Campo Viejo Rioja Reser11.9Va") — that is source data, emitted verbatim per the classifier's raw-name rule. |

## Live but not shipped

| Candidate | URL | Status | Notes |
|---|---|---|---|
| SPAR Isle of Man | https://spar.co.im/ | **NO CATALOG** | Real WordPress site advertising a one-hour Douglas delivery service, but no e-commerce backend: Shopify / Woo Store / Magento / PrestaShop / VTEX endpoints all 404 and `robots.txt` is 29 bytes. Ordering appears to be phone/in-person. Worth re-checking — a chain this size adding a webshop is the most likely future win here. |
| Robinson's Fresh Foods | https://www.robinsons.im/ | **BROCHURE** | 191-page CMS with opaque `page_NNNNNN.html` URLs; homepage carries zero `£` tokens and no shop/cart/order links. Third-party pages describe island-wide grocery delivery, so ordering is likely offline. |
| ShopIOM | https://www.shopiom.im/ | **DIRECTORY** | A retail directory (it has a Groceries category page), not a catalog. Usable as a seller-directory seed for a future pass, not as a price source. |
| Deliveries.im | https://deliveries.im/ | **DIRECTORY + reCAPTCHA** | Community delivery directory; carries a reCAPTCHA wall and no product catalog. |

## Dead ends (carried forward, re-confirmed)

Shoprite (IoM) was acquired by Tesco in Oct 2023 and ceased as a brand in June
2024; Tesco's UK online grocery excludes IoM addresses. The prior pass's
NXDOMAIN guesses (`isleofmancoop.co.im`, `iomcoop.co.im`, `iomcoop.com`,
`shoprite.co.im`, `robinsonsiom.com`) remain dead.

## Next steps

- Re-check `spar.co.im` for a webshop in ~6 months.
- ShopIOM's Groceries directory is the cheapest route to a second source.

## Common Crawl coverage

Probed 2026-09-02 by the common_crawl session: 8 crawls spanning 2019-2026,
`max_blocks=40`. Counts are host records in the CC index and, separately, the
subset matching the manifest's `archive_path_re`.

| Source | Crawls with host | Host records | Matching PDP regex | Verdict |
|---|---|---|---|---|
| `newbys_im` (Shopify `/products.json`) | 6/8 | 2163 | 1887 | Strong series. |


`archive_prefix` on `newbys_im` was shortened to the bare registrable host on
2026-09-02. It is a plain **string** prefix applied to cdx lines *before*
`archive_path_re` is consulted, so a path in the prefix hard-caps what any regex
can see, and a wrong one fails silently — no manifest, no miss record, no error.
Filtering is `archive_path_re`'s job. Over-inclusion is free (`surt_prefix`
rstrips the trailing slash regardless), and a bare host survives the URL-scheme
migrations that break path prefixes.
_Inventory written: 2026-09-01_ (ECA F&B sweep, agent A)

Started at 0 sources of any kind. **Result: 0 shipped -- inconclusive, not
exhaustively confirmed (see caveat below).**

## What was checked

Shoprite (Isle of Man) was the island's largest supermarket chain but was
acquired by Tesco in October 2023 and ceased to exist as a separate brand
in June 2024; all nine former Shoprite stores are now Tesco Superstore/
Express outlets. Tesco's UK online-grocery delivery service is widely
reported as excluding Isle of Man addresses (outside the mainland-GB
delivery zone), and no IoM-specific Tesco storefront domain was found.

Direct domain guesses for an Isle of Man Co-operative or independent
chain all failed to resolve: `isleofmancoop.co.im`, `iomcoop.co.im`,
`iomcoop.com`, `shoprite.co.im`, `robinsonsiom.com` -- all `NXDOMAIN`.

## Caveat -- genuinely incomplete

This session's WebSearch budget was exhausted before this country could
be searched properly (it is shared session-wide across the 12 parallel
agents running this sweep). Only direct domain guesses and two
WebFetch-based search-engine attempts were possible (DuckDuckGo HTML
returned a CAPTCHA page; Bing returned unrelated generic-dictionary
content, likely because the query string didn't survive whatever caching
WebFetch applied). **Treat this as unexamined, not as a confirmed dead
end** -- a future pass with WebSearch available should start fresh here
rather than trusting this file's negative result.

## Next steps for a future pass

- Re-run with WebSearch: "Isle of Man online grocery" / "SPAR Isle of Man
  delivery" / "Isle of Man supermarket home shopping".
- Check whether any of the former Shoprite locations' new Tesco branding
  comes with an IoM-specific delivery arrangement (sometimes acquired
  chains get a special delivery carve-out even when the acquirer's
  mainland service excludes the territory).
