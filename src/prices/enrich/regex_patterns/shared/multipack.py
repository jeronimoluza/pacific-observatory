"""Language-agnostic multipack patterns (pack_patterns.yaml::patterns - canonicalization role).

Translated verbatim from static/pack_patterns.yaml; re.IGNORECASE matches the
existing loader at extract.py. The trailing "Nx" pattern (multipack_n_x_only)
lives in multipack_trailing.py because, in the consumed canon order, the
language-specific multipack_pcs_en (lang/en) sorts between these and it — the
file split is the order source-of-truth (Phase 0.5 / Plan 04).
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
    # "20x1.5g", "4x90g", "12 x 500ml"  → count=20, value=1.5, unit=g
    PackPattern(
        id="multipack_num_x_value_unit",
        regex=re.compile(
            r"(?P<count>\d+)\s*[x×X]\s*(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>ml|mL|ML|l|L|kg|KG|g|G|mg|MG|gm|GM|gr|GR|oz|OZ|lb|LB)\b",
            re.IGNORECASE,
        ),
        groups=("count", "value", "unit"),
        lang="any",
        role="canonicalization",
        kind="canon",
    ),
    # "5kg(5kg×1)" or "5kg x 1" — pack-of-1 explicit  → count=1, value=5, unit=kg
    PackPattern(
        id="multipack_value_unit_x_count",
        regex=re.compile(
            r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>ml|mL|ML|l|L|kg|KG|g|G|mg|MG|gm|GM|gr|GR|oz|OZ|lb|LB)\s*[x×X]\s*(?P<count>\d+)\b",
            re.IGNORECASE,
        ),
        groups=("count", "value", "unit"),
        lang="any",
        role="canonicalization",
        kind="canon",
    ),
)
