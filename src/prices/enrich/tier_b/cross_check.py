"""Deprecated location — moved to `prices.enrich.cross_check`.

Re-export shim kept only until the tier_b package is removed. New code must
import from `prices.enrich.cross_check`.
"""

from prices.enrich.cross_check import (  # noqa: F401
    append,
    build_row,
    canonical_unit_for_basis,
    consolidate,
    lookup_allowed_bases,
)
