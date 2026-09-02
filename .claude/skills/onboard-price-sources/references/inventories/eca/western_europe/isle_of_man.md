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
