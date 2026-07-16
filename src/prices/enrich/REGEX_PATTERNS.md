# REGEX_PATTERNS.md — How we read a price from a product name

## The job

Every scraped product arrives as a raw name like `Coca-Cola 500ml x 24` or
`Laughing Cow 10s 200g`. The extractor (`extract.py`) turns that text into a
small set of structured fields using only deterministic regular expressions —
no model, no guessing. Its output is a `StructuralFields` record:

- **pricing_basis** — what kind of thing is being priced
- **amount_value** + **standard_unit** — how much is in the pack
- **count** and **multiplier** — how many pieces / how many packs
- **is_promotion / is_bundle / is_multipack** — flags

## pricing_basis: what are we measuring?

Every product resolves to one of five bases:

| basis | meaning | example |
|---|---|---|
| mass | sold by weight | Rice 2kg |
| volume | sold by liquid volume | Milk 1L |
| length | sold by length | Foil 10m |
| count | sold as a number of pieces | Eggs 12 |
| item | one indivisible thing | Knife |

## amount_value + standard_unit: normalising the quantity

When a measure is found we convert it to one standard unit so prices are
comparable across the whole corpus: all weights become **kg**, all volumes
**lt**, lengths **m**. So `500ml` → amount_value `0.5`, standard_unit `lt`;
`200g` → `0.2`, `kg`. Count/item rows carry `unit`/`item`.

## count vs multiplier — the important distinction

- **multiplier** = how many identical, separately-measured packs.
  `4 x 20g` = four 20g units → multiplier `4`.
- **count** = how many pieces sit inside one pack whose total is already
  stated. `10s 200g` = 10 slices totalling 200g → count `10`.

This distinction is what keeps unit values correct (see below).

## How the patterns are organised

Rather than one giant regex, patterns are grouped into four families, compiled
from small editable vocabulary tables (`regex_patterns/vocab/*.yaml`) by
`grammar.py`:

- **M — Measure** (numbers + units: g, kg, ml, l, oz…)
- **C — Count noun** (12 pcs, 6 sachets, 50 tablets…)
- **P — Pack** (pack of 6, 24-pack, 10s…)
- **B — Bundle / promo** (gift set, 50% off…)

`extract.py` enumerates every candidate match, then `decide()` picks the best
one by a fixed precedence order. Adding a new word means editing a YAML row,
not the code.

## Handing off to the merge: correct unit values

Extraction's only job is **faithful capture**. It does *not* compute the final
price-per-kg. That happens downstream in `merge.py::compute_unit_value`, under
**Convention A**:

> For weight/volume/length the amount is the pack **total**, so only
> **multiplier** divides the price. **count** is recorded but never multiplies
> a total. For count/item, `count` is the divisor.

So `Laughing Cow 10s 200g @ $5` → `$5 ÷ 0.2kg = $25/kg` — the 10 pieces are
kept as information but don't distort the weight. This split — capture here,
compute there — is why the numbers stay right.
