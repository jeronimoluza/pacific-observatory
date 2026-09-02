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
