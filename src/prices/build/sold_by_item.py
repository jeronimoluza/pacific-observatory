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

import pandas as pd

# COICOP leaves whose `item`-basis rows are GENUINE per-piece unit values.
# Human-authored, F&B-only. Keep this conservative -- an over-broad entry
# ships missing-quantity garbage as trusted. Every entry is a claim that the
# commodity is naturally an indivisible per-piece sale in the source markets.
SOLD_BY_ITEM_LEAVES: frozenset[str] = frozenset({
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
})


def is_sold_by_item(coicop_code) -> bool:
    """True iff this leaf's `item`-basis rows are genuine per-piece unit values."""
    if coicop_code is None or pd.isna(coicop_code):
        return False
    return str(coicop_code) in SOLD_BY_ITEM_LEAVES
