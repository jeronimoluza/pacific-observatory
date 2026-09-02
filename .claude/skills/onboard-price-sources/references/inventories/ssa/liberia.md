# Liberia

_Inventory written: 2026-09-01_

SSA sweep, agent A. Country had `fews_net` + `wfp_prices` (shared regional
humanitarian fetchers) before this pass — 0 retail sources. **Result: 0
sources shipped.** **This pass ran with zero WebSearch budget** (session-wide
cap exhausted before this country's turn) — every candidate below came from
direct domain probing only, no real search sweep ran at all for this
country. Treat this inventory as essentially unexamined.

## Dead ends

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Jumia | jumia.com.lr, jumia.lr | **NOT FOUND — NXDOMAIN (both)** | |
| Glovo | glovoapp.com/lr/ | **DEAD — 404, no LR route** | |
| Harbel Supermarket Corporation | harbelsupermarket.com | **DEAD — brochure site, 0 products/prices** | Live WordPress site (200, 85KB), mentions "product"/"price"/"cart" in page copy but has no WooCommerce Store API (`/wp-json/wc/store/v1/products` -> 404), no `/shop/` page (404), and its `/product-range/` page — the closest thing to a catalogue — has zero currency mentions (0x "LRD"/"USD") and zero "add to cart" occurrences across 144KB of markup. Confirmed brochure-only, same pattern as Martínez Hermanos' own site in Equatorial Guinea. |
| Exclusive Supermarket (Monrovia) | exclusivesupermarketliberia.com | **NOT FOUND — NXDOMAIN** | |

**Conclusion:** No candidates confirmed either way beyond the one dead
brochure site. This inventory is essentially unexamined — the next pass
should start Liberia from scratch with a proper English-language search
(Liberia is anglophone, so this is a comparatively low-cost re-run) before
concluding anything about the country's online grocery sector.
