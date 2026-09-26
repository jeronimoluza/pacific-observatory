"""expatistan: "12 eggs, large" is twelve eggs.

English "eggs" is not a count noun in the shared library, so the name was
sizeless and Stage B imputed the leaf mode (12 in New Zealand, by luck). The
count is stated; read it.

Measured 2026-09-26: one name, 322 product rows (one per city), 33 countries.
"""

import re

from prices.enrich.regex_patterns.types import Intent, PackPattern, SourcePatch

_EGGS = PackPattern(
    id="EXPATISTAN_N_EGGS",
    regex=re.compile(r"(?i)^\s*(?P<count>\d+)\s+eggs\b"),
    groups=("count",),
    lang="any",
    role="extract",
    kind="extra_count",
    bucket="count_pack",
)

PATCH = SourcePatch(
    additions=(_EGGS,),
    intent={
        "EXPATISTAN_N_EGGS": Intent(
            why="'12 eggs, large' states a count of 12",
            expect="item -> count",
            rows=322,
            examples=("12 eggs, large",),
        ),
    },
)
