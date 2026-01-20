"""
Usability classification for product quantity extraction.

This module classifies each product into a usability status based on the
quality and type of quantity information extracted. The classification
determines whether a product's unit price can be reliably calculated.

Classification statuses:
- RESOLVED_MASS: Product has a clear mass-based quantity (e.g., "500g", "1kg")
- RESOLVED_VOLUME: Product has a clear volume-based quantity (e.g., "1L", "500ml")
- RESOLVED_COUNT_FOOD: Food product sold by count (e.g., "6 eggs", "12 rolls")
- PROMOTION_OR_BUNDLE: Product is promotional/bundle (excluded from unit price)
- AMBIGUOUS_QUANTITY: Multiple conflicting quantities found
- UNIT_ONLY_NON_FOOD: Count-only non-food product (e.g., "4 pack batteries")
- UNRESOLVED: Cannot determine reliable quantity
"""

from enum import Enum
from typing import Optional, Tuple

from quantity_candidates import QuantityExtractionResult
from promotion_detection import detect_promotion, is_bundle_product
from regex_config import FOOD_COUNT_KEYWORDS


class UsabilityStatus(str, Enum):
    """Usability classification for products."""

    RESOLVED_MASS = "resolved_mass"
    RESOLVED_VOLUME = "resolved_volume"
    RESOLVED_LENGTH = "resolved_length"
    RESOLVED_COUNT_FOOD = "resolved_count_food"
    PROMOTION_OR_BUNDLE = "promotion_or_bundle"
    AMBIGUOUS_QUANTITY = "ambiguous_quantity"
    UNIT_ONLY_NON_FOOD = "unit_only_non_food"
    UNRESOLVED = "unresolved"


# Statuses that indicate a resolved (usable) product
RESOLVED_STATUSES = {
    UsabilityStatus.RESOLVED_MASS,
    UsabilityStatus.RESOLVED_VOLUME,
    UsabilityStatus.RESOLVED_LENGTH,
    UsabilityStatus.RESOLVED_COUNT_FOOD,
}


def is_food_coicop(coicop_code: Optional[str]) -> Optional[bool]:
    """
    Check if a COICOP code indicates a food product.

    Food products are in COICOP division 01 (Food and non-alcoholic beverages).

    Args:
        coicop_code: The COICOP code (e.g., "01.1.1.1")

    Returns:
        True if the product is food (COICOP 01.x.x.x)
        False if the product is not food (other COICOP codes)
        None if no COICOP code provided (use keyword fallback)
    """
    if not coicop_code or not isinstance(coicop_code, str):
        return None  # Unknown - use keyword fallback

    # COICOP codes starting with "01" are food
    return coicop_code.startswith("01")


def contains_food_keywords(product_name: str) -> bool:
    """
    Check if product name contains keywords indicating food items.

    This is used as a fallback when COICOP code is not available.

    Args:
        product_name: The product name

    Returns:
        True if food keywords are found
    """
    if not isinstance(product_name, str):
        return False

    product_lower = product_name.lower()

    for keyword in FOOD_COUNT_KEYWORDS:
        # Use word boundary matching to avoid partial matches
        # e.g., "apple" should match "apple" but not "pineapple"
        import re

        if re.search(rf"\b{re.escape(keyword)}\b", product_lower):
            return True

    return False


def classify_usability(
    extraction_result: QuantityExtractionResult,
    product_name: str,
    coicop_code: Optional[str] = None,
) -> Tuple[UsabilityStatus, Optional[str]]:
    """
    Classify the usability of a product based on its quantity extraction.

    Decision tree:
    1. Promotion detected → PROMOTION_OR_BUNDLE
    2. Multiple conflicting quantities → AMBIGUOUS_QUANTITY
    3. Resolved with mass unit → RESOLVED_MASS
    4. Resolved with volume unit → RESOLVED_VOLUME
    5. Resolved with length unit → RESOLVED_LENGTH
    6. Count-based AND food (COICOP 01.x or food keywords) → RESOLVED_COUNT_FOOD
    7. Count-based AND not food → UNIT_ONLY_NON_FOOD
    8. Otherwise → UNRESOLVED

    Args:
        extraction_result: The quantity extraction result
        product_name: The original product name
        coicop_code: Optional COICOP classification code

    Returns:
        Tuple of (UsabilityStatus, rejection_reason) where rejection_reason
        explains why a product was not resolved (or None if resolved)
    """
    # Step 1: Check for promotions/bundles
    is_promo, promo_type = detect_promotion(product_name)
    if is_promo:
        return UsabilityStatus.PROMOTION_OR_BUNDLE, f"promotion_detected:{promo_type}"

    # Also check if it's a bundle product
    if is_bundle_product(
        product_name,
        extraction_result.raw_amount,
        extraction_result.raw_units,
    ):
        return UsabilityStatus.PROMOTION_OR_BUNDLE, "bundle_product_detected"

    # Step 2: Check for ambiguous/conflicting quantities
    if extraction_result.has_conflicting_quantities:
        return UsabilityStatus.AMBIGUOUS_QUANTITY, "multiple_conflicting_quantities"

    # Also flag if there are multiple candidates with additive patterns
    if extraction_result.has_additive_pattern and extraction_result.n_candidates > 1:
        return (
            UsabilityStatus.AMBIGUOUS_QUANTITY,
            "additive_pattern_with_multiple_candidates",
        )

    # Step 3-5: Check for resolved mass/volume/length
    primary = extraction_result.primary_candidate

    if primary:
        if primary.candidate_type == "mass":
            return UsabilityStatus.RESOLVED_MASS, None
        elif primary.candidate_type == "volume":
            return UsabilityStatus.RESOLVED_VOLUME, None
        elif primary.candidate_type == "length":
            return UsabilityStatus.RESOLVED_LENGTH, None

    # Step 6-7: Check for count-based products
    count_candidates = [
        c for c in extraction_result.candidates if c.candidate_type == "count"
    ]

    if count_candidates or extraction_result.raw_units not in (None, "1"):
        # Has count information - check if it's food
        # Priority: 1) COICOP code (authoritative), 2) keyword fallback
        coicop_is_food = is_food_coicop(coicop_code)

        if coicop_is_food is True:
            # COICOP says it's food - trust it
            return UsabilityStatus.RESOLVED_COUNT_FOOD, None
        elif coicop_is_food is False:
            # COICOP says it's NOT food - trust it
            return UsabilityStatus.UNIT_ONLY_NON_FOOD, "count_only_non_food_product"
        else:
            # No COICOP code - use keyword fallback
            if contains_food_keywords(product_name):
                return UsabilityStatus.RESOLVED_COUNT_FOOD, None
            else:
                return UsabilityStatus.UNIT_ONLY_NON_FOOD, "count_only_non_food_product"

    # Step 8: Unresolved
    if extraction_result.n_candidates == 0:
        return UsabilityStatus.UNRESOLVED, "no_quantity_found"
    else:
        return UsabilityStatus.UNRESOLVED, "unable_to_determine_standard_unit"


def get_standard_unit(
    extraction_result: QuantityExtractionResult,
    usability_status: UsabilityStatus,
) -> Optional[str]:
    """
    Get the standard unit for a product based on its extraction and status.

    Standard units:
    - Mass: 'kg'
    - Volume: 'lt'
    - Length: 'mt'
    - Count: 'count'

    Args:
        extraction_result: The quantity extraction result
        usability_status: The usability classification

    Returns:
        Standard unit string or None if not resolved
    """
    if usability_status not in RESOLVED_STATUSES:
        return None

    if usability_status == UsabilityStatus.RESOLVED_MASS:
        return "kg"
    elif usability_status == UsabilityStatus.RESOLVED_VOLUME:
        return "lt"
    elif usability_status == UsabilityStatus.RESOLVED_LENGTH:
        return "mt"
    elif usability_status == UsabilityStatus.RESOLVED_COUNT_FOOD:
        return "count"

    return None


def is_resolved(status: UsabilityStatus) -> bool:
    """
    Check if a usability status indicates a resolved product.

    Args:
        status: The usability status

    Returns:
        True if the product is resolved and suitable for unit price calculation
    """
    return status in RESOLVED_STATUSES
