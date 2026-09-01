# Morocco — price source inventory (menaap/north_africa)

_Inventory written: 2026-09-01_

Cold-start inventory (menaap region has UAE only so far; Morocco had none).
Wave-7 brief: Morocco started this pass at 3 sources / 2 food
(`aswak_assalam_ma`, `cima_ma`, `hcp_ipc`), no workbook candidates supplied
("DISCOVER"). Target was >=5 sources AND >=2 food. No Morocco rows exist
anywhere in `outputs/sources_pending_jero.xlsx` (checked all 5 sheets,
case-insensitive match on "morocco"/"maroc"/"MAR" across country/ISO3
columns — zero hits, confirming the brief).

## Onboarded this pass

| Source | Channel | Platform | Notes |
|---|---|---|---|
| `electroplanet_ma` | electronics | Bespoke Magento SSR (Luma theme, listing-card extraction) | `/graphql` is 401'd by an Apache htpasswd wall site-wide; shared `MagentoSSRBaseSpider` regex doesn't match this theme's nested brand+ref spans. 11 top-level category roots, 3-level `family-list-container` tree. Price from `[data-price-type="finalPrice"] data-price-amount` (sidesteps "1 234,56 DH" display formatting entirely). 1,493 rows full unbounded walk, 0% food (pure electronics/home-appliance). |
| `mubawab_ma` | real-estate | Bespoke listing-card scrape, server-rendered | Residential-rental-only scope (`appartements-a-louer`, `villas-et-maisons-de-luxe-a-louer`) across 10 city slugs; commercial rental categories excluded to keep `coicop_codes: ["04.1.1"]` narrow. Pagination is a URL path suffix `:p:<n>:`, NOT `?page=`. Price carries a U+202F narrow-no-break-space thousands separator — handled by the shared `normalize_price()` helper. |

## Candidates probed and rejected

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| Marjane | marjane.ma | DEAD (API auth + automation-fingerprint block) | Real, large food catalog exists (sitemap: 3 shards x 5000 URLs under `/courses-en-ligne/`) but price is loaded from a separate API (`api-ayaline.marjane.ma`) gated behind a subscription key that alone doesn't clear a 401 (likely also needs a reCAPTCHA-Enterprise-derived token), and headless Playwright gets a bilingual "Access Restricted" interstitial even though curl_cffi gets the real page from the same IP. See `known_blockers.md`. Worth a dedicated pass if either wall falls — highest-value remaining Morocco grocery target. |
| Carrefour Morocco (Label'Vie) | carrefour.ma | DEAD — domain does not resolve | `carrefour.ma` gives `Could not resolve host`; the working `carrefour_dz`/`carrefour_tn` Magento-GraphQL pattern has nothing to attach to without finding Label'Vie's actual storefront domain. Not searched further this pass (WebSearch budget). |
| Jumia Morocco | jumia.ma | DEAD — Cloudflare | HTTP 403 "Just a moment..." on curl_cffi (chrome124/chrome120/safari17_0) AND headless Playwright. No `jumia_*` spider exists anywhere in this repo yet to check for a shared-tenant bypass. |
| Kitea (furniture) | kitea.ma | DEAD — Cloudflare | Same signature as jumia.ma: 403 on all 3 curl_cffi profiles + Playwright, `Just a moment...`. |
| BIM Maroc | bim.ma | No online store | 200 OK but the entire site is the Turkish BIM group's corporate KuramPortal CMS — philosophy/store-locator/careers/contact/product-presentation pages, zero prices or product listings anywhere. Matches BIM's known global no-e-commerce posture. |
| Atacadao Maroc | atacadao.ma | DEAD — 403 | curl_cffi chrome124 403; not re-probed with other profiles or Playwright this pass (already had 2 working sources by this point). |

## Dead ends worth remembering

- **Morocco's real e-commerce leaders (Marjane, Carrefour/Label'Vie) are the hard ones**; the inverse-correlation law held here too — Electroplanet (a mid-tier electronics chain) and Mubawab (real-estate classifieds, not even a grocery competitor) verified on the first pass with plain `curl_cffi`, while the two biggest hypermarket brands are either unreachable (Carrefour's domain) or API/automation-gated (Marjane).
- **Marjane's `runtimeConfig.apiUrl` leak is a reusable technique**, not just a dead end: any Next.js SSR storefront that ships its backend config inline (`__NEXT_DATA__.props.pageProps.config` or `.runtimeConfig`) is worth checking even when the rendered HTML carries no price — the leaked API host/key tells you exactly what to probe next, even if this particular key wasn't sufficient alone.
- **Playwright and curl_cffi disagreeing on the SAME site is itself a signal.** Marjane served curl_cffi's `chrome124` fingerprint the real page every time but blocked Playwright with a geo/access-restricted interstitial from the identical IP — i.e. the block keys off browser-automation tells (not IP/geo), the opposite of the usual "curl fails, Playwright passes" WAF pattern documented elsewhere in `known_blockers.md`.
- Morocco's `.ma` retail sites that DO work (Electroplanet, and the pre-existing Aswak Assalam / CIMA) are all comma-decimal, narrow-no-break-space-thousands MAD displays exactly as the wave-7 brief warned — but every spider built this pass reads price from a machine-precise data attribute or runs it through `normalize_price()`, so none of them actually needed bespoke comma-parsing logic. Future Morocco spiders should default to that approach rather than regexing the display text.
