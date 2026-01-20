"""
Confidence scoring for quantity extraction.

This module assigns a confidence score [0, 1] to each extraction based on
the quality and clarity of the extracted quantity information.

Scoring factors:
- Penalties: ranges, multiple candidates, additive patterns, default units
- Bonuses: single clear candidate, standard units, multiplicative structures
"""

from quantity_candidates import QuantityExtractionResult
from usability_classifier import UsabilityStatus, RESOLVED_STATUSES


# Penalty factors (subtracted from base score)
PENALTY_RANGE = 0.20  # Range pattern detected (e.g., "9-15kg")
PENALTY_MULTIPLE_CANDIDATES = 0.15  # Per additional candidate beyond first
PENALTY_ADDITIVE = 0.30  # Additive pattern detected (e.g., "+50g bonus")
PENALTY_DEFAULT_UNIT = 0.15  # Default unit "1" used
PENALTY_NON_STANDARD_UNIT = 0.10  # Unit not in standard conversion list
PENALTY_CONFLICTING = 0.35  # Conflicting quantities detected

# Bonus factors (added to base score)
BONUS_SINGLE_CANDIDATE = 0.10  # Single clear candidate found
BONUS_STANDARD_UNIT = 0.05  # Standard unit (kg, lt, mt) detected
BONUS_MULTIPLICATIVE = 0.05  # Clear multiplicative structure (e.g., "6 x 100g")
BONUS_RESOLVED = 0.10  # Product successfully resolved

# Base score for different statuses
BASE_SCORE_RESOLVED = 0.70  # Resolved products start higher
BASE_SCORE_UNRESOLVED = 0.30  # Unresolved products start lower


def calculate_confidence(
    extraction_result: QuantityExtractionResult,
    usability_status: UsabilityStatus,
) -> float:
    """
    Calculate a confidence score for the quantity extraction.

    The score represents how confident we are that the extracted quantity
    is correct and suitable for unit price calculation.

    Scoring logic:
    - Start with base score based on resolution status
    - Apply penalties for uncertainty factors
    - Apply bonuses for quality factors
    - Clamp result to [0, 1]

    Args:
        extraction_result: The quantity extraction result
        usability_status: The usability classification

    Returns:
        Confidence score between 0.0 and 1.0
    """
    # Determine base score
    if usability_status in RESOLVED_STATUSES:
        score = BASE_SCORE_RESOLVED
    else:
        score = BASE_SCORE_UNRESOLVED

    # Apply penalties
    score -= _calculate_penalties(extraction_result)

    # Apply bonuses
    score += _calculate_bonuses(extraction_result, usability_status)

    # Clamp to [0, 1]
    return max(0.0, min(1.0, score))


def _calculate_penalties(extraction_result: QuantityExtractionResult) -> float:
    """Calculate total penalty score."""
    penalty = 0.0

    # Range pattern penalty
    if extraction_result.has_range_pattern:
        penalty += PENALTY_RANGE

    # Multiple candidates penalty (beyond first)
    if extraction_result.n_candidates > 1:
        extra_candidates = extraction_result.n_candidates - 1
        penalty += PENALTY_MULTIPLE_CANDIDATES * extra_candidates

    # Additive pattern penalty
    if extraction_result.has_additive_pattern:
        penalty += PENALTY_ADDITIVE

    # Default unit penalty
    if extraction_result.raw_units == "1" and extraction_result.raw_amount is None:
        penalty += PENALTY_DEFAULT_UNIT

    # Conflicting quantities penalty
    if extraction_result.has_conflicting_quantities:
        penalty += PENALTY_CONFLICTING

    # Check for non-standard units
    if extraction_result.primary_candidate:
        unit = extraction_result.primary_candidate.unit.lower()
        # Non-standard units that might be ambiguous
        ambiguous_units = {"pc", "pcs", "pk", "ct"}
        if unit in ambiguous_units:
            penalty += PENALTY_NON_STANDARD_UNIT

    return penalty


def _calculate_bonuses(
    extraction_result: QuantityExtractionResult,
    usability_status: UsabilityStatus,
) -> float:
    """Calculate total bonus score."""
    bonus = 0.0

    # Single candidate bonus
    if extraction_result.n_candidates == 1:
        bonus += BONUS_SINGLE_CANDIDATE

    # Standard unit bonus
    primary = extraction_result.primary_candidate
    if primary and primary.unit.lower() in {
        "g",
        "gm",
        "kg",
        "ml",
        "mls",
        "l",
        "ltr",
        "ltrs",
        "litre",
        "m",
        "cm",
    }:
        bonus += BONUS_STANDARD_UNIT

    # Multiplicative structure bonus (indicates clear structure)
    if extraction_result.multiplicative:
        bonus += BONUS_MULTIPLICATIVE

    # Resolved status bonus
    if usability_status in RESOLVED_STATUSES:
        bonus += BONUS_RESOLVED

    return bonus


def get_confidence_tier(confidence: float) -> str:
    """
    Get a human-readable tier for a confidence score.

    Tiers:
    - high: >= 0.75
    - medium: >= 0.50
    - low: >= 0.25
    - very_low: < 0.25

    Args:
        confidence: Confidence score between 0 and 1

    Returns:
        Tier string
    """
    if confidence >= 0.75:
        return "high"
    elif confidence >= 0.50:
        return "medium"
    elif confidence >= 0.25:
        return "low"
    else:
        return "very_low"


def explain_confidence(
    extraction_result: QuantityExtractionResult,
    usability_status: UsabilityStatus,
    confidence: float,
) -> str:
    """
    Generate a human-readable explanation of the confidence score.

    Args:
        extraction_result: The quantity extraction result
        usability_status: The usability classification
        confidence: The calculated confidence score

    Returns:
        Explanation string
    """
    factors = []

    # Status factor
    if usability_status in RESOLVED_STATUSES:
        factors.append(f"+base:resolved({BASE_SCORE_RESOLVED})")
    else:
        factors.append(f"+base:unresolved({BASE_SCORE_UNRESOLVED})")

    # Penalties
    if extraction_result.has_range_pattern:
        factors.append(f"-range({PENALTY_RANGE})")

    if extraction_result.n_candidates > 1:
        extra = extraction_result.n_candidates - 1
        factors.append(f"-multiple_candidates({PENALTY_MULTIPLE_CANDIDATES}*{extra})")

    if extraction_result.has_additive_pattern:
        factors.append(f"-additive({PENALTY_ADDITIVE})")

    if extraction_result.raw_units == "1" and extraction_result.raw_amount is None:
        factors.append(f"-default_unit({PENALTY_DEFAULT_UNIT})")

    if extraction_result.has_conflicting_quantities:
        factors.append(f"-conflicting({PENALTY_CONFLICTING})")

    # Bonuses
    if extraction_result.n_candidates == 1:
        factors.append(f"+single_candidate({BONUS_SINGLE_CANDIDATE})")

    primary = extraction_result.primary_candidate
    if primary and primary.unit.lower() in {
        "g",
        "gm",
        "kg",
        "ml",
        "mls",
        "l",
        "ltr",
        "ltrs",
        "litre",
        "m",
        "cm",
    }:
        factors.append(f"+standard_unit({BONUS_STANDARD_UNIT})")

    if extraction_result.multiplicative:
        factors.append(f"+multiplicative({BONUS_MULTIPLICATIVE})")

    if usability_status in RESOLVED_STATUSES:
        factors.append(f"+resolved({BONUS_RESOLVED})")

    factors.append(f"=>{confidence:.2f}")

    return " ".join(factors)
