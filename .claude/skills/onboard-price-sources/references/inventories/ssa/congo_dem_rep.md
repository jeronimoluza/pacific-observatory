# Congo, Dem. Rep.

_Inventory written: 2026-09-11_

Scope note: single-candidate pass from the onboard4 backlog shard (DRC ranked 158
of 257 COICOP leaves empty). The one candidate was dead.

Already onboarded before this pass: `drcmart_cd`, `kedomarket_cd`, `shoppi_cd`,
`mabele_coop_cd`, `snel_cd` (electricity tariff), `wfp_prices`, `wb_rtdi_prices`.

| Candidate | URL | Outcome |
|---|---|---|
| Kin Marché | https://kinmarche.com/ | **Dead — promo-flyer-image site with zero price text.** Worth reading the detail before re-probing: the site is a **catch-all router**, so `/sitemap.xml`, `/wp-json/wc/store/v1/products`, `/products.json` and `/index.php?route=product/category` all return the identical 30,597-byte homepage with HTTP 200. Every platform fingerprint therefore gives a false positive. The real routes are `/product-categories` (74 KB, 23 category *names*, no items) and four `/product/<id>` pages (57/58/59/71) which are promo-flyer images titled "Promo Anniversaire". Zero USD and zero CDF price matches across both page types. Same class as `superindo.co.id`. See `known_blockers.md`. |

**Gaps for the next run.** DRC has no `official_avg` or `cpi_benchmark` source of
national origin — INS RDC and BCC (Banque Centrale du Congo) both publish price
material and neither is onboarded; a fetcher there is worth more than another
Kinshasa storefront. On the retail side the physical chains (Kin Marché, Peloustore,
Shoprite RDC) are largely Facebook-only, which is the structural reason this market
is thin — record that rather than re-searching it.
