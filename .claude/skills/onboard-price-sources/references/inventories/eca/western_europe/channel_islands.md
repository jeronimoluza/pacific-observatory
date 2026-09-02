# Channel Islands — price source inventory (eca/western_europe/channel_islands)

_Inventory written: 2026-09-01_ (ECA F&B sweep, agent A)

Started at 0 sources of any kind. **Result: 0 shipped -- genuine dead end,
not a search miss.**

## Dead end: Channel Islands Co-operative Society (login-walled catalog)

The Channel Islands Co-operative Society is the territory's main online
grocery operator (per its own press coverage: "5,000 products available
online", Jersey Post/Guernsey Post delivery). Its three storefronts --
`shop.channelislands.coop`, `jeshop.channelislands.coop` (Jersey),
`ggshop.channelislands.coop` (Guernsey) -- all serve the identical
Flutter-web "Eloyalty Customer App" shell, fully canvas-rendered
(CanvasKit), no scrapeable DOM.

A Playwright network-request trace (the shell's served JS never names its
own backend as a literal string) found the real API host,
`ogs.channelislands.coop`, and the exact catalog route reverse-engineered
from the minified `main.dart.js`: `GET /api/stores/<store_id>/products`.
Every `/api/*` route on that host, including the top-level `/api/stores`
list, returns `HTTP 401 {"message":"Unauthenticated."}` -- a Laravel API
requiring a member login to browse at all, with no guest/public variant
found anywhere in the bundle. Full write-up under "Login-walled catalog"
in `known_blockers.md`.

Snappy Shopper (a third-party same-day delivery app partnering with
Alliance Supermarket / The Food Warehouse in Guernsey) was surfaced by
search but not independently probed -- it is a food-delivery-app
aggregator, not itself a first-party grocery retailer's storefront, and
would need its own seller-directory investigation in a future pass if
this territory is revisited.

## Next steps for a future pass

- Snappy Shopper (snappyshopper.co.uk) -- check whether it exposes a
  reachable seller/store directory the way Wolt/Glovo do; if so, the
  underlying Alliance Supermarket / Food Warehouse storefronts might be
  independently scrapeable even though the Co-op's own app is not.
- Re-check the Co-op app periodically -- a login wall is an application
  design choice, not infrastructure decay, so it's unlikely to change on
  its own, but worth a note if the operator ever ships a public
  storefront.
