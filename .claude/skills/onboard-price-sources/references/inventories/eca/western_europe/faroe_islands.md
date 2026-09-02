# Faroe Islands — price source inventory (eca/western_europe/faroe_islands)

_Inventory written: 2026-09-01_ (ECA F&B sweep, agent A)

Started at 0 sources of any kind. **Result: 0 shipped -- no online grocery
sector currently exists in this market.**

## Dead ends checked

| Candidate | What | Why it doesn't work |
|---|---|---|
| `sms.fo` | SMS -- Faroese shopping-centre group, operates the Bónus banner + Miklagarður | WooCommerce install with exactly ONE product: a gift card (`/product/gavukortid-fra-sms/`). No grocery catalog. |
| `bonus.fo` | Bónus -- SMS's discount-grocery banner, 8 stores | Live site, no e-commerce platform fingerprint at all (no WooCommerce/Shopify/etc. markers, no add-to-cart) -- reads as a weekly-flyer/brochure page. |
| `miklagardur.fo` | Miklagarður -- the country's largest single supermarket | Wix site; its only transactable page (`/keyp`, "buy") is a Wix-Stores **gift-card** page, not a product catalog. |
| `kf.fo` | (guessed as a Faroese grocery co-op domain) | Actually "Kommunufelagið", the Faroese municipal association -- wrong guess, unrelated to retail. |
| Wolt | Nordic grocery-delivery marketplace, already covers Iceland | `wolt.com/fo` redirects to the generic global homepage -- no Faroese city listing. |
| Bolt Food | Delivery marketplace | `bolt.eu/en/cities/torshavn/` returns 404. |

No Wolt/Glovo/Bolt-style marketplace and no first-party retailer runs a
real online grocery storefront in the Faroe Islands as of this pass.

## Next steps for a future pass

- This session's WebSearch budget was exhausted partway through this
  country (shared session-wide across 12 parallel agents), so only direct
  domain guesses were tried after that point. A future pass with search
  budget available should search in Faroese directly (dagligvøru,
  handlan, netbúð) rather than relying on domain guesses.
- Re-check in ~6 months per the standard staleness window -- a market
  this small could plausibly gain a first online grocery offering from
  a single new entrant.

---

## UPDATE 2026-09-01 (second pass) — dead ends CONFIRMED with search budget available

The pass above flagged that its verdict rested on domain guesses because the
WebSearch budget was exhausted. That gap is now closed: a Faroese/Icelandic-brand
search was run, and it surfaced no candidate the pass above had missed (FK, Bónus,
A Handil, Miklagarður — all already listed). **The "no online grocery sector"
verdict stands, now on evidence rather than assumption.**

Independently re-probed 2026-09-01 with `curl_cffi impersonate=chrome124` — all
live, none WAF-blocked, and all confirmed brochure-only by price-token count on
the rendered homepage:

| Domain | Status | Price tokens (kr/DKK) | WooCommerce Store API |
|---|---|---|---|
| `fk.fo` (Føroya Keypssamtøka) | 200, 75.6 KB | **0** | `/wp-json/wc/store/v1/products` → 403 |
| `bonus.fo` | 200, 168 KB | **0** | 404 (no store route) |
| `ahandil.fo` (Á — largest supermarket, Klaksvík) | 200, 142 KB | **0** | 404 (no store route) |
| `miklagardur.fo` | 200, 628 KB | 1 (a stray `kr8.`) | n/a (Wix) |

Zero price tokens on a grocer's homepage is the brochure-only signature. `fk.fo`
was added to the list above (not previously probed); it is a real co-op site but
carries no catalogue. See `known_blockers.md` § "Brochure-only WordPress / no
online store".

Next pass: unchanged — re-check in ~6 months. A single new entrant would flip
this market, but nothing is close today.
