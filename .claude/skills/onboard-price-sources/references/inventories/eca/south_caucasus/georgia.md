# Georgia (eca/south_caucasus/georgia)

_Inventory written: 2026-09-01_

Final F&B sweep, ECA agent B. At pickup this pass, worklist snapshot showed
1 food source (`europroduct_ge`); by the time this pass reached Georgia a
concurrent same-day wave had already added `zgapari_ge` (supermarket, flat
`/products/page-N/` walk, ~1,164 SKUs, GEL) -- see that YAML's own notes.
Georgia is therefore already at 2 food sources; **no new source shipped
this pass** despite real effort (documented below to save the next pass
the same dead ends).

## Dead ends / candidates examined, none built

- **nikora.ge** -- this is Nikora Trading LTD's CORPORATE group site, not
  a shop. Links out to three sub-brand sites (`nikora.nikoraltd.ge`,
  `metable.ge`, `mzareuli.nikoraltd.ge`), each with a `/products` page --
  but those pages are static "our product range" showcases with no price
  text, no GEL/₾ signal, and no per-item structure beyond a generic
  menu-item div. Not an e-commerce catalog. Nikora is Georgia's largest
  supermarket chain by store count and is worth revisiting if a genuine
  transactional storefront is found under a different subdomain in a
  future pass (its own delivery app was referenced in search results but
  not located as a web catalog this pass).
- **goodwill.ge**, **spar.ge** -- both HTTP 200 but React/SPA shells with
  zero price signal and zero product links in the raw `curl_cffi` fetch;
  needs a Playwright render + network trace, not attempted to completion
  this pass (goodwill.ge specifically also needs a same-shelf cross-check
  against Wolt's existing goodwill listing if a direct site is ever found,
  per rule 10).
- **bigmarket.ge** -- confirmed via Playwright network trace to be a
  GENERAL marketplace (categories: beauty-personal-care, clothing,
  appliances, home-kitchen, smart-home, computers, electronics) with NO
  food/grocery category at all -- disqualified on category-1/02 relevance
  grounds (rule 1), not on technical difficulty. Its `_rsc=` fetch
  requests are Next.js App Router React-Server-Component payloads (a
  binary-ish serialization, not plain JSON) if anyone does want its
  catalog for a non-food division later.
- **market.extra.ge** ("Extra Market") -- IS food-relevant (categories
  seen: Promotion, Diabetic, ...). Backend is a clean JSON REST API at
  `api.moitane.ge` (the same "Moitane" white-label grocery-delivery
  platform used by `lavka_uz`/`globus_online_kg` in Central Asia).
  `GET /v1/Categories?BrandId=1&Latitude=..&Longitude=..` works
  unauthenticated (200, real category tree, shopId=91). However the
  products-by-category endpoint was NOT found in the time available --
  `/v1/Tags/main-tag-prods` (visible in the network trace) returns 401
  without a session/auth token, and several guessed REST paths
  (`/v1/Products?CategoryId=`, `/v1/Products/ByCategory`,
  `/v1/Shops/{id}/Products`) all 404. A category page needs to be reached
  via the SPA's client-side router (plain anchor scan found no `<a href>`
  category links -- likely `router.push`-driven) to observe the real
  products request. Real, promising lead for a future pass with more
  Playwright interaction budget (needs to actually click through, not just
  load the homepage).
- **2nabiji.ge** ("Ori nabiji") -- same Next.js SPA-shell signature as
  bigmarket.ge (`og:site_name: "Ori nabiji Commerce"`); not probed past
  that this pass.
