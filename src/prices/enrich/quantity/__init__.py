"""
Quantity extraction and classification subpackage.

This subpackage provides utilities for extracting quantities from product names,
classifying their usability, detecting promotions, and converting units.
"""

# Public API exports
from .extraction import extract_quantities, merge_quantities_with_gemini
from .candidates import (
    extract_all_candidates,
    QuantityCandidate,
    MultiplicativeStructure,
)
from .usability import (
    classify_usability,
    get_standard_unit,
    get_extraction_tier,
    UsabilityStatus,
)
from .promotion import detect_promotion, is_bundle_product
from .conversions import UNIT_CONVERSIONS, WEIGHT_TO_KG, VOLUME_TO_LT, LENGTH_TO_MT
from .regex import (
    AMOUNT_REGEX,
    UNITS_REGEX,
    X_SEPARATOR_REGEX,
    PER_KG_REGEX,
    PER_EACH_REGEX,
    COUNT_UNITS,
    AMOUNT_UNITS,
    STOPWORDS,
    FOOD_COUNT_KEYWORDS,
)

__all__ = [
    # Main functions
    "extract_quantities",
    "merge_quantities_with_gemini",
    "extract_all_candidates",
    "classify_usability",
    "get_standard_unit",
    "get_extraction_tier",
    "detect_promotion",
    "is_bundle_product",
    # Data classes
    "QuantityCandidate",
    "MultiplicativeStructure",
    "UsabilityStatus",
    # Constants
    "UNIT_CONVERSIONS",
    "WEIGHT_TO_KG",
    "VOLUME_TO_LT",
    "LENGTH_TO_MT",
    "AMOUNT_REGEX",
    "UNITS_REGEX",
    "X_SEPARATOR_REGEX",
    "PER_KG_REGEX",
    "PER_EACH_REGEX",
    "COUNT_UNITS",
    "AMOUNT_UNITS",
    "STOPWORDS",
    "FOOD_COUNT_KEYWORDS",
]
