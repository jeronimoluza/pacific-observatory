"""
Promotion and bundle detection for product names.

This module detects promotional products and bundles that should be excluded
from unit price calculations, as they represent non-standard pricing.

Examples of promotions:
- "Buy 2 get 1 free"
- "3 for $10"
- "Family pack"
- "Bonus 50g"

Examples of bundles:
- "Combo meal"
- "Value bundle"
- "Twin pack" (when context suggests promotional)
"""

import json
import re
from pathlib import Path
from typing import Optional, Tuple

from .regex import (
    PROMOTION_KEYWORDS,
    PROMOTION_PATTERNS_COMPILED,
    ADDITIVE_PATTERNS,
)


def load_promotion_keywords(project_root: Optional[Path] = None) -> dict:
    """
    Load promotion keywords from config/promotion_keywords.json.

    Args:
        project_root: Project root path. If None, infers from file location.

    Returns:
        Dict with 'global' and 'source_specific' keyword lists
    """
    if project_root is None:
        # Config is in src/cpi/coicopping/config/ relative to this file
        config_path = Path(__file__).parent / "config" / "promotion_keywords.json"
    else:
        config_path = (
            project_root
            / "src"
            / "cpi"
            / "coicopping"
            / "config"
            / "promotion_keywords.json"
        )

    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)

    # Fallback to hardcoded defaults (from PROMOTION_KEYWORDS constant)
    return {"global": list(PROMOTION_KEYWORDS), "source_specific": {}}


def get_keywords_for_source(
    source: Optional[str] = None, project_root: Optional[Path] = None
) -> set:
    """
    Get combined promotion keywords for a specific source.

    Args:
        source: Source name (e.g., 'samoa_market'). If None, returns global only.
        project_root: Project root path.

    Returns:
        Set of all applicable keywords (global + source-specific)
    """
    config = load_promotion_keywords(project_root)
    keywords = set(kw.lower() for kw in config.get("global", []))

    if source and source in config.get("source_specific", {}):
        source_keywords = config["source_specific"][source]
        keywords.update(kw.lower() for kw in source_keywords)

    return keywords


# Phrases that contain promotion keywords but are NOT promotions
# These are product descriptions, not promotional indicators
FALSE_POSITIVE_PHRASES = [
    "free range",  # Egg/chicken description
    "free-range",
    "free from",  # Allergen-free products
    "gluten free",
    "gluten-free",
    "sugar free",
    "sugar-free",
    "fat free",
    "fat-free",
    "dairy free",
    "dairy-free",
    "nut free",
    "nut-free",
    "preservative free",
    "preservative-free",
    "caffeine free",
    "caffeine-free",
    "alcohol free",
    "alcohol-free",
    "sodium free",
    "sodium-free",
    "lactose free",
    "lactose-free",
    "additive free",
    "additive-free",
]


def _contains_false_positive_phrase(product_lower: str, keyword: str) -> bool:
    """
    Check if a keyword match is actually a false positive.

    Some keywords like "free" appear in product descriptions (e.g., "free range")
    that are not promotional.

    Args:
        product_lower: Lowercase product name
        keyword: The keyword that was matched

    Returns:
        True if this is a false positive (not a real promotion)
    """
    for phrase in FALSE_POSITIVE_PHRASES:
        if phrase in product_lower:
            # Check if the keyword is part of this false positive phrase
            if keyword in phrase:
                return True
    return False


def detect_promotion(
    product_name: str,
    source: Optional[str] = None,
    project_root: Optional[Path] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Detect if a product name indicates a promotional or bundle product.

    Args:
        product_name: The product name to analyze
        source: Source name (e.g., 'samoa_market') for source-specific keywords
        project_root: Project root path for loading config

    Returns:
        Tuple of (is_promotion, promotion_type) where:
        - is_promotion: True if promotion/bundle detected
        - promotion_type: Type of promotion detected or None
    """
    if not isinstance(product_name, str):
        return False, None

    product_lower = product_name.lower()

    # Get keywords from JSON config (global + source-specific)
    keywords = get_keywords_for_source(source, project_root)

    # Check for promotion keywords (with false positive filtering)
    for keyword in keywords:
        if keyword in product_lower:
            # Check if this is a false positive
            if not _contains_false_positive_phrase(product_lower, keyword):
                return True, f"keyword:{keyword}"

    # Check for promotion patterns
    for pattern in PROMOTION_PATTERNS_COMPILED:
        match = pattern.search(product_name)
        if match:
            return True, f"pattern:{match.group()}"

    # Check for additive patterns (bonus quantities)
    for pattern in ADDITIVE_PATTERNS:
        if re.search(pattern, product_name, re.IGNORECASE):
            return True, "additive_quantity"

    return False, None


def is_bundle_product(
    product_name: str,
    amount: Optional[str] = None,
    units: Optional[str] = None,
) -> bool:
    """
    Check if a product appears to be a bundle based on its name and quantities.

    Bundle indicators:
    - High unit counts with promotional keywords
    - Multiple different product types in name
    - Explicit bundle/combo keywords

    Args:
        product_name: The product name
        amount: The extracted amount (e.g., "100 g")
        units: The extracted units count (e.g., "24")

    Returns:
        True if product appears to be a bundle
    """
    if not isinstance(product_name, str):
        return False

    product_lower = product_name.lower()

    # Explicit bundle keywords
    bundle_keywords = [
        "bundle",
        "combo",
        "assorted",
        "assortment",
        "mixed",
        "variety",
        "selection",
        "hamper",
        "gift set",
        "gift pack",
    ]

    for keyword in bundle_keywords:
        if keyword in product_lower:
            return True

    # High unit count with promotional context
    if units:
        try:
            unit_count = int(float(units))
            # Very high counts (24+) with promotional keywords suggest bulk/bundle
            if unit_count >= 24:
                bulk_indicators = ["carton", "case", "bulk", "wholesale"]
                for indicator in bulk_indicators:
                    if indicator in product_lower:
                        return True
        except (ValueError, TypeError):
            pass

    # Multiple product indicators (e.g., "chips + dip", "burger & fries")
    multi_product_patterns = [
        r"\b\w+\s*[+&]\s*\w+\b",  # "X + Y" or "X & Y"
        r"\bwith\s+free\s+\w+\b",  # "with free X"
    ]

    for pattern in multi_product_patterns:
        if re.search(pattern, product_name, re.IGNORECASE):
            # Additional check: make sure it's not just a product description
            # like "salt & vinegar" (which is a flavor, not a bundle)
            if "combo" in product_lower or "bundle" in product_lower:
                return True

    return False


def get_promotion_confidence(product_name: str) -> float:
    """
    Get a confidence score for how likely a product is promotional.

    Higher scores indicate stronger promotion signals.

    Args:
        product_name: The product name to analyze

    Returns:
        Confidence score between 0.0 and 1.0
    """
    if not isinstance(product_name, str):
        return 0.0

    product_lower = product_name.lower()
    confidence = 0.0

    # Strong indicators (high confidence)
    strong_keywords = ["bundle", "combo", "buy", "get free", "promo"]
    for keyword in strong_keywords:
        if keyword in product_lower:
            confidence += 0.4

    # Medium indicators
    medium_keywords = ["bonus", "extra", "free", "deal", "special", "save"]
    for keyword in medium_keywords:
        if keyword in product_lower:
            confidence += 0.25

    # Weak indicators (context-dependent)
    weak_keywords = ["value", "pack", "family", "economy"]
    for keyword in weak_keywords:
        if keyword in product_lower:
            confidence += 0.1

    # Pattern matches
    for pattern in PROMOTION_PATTERNS_COMPILED:
        if pattern.search(product_name):
            confidence += 0.3

    # Cap at 1.0
    return min(confidence, 1.0)
