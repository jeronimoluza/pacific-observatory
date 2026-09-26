r"""sayurbox: spelled-out "gram" size word.

Same gap as pasar_segar (see that patch's docstring for the full reasoning):
sayurbox names spell "gram" out in full ("Shortplate Sliced Beef US 250
gram", "Keju Meg 160 gram", "Himalayan Salt Pura 125 gram") and units.yaml
has no spelled-out "gram" surface, so these fell to `item` with no size.

Value is `\\d+(?:,\\d+)?` (comma-decimal allowed, no bare dot) for the same
reason as pasar_segar: the shared value parser always does
`float(value.replace(",", "."))` with no thousands-grouping awareness, and a
bare dot would misread an Indonesian thousands-grouped size ("1.000 ml", "1.500
ml", seen in sayurbox names) 1000x too small. Neither example seen in
sayurbox uses "gram" together with a dot-grouped value, so nothing is known
to be excluded by this choice here, but it is kept consistent with the
pasar_segar patch as a standing rule for this country's sources.

A `(?<!\d)(?<!x )` lookbehind excludes "gram" preceded by an "x " multiplier
("Nutella Wafer B-Ready Chocolate Isi 6 pcs x 22 gram", "Oatside Oat Cereal
Bar Chocolate 6 x 18 gram" / "12 x 18 gram"): rulecheck's own count_loss check
only caught the first of these (a pre-existing count > 1 collapsing to 1);
the other two were a silent multiplier miss it cannot see (per-piece 18 g
read as the item's whole size when the true total is 6x/12x that), the same
"count beside a size becomes the multiplier" trap the Vietnam pilot
documented. The plain `(?<!x )` lookbehind alone was not enough: `re.search`
just retries one character later inside the same number ("22" -> "2"), so
`(?<!\d)` is required first to stop the match from ever starting mid-number.
All three are left as `item` (unchanged) rather than a plausible-looking but
wrong single-piece size; a correct total needs a multiplier reading this
patch does not attempt.

Measured 2026-09-26 with `rulecheck source sayurbox` (sayurbox is
indonesia-only): 112 rows move, all item -> mass, 0 count_loss. Verdict:
model_review.
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch, UnitEmit

_GRAM = PackPattern(
    id="SAYURBOX_GRAM",
    regex=re.compile(r"(?<!\d)(?<!x )(?P<value>\d+(?:,\d+)?)\s*gram\b", re.IGNORECASE),
    groups=("value",),
    lang="any",
    role="extract",
    kind="extra_unit",
    bucket="single_measure",
    unit_emit=UnitEmit(basis="mass", su="kg", mul=0.001),
)

PATCH = SourcePatch(
    additions=(_GRAM,),
    intent={
        "SAYURBOX_GRAM": Intent(
            why="spelled-out 'gram' states the size in grams",
            expect="item -> mass",
            rows=112,
            examples=(
                "Shortplate Sliced Beef US 250 gram",
                "Ikan Cakalang  500 gram",
                "Keju Meg 160 gram",
                "Himalayan Salt Pura 125 gram",
                "Biskuit Sandwich Ritz 91 gram",
            ),
        ),
    },
)
