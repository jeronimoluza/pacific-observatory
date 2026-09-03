"""Per-leaf `sold_by_item` prior for the consumable unit-value deliverable.

Disambiguates the two products that both land on ``pricing_basis == "item"``:

  1. GENUINE per-item commodity -- the good is naturally priced per piece
     (a pineapple, a coconut, a lettuce). The scraped price IS the unit value;
     the row is trustworthy even though extract() found no mass/volume marker.
  2. MISSING-QUANTITY parse failure -- a good that is really sold by weight or
     volume (loose flour, bulk oil) whose product name happened to omit the
     "500 g" / "1 L" token, so extract() fell back to `item`. The price of an
     unknown quantity is meaningless for unit-value aggregation.

A single row cannot tell these apart; the discriminator is the COICOP leaf
(the commodity), so the decision is authored ONCE per leaf here. This rides the
same human-authored, food-only posture as the Layer-1 basis denylist: only
leaves whose commodity is genuinely a per-item sale are listed. Everything not
listed defaults to False -- its `item` rows are quarantined as
``review_missing_qty`` (retained, flagged, never shipped), never fabricated
into trusted unit values. Precision-first: under-cover rather than mis-trust.

Authoring contract: add a leaf here ONLY when the commodity is inherently sold
as an indivisible piece in the source markets. When in doubt, leave it out --
the default is the safe (quarantine) branch. `count`-basis rows are never
routed through this prior: they carry an explicit piece marker and are always
trustworthy.
"""

from __future__ import annotations

import logging

import pandas as pd

from prices.build.leaf_typical_mass import (
    MEASURED_BASES,
    UNIT_TO_BASIS,
    accepted_lookup,
    derive_typical_mass,
    write_typical_mass,
)

logger = logging.getLogger(__name__)

# COICOP leaves whose `item`-basis rows are GENUINE per-piece unit values.
# Human-authored, F&B-only. Keep this conservative -- an over-broad entry
# ships missing-quantity garbage as trusted. Every entry is a claim that the
# commodity is naturally an indivisible per-piece sale in the source markets.
SOLD_BY_ITEM_LEAVES: frozenset[str] = frozenset(
    {
        # Batch 1 (2026-08-03) -- authored from the review_missing_qty backlog. Each
        # leaf is piece-dominant (or cut-portion with a tight, unimodal price) with
        # negligible loose/per-kg contamination and a plausible cheap per-piece USD
        # median. Rationale + evidence: docs/sessions/2026-08-03-sold-by-item-leaves.md
        "01.1.6.1.1",  # Avocados, fresh
        "01.1.6.1.5",  # Mangoes, guavas and mangosteens, fresh
        "01.1.6.1.6",  # Papayas, fresh
        "01.1.6.1.7",  # Pineapples, fresh
        "01.1.6.1.8",  # Coconuts, fresh
        "01.1.6.2.1",  # Pomelos and grapefruits, fresh
        "01.1.6.2.2",  # Lemons and limes, fresh
        "01.1.6.3.2",  # Pears and quinces, fresh
        "01.1.7.1.4",  # Lettuce and chicory, fresh or chilled (sold per head)
        "01.1.7.4.8",  # Green maize / green corn (sold per cob)
        # DEFER (per-kg contamination too high for a leaf-level call; unlock via a
        # row-level loose guard first): 01.1.6.3.1 apples, 01.1.6.2.3 oranges.
        # REJECT (weighed/packaged): grapes, bananas, cherries, plums, strawberries,
        # kiwi, watermelons, all dried/nuts/canned/frozen/tofu, most 01.1.7.x veg.
    }
)


def is_sold_by_item(coicop_code) -> bool:
    """True iff this leaf's `item`-basis rows are genuine per-piece unit values."""
    if coicop_code is None or pd.isna(coicop_code):
        return False
    return str(coicop_code) in SOLD_BY_ITEM_LEAVES


def convert_item_rows(
    df: pd.DataFrame, table: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Route every `item`-basis row into one of three buckets, and tag provenance.

    The three buckets, in strict priority order:

      1. GENUINE per-piece (`SOLD_BY_ITEM_LEAVES`) -- left exactly as it was.
         Checked FIRST, so a leaf already declared per-piece can never be
         converted, even if it happens to have a stable derived mass. The
         ordering is load-bearing, not cosmetic: pineapples carry a spurious
         0.02 kg entry in the mass table that this priority renders inert.
      2. CONVERTIBLE -- the leaf has an accepted typical mass, so the row is
         relabeled as a mass/volume row carrying that amount. It then flows
         through the unchanged unit-value, Layer-2 and QA stages exactly like a
         measured row, which is why none of those needed modifying.
      3. STILL MISSING QUANTITY -- no accepted mass, so the row is untouched and
         quarantines downstream as before.

    Rows are tagged in ``mass_source`` (`measured`, `genuine_item`,
    `derived_typical`, or unset) so a downstream consumer can always exclude
    conversions. A derived row must never be mistakable for a measured one.

    The mass table is derived from THIS frame rather than read from the build's
    own output parquet, which would make the build depend on its previous run.
    That holds for a full build. A build covering part of the corpus must pass
    `table` instead: derive_typical_mass groups by coicop_code across every
    country, so re-deriving it from a slice gives a leaf a typical mass drawn
    from the slice alone, and the converted rows then disagree with the full
    build for reasons unrelated to whatever is being tested. A supplied table is
    used as-is and never rewritten, so a slice cannot overwrite the pin it read.
    """
    if df.empty:
        return df
    df = df.copy()

    if table is None:
        table = derive_typical_mass(df)
        write_typical_mass(table)
    typical = accepted_lookup(table)

    df["mass_source"] = pd.NA
    df.loc[df["pricing_basis"].isin(MEASURED_BASES), "mass_source"] = "measured"

    is_item = df["pricing_basis"] == "item"
    genuine = is_item & df["coicop_code"].apply(is_sold_by_item)
    df.loc[genuine, "mass_source"] = "genuine_item"

    candidates = is_item & ~genuine
    if not typical or not candidates.any():
        return df

    mapped = df.loc[candidates, "coicop_code"].astype(str).map(typical)
    convertible = mapped[mapped.notna()]
    if convertible.empty:
        logger.info(
            "typical-mass conversion: 0 of %d candidate item rows convertible",
            int(candidates.sum()),
        )
        return df

    idx = convertible.index
    units = convertible.apply(lambda t: t[1])
    df.loc[idx, "amount_value"] = convertible.apply(lambda t: t[0])
    df.loc[idx, "standard_unit"] = units
    df.loc[idx, "pricing_basis"] = units.map(UNIT_TO_BASIS)
    df.loc[idx, "mass_source"] = "derived_typical"

    logger.info(
        "typical-mass conversion: %d of %d candidate item rows converted "
        "(%d genuine per-piece left untouched)",
        len(idx),
        int(candidates.sum()),
        int(genuine.sum()),
    )
    return df
