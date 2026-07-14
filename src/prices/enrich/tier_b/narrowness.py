"""Deprecated location — moved to `prices.enrich.coicop_codes`.

Re-export shim kept only until the tier_b package is removed. New code must
import from `prices.enrich.coicop_codes`.
"""

from prices.enrich.coicop_codes import (  # noqa: F401
    is_narrow,
    parse_codes,
    resolved_code,
    serialize_codes,
)
