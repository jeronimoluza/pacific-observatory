# St. Vincent and the Grenadines

_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 pass, which explicitly asked not to be treated as exhausted)

Before this pass: 0 sources total, 0 food. **Result: 0 shipped.** The fresh
per-country WebSearch the previous file asked for was run, and it did not
surface an online storefront.

## What the search returned

Every SVG grocery result is a **Facebook page or a directory listing**, not a
storefront:

| Candidate | Where it lives | Status |
|---|---|---|
| C.K. Greaves Supermarkets | facebook.com/greavessupermarkets, insandoutsofsvg.com listing | **FACEBOOK / DIRECTORY ONLY** — Upper Bay Street Kingstown, in-store pickup only per its listing. No independent domain surfaced. |
| Bonadie Supermarket #2 | facebook.com/bonadieno2 | **FACEBOOK-ONLY** — Middle Street & Egmont Street, Kingstown. |
| EHub SVG | facebook.com/eHubSVG | **FACEBOOK-ONLY** — a personal grocery-shopping and island-wide delivery service, i.e. a concierge shopper, not a catalog with prices. |
| Massy Stores SVG | https://www.massystoressvg.com/ | **BROCHURE** — carried forward and unchanged: static WordPress, `?rest_route=/wc/store/v1/products` returns `rest_no_route`. The `shopmassystores<code>.com` pattern used by the Barbados / Trinidad / St Lucia storefronts does not exist for SVG (`shopmassystoresvct.com`, `massystoresvct.com` both NXDOMAIN). |
| CaribeEats | backend.caribeeats.com | **NOT APPLICABLE** — carried forward: its `/api/init` region list (21 regions) has no St Vincent entry. |

## Verdict

This is now a **searched negative**, not an unexamined country. SVG's grocery
retail transacts through Facebook pages and phone orders; there is no
scrapeable catalog. That is a different and stronger statement than the
2026-09-01 file could make.

## Next steps

- Watch for Massy Group extending its `shopmassystores*` storefront platform
  to SVG — Massy already runs physical stores in Kingstown and Arnos Vale, and
  the platform exists for four sibling markets. That is the single most likely
  future win, and it costs nothing to re-check the domain pattern.
