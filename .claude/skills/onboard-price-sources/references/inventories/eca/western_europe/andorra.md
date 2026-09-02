# Andorra — price source inventory (eca/western_europe/andorra)

_Inventory written: 2026-09-01_ (ECA F&B sweep, agent A)

Started at 0 sources of any kind. **Result: 1 source shipped (andorra2000_ad,
supermarket, food-and-beverage).**

## Shipped

| Source key | What | Notes |
|---|---|---|
| `andorra2000_ad` | Carrefour Andorra 2000 -- Andorra's own Carrefour-branded online supermarket (`alimentacio.andorra2000.ad`), legally/technically distinct from carrefour.es/.fr | Classic OpenCart, 584 category `path=` values on the nav; theme overrides product-card anchors with a JS quickview handler instead of a real `href`, worked around with a spider-level subclass (not a shared-base change). Full unbounded run launched 2026-09-01, cadence weekly. |

## Dead ends / not pursued

None found this pass beyond andorra2000_ad -- it was the first and only
candidate searched (Carrefour's own e-commerce dominates the Andorran
online-grocery search results; Caprabo was mentioned in passing as having
weaker delivery infrastructure but was not independently probed given
andorra2000_ad's clean win).

## Next steps for a future pass

- Caprabo (mentioned in search results as also present in Andorra with
  weaker online delivery) not independently probed -- andorra2000_ad
  already fills the food-and-beverage slot, so this is low priority
  unless coverage-density ranking is later applied here.
