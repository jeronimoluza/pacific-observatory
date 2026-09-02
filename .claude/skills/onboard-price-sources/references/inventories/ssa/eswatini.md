# Eswatini

_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 budget-limited pass)

Before this pass: `fews_net` + `wfp_prices`, 0 retail sources. **Result: 0
shipped.** An English-language search was run — the lever the previous pass
lacked — and it confirms the earlier "inconclusive-leaning-negative" read.

## What the search added

Eswatini's grocery retail is entirely South African franchise chains: SPAR,
Pick n Pay, Shoprite, Boxer, OK Foods, PnPay. Named stores confirmed in
Mbabane (OK Foods, Pick n Pay at The Mall) and Manzini (SUPERSPAR Buy N Save,
Boxer Superstores, Shoprite Busrank, Pick n Pay Family River Stone).

**No online ordering or delivery service surfaced for any of them.** The
searched result is consistent with the pattern already confirmed for Namibia
and Eswatini's other SACU/CMA neighbours: the dominant chains run brochure /
store-locator sites with no e-commerce.

## Dead ends

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Shoprite Eswatini | https://www.shoprite.co.sz | **BROCHURE** | Carried forward: pan-African Shoprite Group AEM corporate template, no add-to-cart, no product markup. |
| Pick n Pay Eswatini | pnp.co.sz | **NXDOMAIN** | Probed this pass. Pick n Pay operates physical stores in Mbabane and Manzini but has no `.sz` domain. |
| SPAR Eswatini | spar.co.sz | **NXDOMAIN** | Probed this pass. The franchise's public presence is a Facebook page (`facebook.com/spareswatini`, "Buy n Save - SPAR Eswatini", Manzini). |
| OK Foods, PEP, Friendly Foods | ok.co.sz, pep.co.sz, friendlyfoods.co.sz | **NXDOMAIN** | Carried forward. |

No delivery marketplace (Jumia / Glovo / Bolt / Yango) operates in Eswatini.

## Next steps

- The realistic route into Eswatini is **not** a local domain: it is whether a
  South African parent's storefront (`pnp.co.za`, `spar.co.za`,
  `checkers.co.za` Sixty60) exposes an Eswatini delivery zone or store-scoped
  catalog. That is a South-Africa-tenant question, not an Eswatini discovery
  question, and should be answered once for the whole CMA/SACU bloc rather
  than per country.
