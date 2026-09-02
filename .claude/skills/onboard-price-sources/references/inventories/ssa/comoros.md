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
