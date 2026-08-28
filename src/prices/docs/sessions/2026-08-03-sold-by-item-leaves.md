# 2026-08-03 — Populating `SOLD_BY_ITEM_LEAVES` from the `review_missing_qty` backlog

## Goal

Whole per-piece produce (a pineapple, a coconut, a lettuce head) is scraped with
no weight token, so `extract()` falls back to `pricing_basis='item'` with
`amount_value=NULL`. Downstream QA quarantines every `item`-basis row as
`review_missing_qty` unless its COICOP leaf is on the
`build/sold_by_item.py::SOLD_BY_ITEM_LEAVES` allowlist. The allowlist shipped
**empty**, so these leaves currently ship **0 trusted rows**. This session reads
the actual quarantined observations and authors the first precision-first batch.

The decision lives downstream at the unit-value/QA seam **by design** — not at
classify. No re-embed, no re-classify; only `qa_quantity` flips, so a candidate's
exact yield can be simulated off the existing `eap_fnb_observations.parquet`
without any rebuild.

## Data checked

`data/prices/build/eap_fnb_observations.parquet` (2026-08-01 build, 1,198,637
finalized rows). `qa_status` breakdown:

| qa_status | rows |
|---|---|
| trusted | 845,325 |
| **review_missing_qty** | **208,648** |
| review_uv_outlier | 142,267 |
| review_fx | 1,878 |
| review_zero_price | 519 |

All 208,648 `review_missing_qty` rows are `pricing_basis == 'item'` (the only
path to that status). 23,812 of them fall in fruit (`01.1.6`) + veg (`01.1.7`).

## The core tension: leaf-level is a *lossy* discriminator

The `sold_by_item` design assumes a leaf's commodity is "inherently sold as an
indivisible piece." The data shows that is **only partly true**: within almost
every produce leaf the *same* commodity is sold both

- **per-piece** — `Apple Each`, `Pineapple 1 Unit`, `Pomelo 1 Unit`, `(1Pc)` —
  the scraped price *is* the per-piece unit value; and
- **loose / by weight** — `Pink Lady Apples Loose`, `GRAPES RED SEEDLESS FLAME
  KG`, `Navel Oranges Loose` — the scraped price is a **per-kg** figure with the
  quantity lost.

`basis='item'` collapses both. Enabling a leaf therefore trusts its loose/per-kg
rows *as if* per-piece, fabricating a wrong (≈per-kg) unit value for them.

### Why `… KG` is not caught upstream

Every mass/volume pattern in `extract_patterns.py` requires a **numeric** value
glued to the unit — `(?P<value>\d+…)(?P<unit>kg|KG|…)`. A **bare** `KG`
(`GRAPES RED SEEDLESS FLAME KG`) has no number, so nothing matches and the row
falls to `item`. This is the textbook "MISSING-QUANTITY parse failure": the name
signals sold-by-weight but carries no amount, so there is no unit-value
denominator. Working as intended — and a direct confirmation that such leaves
(grapes) must stay **off** the allowlist.

**Corollary / future refinement:** a bare weight/loose marker (`KG`, `/kg`,
`per kg`, `Loose`) inside an `item` name is a strong *negative* signal. Excluding
those rows *within* an enabled leaf (a row-level guard, not a leaf-level one)
would let us safely turn on the big piece-dominant-but-loose-contaminated leaves
later (apples, oranges). Not done this pass — see backlog.

## Two safety nets make a leaf-level call defensible anyway

1. **Enable only where PIECE clearly dominates LOOSE** with a tight price spread.
2. **Layer-2 unit-value audit** (`flag_uv_outliers` over
   `(coicop, country, standard_unit='item')`) already runs *after* QA and
   quarantines the residual per-kg outliers as `review_uv_outlier`. So a few
   loose contaminants inside a piece-dominant leaf do **not** ship.

## Evidence (per leaf: piece/loose share + per-piece USD sanity)

Two signals decide each leaf. **PIECE% vs LOOSE%** (regex over product names:
`each`/`1 pc`/`1 Unit`/`(1Pc)`/`個`/`粒` vs `loose`/`kg`/`/kg`/`per kg`) and the
**per-piece `unit_value_usd`** of the would-ship rows. Genuine per-piece produce
clusters at **$0.9–2.5 with a moderate spread**; packs/trays/per-kg goods betray
themselves as a high median ($4+) or a huge p90 tail.

| leaf | title | item rows | %piece | %loose | med USD | p90 USD | verdict |
|---|---|---|---|---|---|---|---|
| 01.1.6.2.1 | Pomelos & grapefruits | 138 | 93 | 0 | 2.33 | 3.54 | **ENABLE** |
| 01.1.6.1.1 | Avocados | 274 | 78 | 1 | 1.93 | 4.93 | **ENABLE** |
| 01.1.6.3.2 | Pears & quinces | 380 | 76 | 8 | 0.99 | 4.50 | **ENABLE** |
| 01.1.6.1.7 | Pineapples | 469 | 72 | 0 | 1.96 | 3.91 | **ENABLE** |
| 01.1.6.2.2 | Lemons & limes | 481 | 71 | 0 | 0.90 | 1.27 | **ENABLE** |
| 01.1.6.1.8 | Coconuts | 150 | 53 | 0 | 2.50 | 4.87 | **ENABLE** |
| 01.1.6.1.5 | Mangoes/guavas/mangosteens | 496 | 40 | 2 | 2.11 | 5.50 | **ENABLE** † |
| 01.1.6.1.6 | Papayas | 330 | 16 | 5 | 1.32 | 3.87 | **ENABLE** † |
| 01.1.7.1.4 | Lettuce & chicory | 808 | 75 | 7 | 1.52 | 4.22 | **ENABLE** (per head) |
| 01.1.7.4.8 | Green maize (corn) | 450 | 52 | 3 | 1.00 | 13.24 | **ENABLE** (per cob) |
| 01.1.6.3.1 | Apples | 2879 | 65 | 9 | 2.20 | 6.52 | DEFER (per-kg tail; row-guard first) |
| 01.1.6.2.3 | Oranges | 707 | 74 | 20 | 1.47 | 3.53 | DEFER (20% loose) |
| 01.1.6.5.2 | Kiwi fruits | 213 | 52 | 0 | 3.94 | 27.25 | REJECT (punnet/tray) |
| 01.1.6.5.4 | Watermelons | 427 | 2 | 23 | 2.23 | 7.40 | REJECT (cut = weighed) |
| 01.1.6.5.1 | Grapes | 409 | 0 | 53 | 4.42 | 11.64 | REJECT (weighed) |
| 01.1.6.1.2 | Bananas | 190 | 0 | 34 | 1.98 | 2.41 | REJECT (per bunch/kg) |
| 01.1.6.3.4 | Cherries | 75 | 88 | 9 | 15.75 | 19.05 | REJECT (per kg/pack) |
| 01.1.6.3.6 | Plums | 64 | 0 | 86 | 16.21 | 16.43 | REJECT (per kg) |
| 01.1.6.4.5 | Strawberries | 156 | 42 | 5 | 11.54 | 23.61 | REJECT (per tray) |
| 01.1.6.7.* / 8.* / 9.* | dried / nuts-in-shell / prepared | — | — | — | — | — | REJECT (packaged) |
| 01.1.7.2.4 / 2.2 / 4.1 / 4.2 / 4.3 / 5.1 … | tomato/cucumber/carrot/garlic/onion/potato | — | low | high | — | — | REJECT (normally weighed) |
| 01.1.7.9.* | tofu/canned/frozen/processed | — | low | — | — | — | REJECT (packaged) |

† `01.1.6.1.5` and `01.1.6.1.6` are ambig-dominated (the modal product is a
`CUT MANGO` / `CUT PAPAYA` portion). A cut half sold as one physical unit at one
price is a valid per-piece observation; the tight price MAD (0.08 / 0.04) and
plausible median confirm the cell is unimodal. Included, but the softest two.

## Decision — first batch (10 leaves)

Precision-first: enable only leaves that are piece-dominant (or ambig-with-tight-
price), ≤8% loose, and land at a plausible cheap per-piece USD median. Everything
in doubt is left off.

| # | leaf | commodity |
|---|---|---|
| 1 | 01.1.6.1.1 | Avocados |
| 2 | 01.1.6.1.5 | Mangoes, guavas and mangosteens |
| 3 | 01.1.6.1.6 | Papayas |
| 4 | 01.1.6.1.7 | Pineapples |
| 5 | 01.1.6.1.8 | Coconuts |
| 6 | 01.1.6.2.1 | Pomelos and grapefruits |
| 7 | 01.1.6.2.2 | Lemons and limes |
| 8 | 01.1.6.3.2 | Pears and quinces |
| 9 | 01.1.7.1.4 | Lettuce and chicory (per head) |
| 10 | 01.1.7.4.8 | Green maize / corn (per cob) |

**Simulated yield** (rows that flip to `trusted` — i.e. also pass Layer-2 + FX):
avocado 265, mango 462, papaya 327, pineapple 445, coconut 148, pomelo 134,
lemon/lime 427, pears 357, lettuce 794, corn 417 → **≈3,774 new trusted
per-piece observations**.

**Net-new leaves: only 2** — `01.1.6.1.7` pineapple and `01.1.6.1.8` coconut.
The other 8 leaves ALREADY ship trusted rows via their kg/count cells (verified
against `eap_fnb_trusted_observations.parquet`, 175 shipped leaves); enabling
them adds a per-*piece* `standard_unit='item'` cell alongside the existing
per-kg/count series, it does not light up an empty leaf. The value here is depth
+ correctness (a comparable per-piece series), not leaf count.

## Proposal 1 prototype — bare `KG`/`/kg` → mass, amount 1 kg (SHIPPED to extract, un-rerun)

Superseding the "exclude the loose rows" idea: a bare weight marker means the
price is *already per standard unit*, so **recover** it as a per-kg cell rather
than drop it. `extract()`'s rung 5 (`basis_marker`) already emits
`mass, amount=1.0, unit_value=price`; the only gap was the **detector**, which
required the literal word `per` (`PER_KG: \b[Pp]er\s+[Kk][Gg]\b`). Widened it:

- `pack_basis.yaml::basis_markers` += `SLASH_KG` `(?<![A-Za-z])/\s*[Kk][Gg]\b`,
  `BARE_KG` `\b[Kk][Gg]\b(?![-\w])`, `SLASH_LITRE` `(?<![A-Za-z])/\s*[Ll]\b`.
- `buckets/per_unit_marker.py` += the three ids; `grammar.py::_META` += three
  entries with **`lang="any"`** (the kg/L symbol is language-universal, so this
  also rescues CJK/Thai names — unlike the `en`-only `per` markers).

Guard-tested against the real `extract()`: every `500g`/`1L`/`5kg` still wins
(rung 3/4 precede rung 5), per-piece `Apple Each`/`Pineapple 1 Unit` stay `item`.
The tightened regexes killed two false positives — product code `KG-20N` and size
`S/M/L`. Corpus impact: **2,176 item rows** recovered as per-kg/L cells; only **2**
count-basis rows affected (`Pork 2 Pack (KG)`, defensibly per-kg). Recovered
medians are all real per-kg prices (poultry $6.09, beef $10.11, grapes $8.10,
apples $4.29, onions $2.65, carrots $1.92). Recovers **weighed** commodities that
are correctly *off* the per-piece allowlist — a distinct per-kg surface.

Not yet re-run: this is an `extract()` (structural) change, so it needs a re-run
of the structural stages → merge → build (rewrites `classified.parquet` structural
fields; **no re-embed**), plus a `prices eval` check on `pricing_basis`/
`standard_unit` gold accuracy before commit.

## Backlog

- **Row-level loose guard** — treat a bare weight/loose marker in an `item` name
  as missing-quantity even inside an enabled leaf. Unlocks apples (2,879 rows)
  and oranges safely. NB: Proposal 1 above only catches an explicit `kg` token;
  `Loose`-tagged rows (no unit token) still need this guard or leaf-enabling.
- **DEFER leaves** (apples, oranges, cucumbers, eggplant, leeks, whole melons)
  pending the row-guard or a per-country cut.
- After the batch is confirmed: re-run `prices build` **only** (no re-classify),
  verify the 10 leaves appear in `eap_fnb_trusted_observations.parquet` with sane
  per-piece prices, then regenerate the consumable_datasets + README. Net-new
  leaves are only ~3 (pineapple, coconut, plums); 175 → ~178. Both changes are
  depth/correctness wins, not leaf-count wins — lighting up the ~60 addressable
  empty leaves is a **corpus/sourcing** problem, not a parsing one.
