# Comoros

_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 budget-limited pass)

Before this pass: 0 manifests of any kind. **Result: 0 shipped.** A proper
French-language search was run — the lever the previous pass lacked — and it
found live storefronts, but all of them price in EUR for the diaspora.

## Found, live, and NOT shippable as Comorian retail

Both surviving candidates are "order from abroad, delivered to your family in
Moroni" services. They carry real catalogs, but the prices are **EUR prices
paid by a sender in France**, not what a consumer in Moroni pays. See
`ssa/congo_rep.md` for the same pattern in Francophone Africa — it is the
dominant shape of "online grocery" in these small diaspora-heavy markets and
is the single biggest false-positive risk in this whole region.

| Candidate | URL | Platform | Why not shipped |
|---|---|---|---|
| Comores En Ligne | https://comores-en-ligne.fr/ | Next.js SPA, 26KB sitemap | Has a real **Épicerie** category scoped to Moroni/Ngazidja and advertises fresh farm produce. Page carries 83 EUR tokens against 3 KMF tokens — priced in euros, `.fr` domain. Diaspora-facing. |
| Coliscom | https://www.coliscom.fr/ | **Shopify, `/products.json` open and paginating** | Technically trivial to onboard (page 2 returns a different set), but it is a French retailer shipping to the Indian Ocean; catalog is cookware, nappies and general goods at EUR prices. Not Comorian retail. |

## Dead ends

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Comores Market | https://comoresmarket.com | **BROKEN TLS** | Carried forward and re-confirmed: `TLSV1_ALERT_INTERNAL_ERROR` across all impersonation profiles, plain HTTP 404. This is the one genuinely Comorian online supermarket ("drive" with 1-hour pickup, two physical Moroni stores, active Facebook page) and its site is simply broken. **The highest-value re-check in this country** — if the TLS config is ever fixed it should ship immediately. |
| Smart Shahula, MAG MARKET, SAWA Prix, SARA MARKET | — | **NO WEB PRESENCE** | Physical Moroni supermarkets surfaced only via directory aggregators; no independent domain for any of them. |

No Jumia / Glovo / Bolt Food / Yango-style marketplace operates in Comoros.

## Next steps

- Re-probe `comoresmarket.com` in ~3 months (shorter than the standard window
  — it is a live business with a fixable server misconfiguration, not an
  absent one).
_Inventory written: 2026-09-01_

Final F&B sweep, wave (2026-09), agent B. Cold-start (no prior inventory file
existed). Comoros had **zero** manifests of any kind before this pass (0 food,
0 total). Search-budget-limited pass (WebSearch quota was shared/exhausted
mid-sweep across the 12 parallel agents) — one round of marketplace/local
search plus direct-domain probing.

**Result: 0 sources shipped. No viable online grocery found.**

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Comores Market | https://comoresmarket.com | **DEAD — broken TLS / 404** | Search results describe it as an "online supermarket drive" (order + 1hr pickup) for Moroni. Live probe 2026-09-01: HTTPS fails with `TLSV1_ALERT_INTERNAL_ERROR` across chrome124/chrome120/chrome99/safari17_0 impersonation profiles (server-side TLS misconfiguration, not a WAF — no handshake completes at all); plain HTTP on the bare domain returns 404. The business may exist (Facebook page is active) but has no working website to scrape. Re-check in ~6 months in case the site is fixed. |
| Smart Shahula, MAG MARKET, SAWA Prix, SARA MARKET | (no domains found) | **NOT PROBED — no web presence found** | Physical supermarkets in Moroni surfaced by search (via `evendo.com` listing aggregator, not their own sites); no independent e-commerce domain found for any of them in this pass. |

No marketplace-directory candidate (Jumia/Glovo/Bolt Food/Yango-style) was
found operating in Comoros. Population (~850k) and general SSA e-commerce
patterns make a thin market plausible; this is a "no online grocery sector
found," not a confirmed structural absence — worth a fresh, deeper pass
(French-language search specifically) rather than treating as settled.

---

## UPDATE 2026-09-01 (second pass) — source SHIPPED. The pass above missed the platform entirely.

**Result: 1 source shipped — `comoresenligne_km`. Comoros is no longer greenfield.**

The pass above was right that `comoresmarket.com` is dead (TLS handshake still
fails on chrome124 and safari17_0, re-confirmed) and right to flag itself as
search-starved. A French-language search — the exact "next step" it recommended —
surfaced **comores-en-ligne.fr** immediately, which it had never seen.

Next.js storefront: category pages server-render zero products and zero price
text, and even a hydrated Playwright DOM returned no price tokens. An XHR capture
found a same-origin proxy over an open Django REST API, no auth of any kind:

    GET /api-proxy/products?limit=100&offset=<N>[&category=<id>]
    -> {"count", "next", "previous", "results": [...]}

`count` = 1,527 site-wide. Scraped UNSCOPED (whole catalogue, non-food included).
Food is a minority: ~172 products across the five food categories (epicerie 91,
produits-frais 33, cremerie 22, les-boissons 20, boucherie 7); the rest is
hygiene/beauty, appliances, phones, construction materials and school supplies.

Test run 2026-09-01: **1,524 rows** — exactly `count` minus the 3 products that
carry no `incl_tax` price. 1,524 distinct ids AND urls, 0 blank names, 0
non-positive prices, 100% EUR.

**IDENTITY TRAP — cost 83 rows on the first run.** `slug` is NOT unique: 43 slugs
are reused across distinct products (`carreau-m2` 12x, `kabaila` 9x,
`carte-cadeau` 9x). Keying the emitted URL on the slug gave
`DuplicationPipeline` 1,441 distinct URLs for 1,524 priced products and silently
dropped the remainder. Fixed by using the API's own canonical per-product `url`
field. The first run reported 1,441 and looked plausible — the only reason it was
caught is that the API's `count` gave an independent expected value. **Always
derive an expected row count from the source before believing a row count.**

**UNRATIFIED DEFINITIONAL CALL:** every product returns `price.currency: "EUR"`,
not the KMF in countries.yaml. Stock is physically in-country (products carry a
`stock_location` of "Grande Comore"/"Anjouan"; `partners` names Moroni and Ouani
stores) but the platform bills in EUR because much of its custom is diaspora
paying from abroad. Same shape as `dokan_sy` (Syrian stock, USD pricing) and
cleaner, since KMF is on a fixed peg (1 EUR = 491.96775 KMF). If diaspora EUR
pricing is judged unacceptable as a proxy for Comorian domestic retail, drop the
manifest and Comoros returns to zero.

Still unchased: `kuuzacomores.com` (live, 200, ~83 KB, "first marketplace of the
Comoros" — only 2 price tokens on the landing page, needs an API hunt);
`coliscom.fr` (diaspora parcel service operating out of Réunion — almost
certainly export pricing, lower value).
