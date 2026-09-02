# Greenland — price source inventory (eca/western_europe/greenland)

_Inventory written: 2026-09-01_ (ECA F&B sweep, agent A)

Started at 0 sources of any kind. **Result: 0 shipped -- no scrapeable
grocery e-commerce found this pass.**

## Dead ends checked

| Candidate | What | Why it doesn't work |
|---|---|---|
| `pisiffik.gl` | Pisiffik -- Greenland's largest private retail company, ~40 stores | Live PrestaShop storefront (real product pages, EAN-coded SKUs) but the catalogue is mattresses, kitchenware, small electronics, furniture and toys, with only incidental wine/sparkling-wine categories. This is Pisiffik's **department-store** e-commerce arm, not catalogue-led by COICOP 01/02 -- fails win criterion #1. |
| `brugseni.gl` | Brugseni (KNI) -- the other major Greenlandic chain | WordPress corporate site (Yoast SEO plugin), store-locator only (`/butikker/`), no webshop link anywhere. |
| `pilersuisoq.gl` | Pilersuisoq -- government-linked chain serving small settlements | Brochure site, no shop link, no e-commerce platform fingerprint of any kind. |
| `brugsen.gl` | (no "i", guessed variant) | TLS certificate hostname mismatch -- does not serve the real site. |

## Next steps for a future pass

- If Pisiffik's electronics/general-merchandise arm is ever wanted for a
  non-food division (COICOP 05/06/09-adjacent), the PrestaShop catalog at
  `pisiffik.gl` is fully scrapeable (Tier 1A, real PDP pages) -- just not
  a food-and-beverage win.
- No genuine grocery e-commerce sector was found to exist for Greenland
  this pass; Greenland's remote settlement structure (small towns served
  by government-subsidized Pilersuisoq stores) makes a delivery-style
  online grocery offering structurally unlikely, but this was not
  independently confirmed via search (budget exhausted -- see
  faroe_islands.md for the same constraint).
