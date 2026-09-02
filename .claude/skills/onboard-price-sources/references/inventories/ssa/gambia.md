# Gambia, The

_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 zero-budget pass, which recorded itself as "essentially
unexamined")

Before this pass: `fews_net` + `wfp_prices` only, 0 retail sources.
**Result: 1 shipped.** The prior pass ran with zero WebSearch budget and
found nothing; one English-language search surfaced four live candidates.

## Shipped

| Source name | URL | Channel / role | Status | Notes |
|---|---|---|---|---|
| `ebaaba_gm` | https://www.ebaaba.com/ | marketplace / `retailer_sku` | **SHIPPED** | The Gambia's largest online marketplace (Mall of Gambia, Bakoteh). 1,615 sitemap URLs of which **1,486 are product pages**; PDPs carry JSON-LD with GMD prices and a `category` field. Test run scraped 6 items (capped by `--max-items 5`): GMD 2,900 voltage stabilizer, GMD 4,500 Huawei LTE router — sane against a ~72 GMD/USD rate. Groceries sit alongside general merchandise, so `coicop_codes` is left unset for the classifier. The WooCommerce Store API route answers **403** while PDPs serve fine, which is why the spider goes through the sitemap. |

## Live but not shipped

| Candidate | URL | Status | Notes |
|---|---|---|---|
| PriceGambia | https://www.pricegambia.com/ | **NO SITEMAP** | Live 70KB marketplace page ("shop groceries and supermarkets… delivered to your doorsteps") but `/sitemap.xml` is empty and no platform fingerprint matched. Needs a Playwright network trace to find its catalog API — the single highest-value remaining lead for a second Gambian source. |
| Maroun's Supermarket | https://marounssupermarket.com/ | **EMPTY RESPONSE** | Resolves and returns 200 with a zero-length body across chrome124/chrome120/safari17_0. Real chain (Kololi + Serrekunda); site appears broken rather than absent. Re-check in ~6 months. |
| FoodGambia / Julabaa | https://www.foodgambia.com/ | **NXDOMAIN** | Described in search results as a Banjul/Serrekunda/Bakau delivery service, but the domain does not resolve. |

## Dead ends (carried forward from the 2026-09-01 pass)

`jumia.gm` NXDOMAIN; `glovoapp.com/gm/` 404; `homefrontgambia.com` and
`kombosupermarket.gm` NXDOMAIN. Yango's per-country list is client-side
rendered and remains inconclusive.

## Next steps

- Playwright network trace on `pricegambia.com` — it advertises a grocery
  catalog and is the most likely second source.
- Re-probe `marounssupermarket.com` once its server stops returning an empty
  body.
