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
