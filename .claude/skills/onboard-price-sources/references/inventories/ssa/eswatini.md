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
_Inventory written: 2026-09-01_

Final F&B sweep, wave (2026-09), agent B. Cold-start (no prior inventory file
existed). Already-covered before this pass: 2 non-food sources (per the
sweep worklist), 0 food.

**Result: 0 sources shipped. No viable online grocery found.**

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Shoprite Eswatini | https://www.shoprite.co.sz | **DEAD — brochure/store-locator only** | Same pan-African Shoprite Group AEM corporate template confirmed on Namibia in this same pass (generic "Home" title, "shop" text present but no add-to-cart, no product markup, no cart/checkout flow). |
| SPAR, OK Foods, PEP, Friendly Foods (Eswatini) | (no domains found) | **NOT PROBED — no resolvable domain** | `spar.co.sz`, `ok.co.sz`, `pep.co.sz`, `friendlyfoods.co.sz` all NXDOMAIN on direct-guess probing. |

Eswatini is in the same Common Monetary Area / SACU bloc as Namibia and
South Africa and shows the identical pattern: the region's dominant grocery
chain (Shoprite) runs the same brochure-only corporate template with no
online ordering. No delivery marketplace (Jumia/Glovo/Bolt/Yango-style)
operates in Eswatini. WebSearch budget was exhausted session-wide before
this country could be searched properly (only direct-domain-guess probing
was possible) — treat as **inconclusive-leaning-negative**, not exhaustively
confirmed. A fresh WebSearch-based pass (once budget resets) is the clear
next step, specifically for SPAR/OK Foods Eswatini, which are real chains
with no domain found yet rather than confirmed non-existent online.
