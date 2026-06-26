# Tier-a unit-value labeling schema spec (representation rules — v0.3)

You are labeling retail product names with their **structured unit-value tuple** for a
price-normalization system. For each product, output exactly these 5 fields. These are
**representation rules** — follow them exactly so your labels are comparable to the target
schema. They tell you HOW to express your answer, not what the answer is for any given row;
the judgment of what the product actually is remains yours. You see only the name + country,
never the machine's guess — label independently.

## Fields

1. **pricing_basis** — how the product is sold. One of:
   - `mass` — has a per-unit weight (g, kg, mg, oz, lb, 公斤/克 …)
   - `volume` — has a per-unit liquid volume (ml, l, cl, gallon, 毫升/公升 …)
   - `count` — sold as a number of discrete identical units (tablets, capsules, pcs, sheets,
     pieces, 入/錠/個/枚/箱/本/抽/包, Vietnamese miếng/viên/gói …) with **no** per-unit
     weight/volume given
   - `length` — priced by length of a length-good (rope, wire, fabric sold by the metre).
     **Not** a size spec.
   - `item` — a single product with no pack quantity that sets price, OR where the only number
     is a **size/dimension SPEC** (a 14 cm strainer, a 50 cm ruler, a 6.1-inch phone, a 24-port
     switch). A spec is not a unit → stays `item`. A book, a garment, a single device → `item`.

   **Basis precedence (schema rule — apply it):** if a per-unit **mass or volume** is present,
   basis is `mass`/`volume` even when a count also appears (`500mg 20 tablets` → `mass`; the 20
   is packaging). Use `count` only when there is no per-unit weight/volume. Use `item` when there
   is no consumable quantity at all.

   **Pharma dose-form carve-out (v0.3) — the one exception to precedence:** when a drug strength
   `<N>mg`/`mcg`/`µg` sits **directly before** a tablet/capsule form word (`5mg Tablet`,
   `250mg Capsule`, `100mcg Caplet`) with **no intervening pack count**, the number is the API
   **dose**, not a sellable weight — a per-kg price off a 5 mg pill is meaningless. Such a product
   is sold **per unit** → `pricing_basis=count`, `standard_unit=unit`, `amount_value=null`,
   `count=1`, `multiplier=1`. An explicit `(per Tablet)` / `(per Capsule)` marker forces the same.
   This OVERRIDES both the precedence rule and the single-unit rule below. It does **not** apply
   when a pack count breaks the adjacency (`500mg 20 tablets` keeps `mass` — the dose is per-unit
   but the 20-pack makes the listing a weighable pack), nor to non-dose masses (`Protein 1kg` is
   `mass`).

   **Single-unit rule (v0.2):** a count of exactly ONE (`1入`, `1pc`, `1 set`, a lone discrete
   item with no per-unit mass/volume) canonicalizes to `pricing_basis=item`, `standard_unit=item`,
   `count=1` — **not** `count`/`unit`/1. Use `count` only when there are 2+ discrete units.

   **Included-content rule (v0.2):** "included content" specs (a diffuser bottle that *contains*
   5 ml of oil, `含5ml`) are NOT the sellable measure → treat as `item`, not `volume`.

2. **amount_value** — the **per-unit** quantity in **canonical** units (for ONE unit, not the
   pack total):
   - mass → **kilograms**: `95g→0.095`, `1.5kg→1.5`, `500mg→0.0005`, `8oz→0.2268`
   - volume → **liters**: `500ml→0.5`, `1L→1.0`, `1 gallon→3.785`, `60ml→0.06`
   - count / item / length → `null`
   - For a stated mass/volume **range** (`800g-1Kg`), use the **lower bound**.

3. **standard_unit** — `kg` (mass), `lt` (volume), `unit` (count), `item` (item), `mt` (length)

4. **count** — integer count of discrete units when basis=`count` (`20 tablets`→20, `9入`→9,
   `1 dozen`/`1ダース`→12). For mass / volume / item → `1`.

5. **multiplier** — the **outer pack** multiplier: how many identical sub-packs/bundles
   (`500ml × 24`→24, `Pack of 2`→2, `3 x 100g`→3, `2本セット`→2, `8x50g`→8). Single unit, no
   outer pack → `1`. **A bare "N Pack" next to a single TOTAL mass/volume** (`24 Pack 1.8kg` =
   24 sausages totalling 1.8 kg) is NOT an outer multiplier of the stated total → `multiplier=1`.

## Worked examples (mirror these exactly)

| name | basis | amount_value | standard_unit | count | multiplier |
|---|---|---|---|---|---|
| Tuna Chunks 95g | mass | 0.095 | kg | 1 | 1 |
| Coke 500ml × 24本 | volume | 0.5 | lt | 1 | 24 |
| Soap 3 x 100g | mass | 0.1 | kg | 1 | 3 |
| Hot Dogs 8x50g | mass | 0.05 | kg | 1 | 8 |
| Vitamin C 20 tablets | count | null | unit | 20 | 1 |
| Paracetamol 500mg 20 tablets | mass | 0.0005 | kg | 1 | 1 |
| Norvasc Amlodipine 5mg Tablet | count | null | unit | 1 | 1 |
| Amoxicillin 250mg Capsule | count | null | unit | 1 | 1 |
| Milk 1 gallon | volume | 3.785 | lt | 1 | 1 |
| NIVEA Spray 150ml Pack Of 2 | volume | 0.15 | lt | 1 | 2 |
| 1ダース shuttlecocks | count | null | unit | 12 | 1 |
| Strainer 14cm | item | null | item | 1 | 1 |
| Shampoo Anti-Dandruff | item | null | item | 1 | 1 |
| Convertible Vehicle 1 set | item | null | item | 1 | 1 |
| Sausages 24 Pack 1.8kg | mass | 1.8 | kg | 1 | 1 |

## Out of scope (do not overthink)

- Contested basis philosophy (is a pill priced per-tablet or per-mg?) is resolved by the pharma
  dose-form carve-out above (v0.3): a bare `<N>mg Tablet`/`Capsule` is per-unit `count`, not mass.
  Follow it, don't relitigate.
- Promotions ("Buy 2 Take 1", coupons, %OFF) do not change the tuple. Label the product's own pack.
- Marketing words, store names, shipping tags (送料無料, 廠商直送, `| NTUC FairPrice`, Vietnamese
  `Mua` = "Buy", `tại …Store`) are noise.
