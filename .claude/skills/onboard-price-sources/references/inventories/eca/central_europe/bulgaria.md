# Bulgaria

_Inventory written: 2026-09-11_

Scope note: two-candidate pass from the onboard4 backlog shard (Bulgaria ranked
132 of 257 COICOP leaves empty). Both are Schwarz-group (Lidl/Kaufland) and both
are dead for the same underlying reason — neither runs a Bulgarian webshop.

Already onboarded before this pass: `ebag_bg`, `tmarketonline_bg`, `supermag_bg`,
`ogimarket_bg`, `sid_shop_bg`, `gracia_cosmetics_bg`, plus the Eurostat
electricity/gas/PPP fetchers.

| Candidate | URL | Outcome |
|---|---|---|
| Lidl Bulgaria | https://www.lidl.bg/ | **Dead — no prices published on the web**, despite a real 1,073-product sitemap at `/p/export/BG/bg/product_sitemap.xml.gz` and three JSON-LD blocks per PDP. The `Offer` node carries `priceCurrency: BGN` / `availability: InStoreOnly` and **no `price` key**; zero `лв` matches in 393 KB of PDP HTML, and the weekly-offer routes render as image flipbooks. `/q/api/search` exists but 406s on every `assortment=`/`locale=` combination tried. See `known_blockers.md`. |
| Kaufland Bulgaria | https://www.kaufland.bg/ | **Dead — brochure site.** `/.sitemap.xml` has 2,386 URLs, of which 582 are `/asortiment/*` — which reads like a catalogue and is not one: three sampled pages (180-224 KB) returned zero `лв` matches; they are brand/product-range pages. The rest is 1,420 recipes and 180 magazine articles. `/produkti.html` 404s. Only price surface is the leaflet DAM at `assets.leaflets.schwarz`. Note this is a *different* failure from `kaufland.cz`/`kaufland.sk`, which are a hard 403 WAF — the `.bg` host is wide open and simply has nothing to sell online. See `known_blockers.md`. |

**Gaps for the next run.** `billa.bg` is the highest-value unclaimed Bulgarian
grocer and is explicitly recorded in `known_blockers.md` as *unfinished, not
blocked*: Nuxt SPA with an Algolia client in `/_nuxt/*.js`, needing one Playwright
network trace to recover the app id + search-only key, which would land it on
Tier 1B. That is the cheapest next move here. Also unclaimed: NSI Bulgaria
(national statistics) for `official_avg` / `cpi_benchmark`.
