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

## Common Crawl coverage

Probed 2026-09-02 by the common_crawl session: 8 crawls spanning 2019-2026,
`max_blocks=40`. Counts are host records in the CC index and, separately, the
subset matching the manifest's `archive_path_re`.

| Source | Crawls with host | Host records | Matching PDP regex | Verdict |
|---|---|---|---|---|
| `ebaaba_gm` (WooCommerce, sitemap walk) | 6/8 | 64 | 55 | **Single price point, not a series** — see note below. |

**ebaaba_gm yields one observation, not a series.** 54 of its 55 matching
records sit in a single crawl, CC-MAIN-2023-14; every other crawl holds 1-4
records, all `/categories/...` listing pages. Treat any historical ebaaba
figure as a single 2023 price point. The live scrape is the real source here.


`archive_prefix` on `ebaaba_gm` was shortened to the bare registrable host on
2026-09-02. It is a plain **string** prefix applied to cdx lines *before*
`archive_path_re` is consulted, so a path in the prefix hard-caps what any regex
can see, and a wrong one fails silently — no manifest, no miss record, no error.
Filtering is `archive_path_re`'s job. Over-inclusion is free (`surt_prefix`
rstrips the trailing slash regardless), and a bare host survives the URL-scheme
migrations that break path prefixes.
