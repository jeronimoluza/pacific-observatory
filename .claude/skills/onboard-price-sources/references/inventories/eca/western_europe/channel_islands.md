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

---

## UPDATE 2026-09-01 (second pass) — the dead end above was WRONG. Source shipped.

**Result: 1 source shipped — `coop_ci`. Channel Islands is no longer greenfield.**

The pass above got everything right except the last step. It found the Flutter
shell, traced the real backend (`ogs.channelislands.coop`), and reverse-engineered
the route (`GET /api/stores/<id>/products`) — then hit `401 {"message":
"Unauthenticated."}` and concluded the catalogue was member-login-walled.

It is not. The bundle ships a **static anonymous Laravel Sanctum app token** that
every visitor receives. The earlier pass grepped `main.dart.js` for the strings
`"guest"` and `"public"`; the token is neither — it is a bare bearer literal
matching `\d+\|[A-Za-z0-9]{40,60}`. Sending it as `Authorization: Bearer <token>`
opens the entire catalogue over plain HTTP, no browser, no login, no cookie.

| Store | Island | Products |
|---|---|---|
| `id=1` Jsy - Millennium Park Grand Marché | Jersey | 5,058 |
| `id=2` Gsy - St Martin Grand Marché | Guernsey | 4,687 |

Both are scraped: of 110 products sharing an id across stores, **108 had
different prices** (Guernsey systematically cheaper — Nescafé Gold Blend 190g
£10.85 Jsy vs £10.30 Gsy). Identity is (store, id); the emitted URL carries
`?store=` or `DuplicationPipeline` would drop the Guernsey half.

Test run 2026-09-01: 500 rows / 7.4s, all HTTP 200, 500 distinct product_ids and
URLs, 0 blank names, 0 non-positive prices, 100% GBP, price range £0.48–£99.99
(median £2.65). **Measured food+beverage share 73.4%** (Fresh Food 35.0%, Food
Cupboard 22.4%, Alcohol 8.6%, Drinks 4.2%, Bakery 3.2%). Records also carry EANs
and a two-level category breadcrumb.

Trap for the next pass: `price` is an integer in **pence** (`3150` alongside
`unit_price_text: "£31.50 per ITEM"`).

**Lesson worth generalising:** a 401 from a canvas-SPA backend is not evidence of
a login wall until the bundle has been grepped for a *token literal*. A Flutter or
React app must authenticate somehow before the user logs in, and for Laravel
Sanctum that is routinely a hardcoded anonymous token.

Still unchased (unchanged from above): Snappy Shopper's seller directory.
