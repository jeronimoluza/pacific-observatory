"""
Usability classification for product quantity extraction.

This module classifies each product into a usability status based on the
quality and type of quantity information extracted. The classification
determines whether a product's unit price can be reliably calculated.

Classification statuses:
- RESOLVED_WEIGHT_VOLUME: Tier 1 match (kg, L, g, ml, etc.)
- RESOLVED_COUNT: Tier 2 match (pcs, dozen, pack, etc.)
- RESOLVED_PER_ITEM: Tier 3 fallback (no quantity detected)
- CONTRADICTORY: Conflicting quantities found
- PROMOTION_OR_BUNDLE: Product is promotional/bundle (excluded from unit price)
- PENDING_REVIEW: Flagged for manual review (still included provisionally)
"""

from enum import Enum
from typing import Optional, Tuple

from quantity_candidates import QuantityExtractionResult
from promotion_detection import detect_promotion, is_bundle_product
from regex_config import FOOD_COUNT_KEYWORDS


class UsabilityStatus(str, Enum):
    """Usability classification for products.

    Status model from design document:
    - resolved_weight_volume: Tier 1 match (kg, L, g, ml, etc.)
    - resolved_count: Tier 2 match (pcs, dozen, pack, etc.)
    - resolved_per_item: Tier 3 fallback (no quantity detected)
    - contradictory: Conflicting quantities found
    - promotion_or_bundle: Promotion keyword matched
    - pending_review: Flagged for manual review (still included provisionally)
    """

    RESOLVED_WEIGHT_VOLUME = "resolved_weight_volume"
    RESOLVED_COUNT = "resolved_count"
    RESOLVED_PER_ITEM = "resolved_per_item"
    CONTRADICTORY = "contradictory"
    PROMOTION_OR_BUNDLE = "promotion_or_bundle"
    PENDING_REVIEW = "pending_review"


# Statuses that indicate a resolved (usable) product for index inclusion
RESOLVED_STATUSES = {
    UsabilityStatus.RESOLVED_WEIGHT_VOLUME,
    UsabilityStatus.RESOLVED_COUNT,
    UsabilityStatus.RESOLVED_PER_ITEM,
    UsabilityStatus.PENDING_REVIEW,  # Included provisionally
}

# Statuses that exclude products from the index
EXCLUDED_STATUSES = {
    UsabilityStatus.CONTRADICTORY,
    UsabilityStatus.PROMOTION_OR_BUNDLE,
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

    Decision tree from design document:
    1. Promotion detected → PROMOTION_OR_BUNDLE (exclude)
    2. Tier 1: Weight/Volume found → RESOLVED_WEIGHT_VOLUME
    3. Tier 2: Count found → RESOLVED_COUNT
    4. Tier 3: No quantity → RESOLVED_PER_ITEM (include with quantity=1)
    5. Contradiction check → CONTRADICTORY (exclude)

    Args:
        extraction_result: The quantity extraction result
        product_name: The original product name
        coicop_code: Optional COICOP classification code

    Returns:
        Tuple of (UsabilityStatus, rejection_reason) where rejection_reason
        explains exclusion (or None if included)
    """
    # Step 1: Check for promotions/bundles FIRST (per design doc flow)
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

    # Step 5 (done early): Check for contradictory signals
    if extraction_result.has_conflicting_quantities:
        return UsabilityStatus.CONTRADICTORY, "multiple_conflicting_quantities"

    if extraction_result.has_additive_pattern and extraction_result.n_candidates > 1:
        return (
            UsabilityStatus.CONTRADICTORY,
            "additive_pattern_with_multiple_candidates",
        )

    # Step 2: Tier 1 - Weight/Volume
    primary = extraction_result.primary_candidate
    if primary and primary.candidate_type in ("mass", "volume", "length"):
        return UsabilityStatus.RESOLVED_WEIGHT_VOLUME, None

    # Step 3: Tier 2 - Count
    count_candidates = [
        c for c in extraction_result.candidates if c.candidate_type == "count"
    ]
    if count_candidates or (
        extraction_result.raw_units and extraction_result.raw_units != "1"
    ):
        return UsabilityStatus.RESOLVED_COUNT, None

    # Step 4: Tier 3 - Per-Item Fallback
    # Per design doc: "Products are compared item-to-item over time without unit normalization"
    return UsabilityStatus.RESOLVED_PER_ITEM, None


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
