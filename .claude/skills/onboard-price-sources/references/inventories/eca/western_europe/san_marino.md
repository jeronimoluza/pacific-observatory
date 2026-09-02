# San Marino — price source inventory (eca/western_europe/san_marino)

_Inventory written: 2026-09-01_ (ECA F&B sweep, agent A)

Started at 0 sources of any kind. **Result: 1 source shipped (coal_sm,
supermarket, food-and-beverage).**

## Shipped

| Source key | What | Notes |
|---|---|---|
| `coal_sm` | "Spesa Online COAL" -- online grocery arm of COAL, San Marino's retail/consumer cooperative group (`spesa.gruppoce.sm`) | Next.js static-export shell + a same-brand SaaS backend on a different domain (`spesa.lenny.sm`, "Lenny" platform), found via a Playwright network trace. Fully open JSON API (`/api/category/tree`, `/api/product/search?category_id=<id>&page=<n>`), 210 leaf categories. **Bug found and worked around**: `category_id` isn't validated once a category's real content is exhausted -- the API silently falls back to an unrelated, never-empty default listing instead of returning `[]` (confirmed: `category_id=818`, tree-declared count 3, still returned new 20-row pages past page 3). Spider stops pagination on zero NEW post-dedup items per page, not on an empty array. Full unbounded run launched 2026-09-01, cadence weekly. |

## Considered and rejected

- `titancoop.sm` -- TITANCOOP's Dogana location is COAL's supermarket
  format per search results, but `curl_cffi` failed with `curl: (56)
  Connection closed abruptly` on first probe; not re-probed since
  `spesa.gruppoce.sm` (COAL's own e-commerce arm) already covers the same
  operator group with a clean win.

## Next steps for a future pass

- The API-fallback bug documented above means the crawl's traversal order
  matters more than the category tree's structure suggests -- worth a
  periodic re-check that the dedup-based early-stop is still keeping run
  time bounded as the catalog grows.
- `titancoop.sm`'s connection failure was not deeply investigated (no
  curl_cffi profile retry, no Playwright check) since coal_sm already
  filled the slot -- worth a proper mandatory-gate probe in a future pass
  if a second San Marino source is ever wanted.
