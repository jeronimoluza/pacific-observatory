"""
Multi-candidate quantity extraction from product names.

This module extracts ALL quantity expressions from product names with metadata,
enabling better classification and confidence scoring. Unlike the original
first-match approach, this captures all candidates for downstream analysis.

Key features:
- Extracts all quantity candidates (mass, volume, length, count)
- Detects multiplicative structures (e.g., "6 x 100g")
- Detects additive patterns (e.g., "+50g bonus")
- Detects range patterns (e.g., "9-15kg")
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .regex import (
    AMOUNT_UNITS,
    COUNT_UNITS,
    AMOUNT_REGEX,
    UNITS_REGEX,
    X_SEPARATOR_REGEX,
    ADDITIVE_PATTERNS,
    RANGE_PATTERN,
)
from .conversions import UNIT_CONVERSIONS


@dataclass
class QuantityCandidate:
    """Represents a single quantity expression found in a product name."""

    value: float
    unit: str
    raw_string: str
    start_pos: int
    end_pos: int
    candidate_type: str  # 'mass', 'volume', 'length', 'count'
    is_range: bool = False
    range_values: Optional[Tuple[float, float]] = None
    is_additive: bool = False


@dataclass
class MultiplicativeStructure:
    """Represents a multiplicative structure like '6 x 100g'."""

    multiplier: float
    quantity: QuantityCandidate
    raw_string: str
    start_pos: int
    end_pos: int


@dataclass
class QuantityExtractionResult:
    """Complete result of quantity extraction from a product name."""

    product_name: str
    candidates: List[QuantityCandidate] = field(default_factory=list)
    multiplicative: Optional[MultiplicativeStructure] = None
    has_additive_pattern: bool = False
    has_range_pattern: bool = False
    raw_amount: Optional[str] = None  # For backward compatibility
    raw_units: Optional[str] = None  # For backward compatibility

    @property
    def n_candidates(self) -> int:
        """Number of quantity candidates found."""
        return len(self.candidates)

    @property
    def has_conflicting_quantities(self) -> bool:
        """Check if there are multiple candidates of the same type that conflict."""
        if len(self.candidates) <= 1:
            return False

        # Group by type
        types_seen = {}
        for c in self.candidates:
            if c.candidate_type in types_seen:
                # Check if values are different (conflicting)
                if c.value != types_seen[c.candidate_type]:
                    return True
            else:
                types_seen[c.candidate_type] = c.value
        return False

    @property
    def primary_candidate(self) -> Optional[QuantityCandidate]:
        """Get the primary (most likely correct) candidate."""
        if not self.candidates:
            return None
        # Prefer mass/volume over count, and earlier positions
        mass_volume = [
            c for c in self.candidates if c.candidate_type in ("mass", "volume")
        ]
        if mass_volume:
            return mass_volume[0]
        return self.candidates[0]


def classify_unit_type(unit: str) -> str:
    """
    Classify a unit into its type category.

    Args:
        unit: The unit string (e.g., 'g', 'ml', 'pack')

    Returns:
        One of: 'mass', 'volume', 'length', 'count'
    """
    unit_lower = unit.lower()

    if unit_lower in UNIT_CONVERSIONS:
        _, standard_unit = UNIT_CONVERSIONS[unit_lower]
        if standard_unit == "kg":
            return "mass"
        elif standard_unit == "lt":
            return "volume"
        elif standard_unit == "mt":
            return "length"

    if unit_lower in [u.lower() for u in COUNT_UNITS]:
        return "count"

    # Unknown unit, default to count
    return "count"


def extract_all_candidates(product_name: str) -> QuantityExtractionResult:
    """
    Extract ALL quantity expressions from a product name with metadata.

    This is the main entry point for multi-candidate extraction.

    Args:
        product_name: The product name to analyze

    Returns:
        QuantityExtractionResult with all candidates and metadata
    """
    if not isinstance(product_name, str):
        return QuantityExtractionResult(
            product_name=str(product_name) if product_name else ""
        )

    result = QuantityExtractionResult(product_name=product_name)
    candidates: List[QuantityCandidate] = []

    # Check for additive patterns
    result.has_additive_pattern = detect_additive_patterns(product_name)

    # Check for range patterns
    result.has_range_pattern = detect_range_patterns(product_name)

    # Check for multiplicative structure
    mult_result = detect_multiplicative_structure(product_name)
    if mult_result:
        result.multiplicative = mult_result

    # Extract amount candidates (mass/volume/length)
    amount_candidates = _extract_amount_candidates(product_name)
    candidates.extend(amount_candidates)

    # Extract count candidates
    count_candidates = _extract_count_candidates(product_name)
    candidates.extend(count_candidates)

    # Sort by position
    candidates.sort(key=lambda c: c.start_pos)
    result.candidates = candidates

    # Set backward-compatible raw_amount and raw_units
    _set_backward_compatible_values(result)

    return result


def _extract_amount_candidates(product_name: str) -> List[QuantityCandidate]:
    """Extract all mass/volume/length candidates from product name."""
    candidates = []

    # Use AMOUNT_REGEX to find all matches
    for match in AMOUNT_REGEX.finditer(product_name):
        (range_val1, range_val2, range_unit, single_val, single_unit) = match.groups()

        if range_val1 and range_val2:
            # Range pattern (e.g., "9-15kg")
            val1 = float(range_val1)
            val2 = float(range_val2)
            avg_value = (val1 + val2) / 2
            unit = range_unit
            candidate = QuantityCandidate(
                value=avg_value,
                unit=unit,
                raw_string=match.group(),
                start_pos=match.start(),
                end_pos=match.end(),
                candidate_type=classify_unit_type(unit),
                is_range=True,
                range_values=(val1, val2),
            )
            candidates.append(candidate)
        elif single_val:
            # Single value (e.g., "100g")
            value = float(single_val)
            unit = single_unit
            candidate = QuantityCandidate(
                value=value,
                unit=unit,
                raw_string=match.group(),
                start_pos=match.start(),
                end_pos=match.end(),
                candidate_type=classify_unit_type(unit),
            )
            candidates.append(candidate)

    # Check for additive patterns and mark candidates
    for pattern in ADDITIVE_PATTERNS:
        for match in re.finditer(pattern, product_name, re.IGNORECASE):
            # Mark any overlapping candidates as additive
            for c in candidates:
                if (c.start_pos >= match.start() and c.start_pos < match.end()) or (
                    c.end_pos > match.start() and c.end_pos <= match.end()
                ):
                    c.is_additive = True

    return candidates


def _extract_count_candidates(product_name: str) -> List[QuantityCandidate]:
    """Extract all count-based candidates from product name."""
    candidates = []

    # Use UNITS_REGEX to find all matches
    for match in UNITS_REGEX.finditer(product_name):
        (range_val1, range_val2, range_unit, single_val, single_unit) = match.groups()

        if range_val1 and range_val2:
            # Range pattern (e.g., "6-10 pack")
            val1 = float(range_val1)
            val2 = float(range_val2)
            avg_value = int((val1 + val2) / 2)
            unit = range_unit
            candidate = QuantityCandidate(
                value=float(avg_value),
                unit=unit,
                raw_string=match.group(),
                start_pos=match.start(),
                end_pos=match.end(),
                candidate_type="count",
                is_range=True,
                range_values=(val1, val2),
            )
            candidates.append(candidate)
        elif single_val:
            # Single value (e.g., "6 pack")
            value = float(single_val)
            unit = single_unit
            candidate = QuantityCandidate(
                value=value,
                unit=unit,
                raw_string=match.group(),
                start_pos=match.start(),
                end_pos=match.end(),
                candidate_type="count",
            )
            candidates.append(candidate)

    return candidates


def detect_multiplicative_structure(text: str) -> Optional[MultiplicativeStructure]:
    """
    Detect multiplicative patterns like '6 x 100g' or '250ml x 24'.

    Args:
        text: Product name to analyze

    Returns:
        MultiplicativeStructure if found, None otherwise
    """
    for match in X_SEPARATOR_REGEX.finditer(text):
        first_num, first_unit, second_num, second_unit = match.groups()

        if first_unit and first_unit.lower() in [u.lower() for u in AMOUNT_UNITS]:
            # Pattern: "250ml x 24" - amount first, multiplier second
            if second_num:
                quantity = QuantityCandidate(
                    value=float(first_num),
                    unit=first_unit,
                    raw_string=f"{first_num}{first_unit}",
                    start_pos=match.start(),
                    end_pos=match.end(),
                    candidate_type=classify_unit_type(first_unit),
                )
                return MultiplicativeStructure(
                    multiplier=float(second_num),
                    quantity=quantity,
                    raw_string=match.group(),
                    start_pos=match.start(),
                    end_pos=match.end(),
                )
        elif second_unit and second_unit.lower() in [u.lower() for u in AMOUNT_UNITS]:
            # Pattern: "6 x 100g" - multiplier first, amount second
            if first_num:
                quantity = QuantityCandidate(
                    value=float(second_num),
                    unit=second_unit,
                    raw_string=f"{second_num}{second_unit}",
                    start_pos=match.start(),
                    end_pos=match.end(),
                    candidate_type=classify_unit_type(second_unit),
                )
                return MultiplicativeStructure(
                    multiplier=float(first_num),
                    quantity=quantity,
                    raw_string=match.group(),
                    start_pos=match.start(),
                    end_pos=match.end(),
                )

    return None


def detect_additive_patterns(text: str) -> bool:
    """
    Detect additive patterns like '+50g', 'bonus', 'extra', 'free'.

    Args:
        text: Product name to analyze

    Returns:
        True if additive pattern detected
    """
    for pattern in ADDITIVE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def detect_range_patterns(text: str) -> bool:
    """
    Detect range patterns like '9-15kg' or '6-10 pack'.

    Args:
        text: Product name to analyze

    Returns:
        True if range pattern detected
    """
    if re.search(RANGE_PATTERN, text, re.IGNORECASE):
        return True
    return False


def _set_backward_compatible_values(result: QuantityExtractionResult) -> None:
    """
    Set raw_amount and raw_units for backward compatibility.

    This mimics the original extract_amount_and_units() behavior for the
    primary candidate.
    """
    if result.multiplicative:
        # Use multiplicative structure
        mult = result.multiplicative
        result.raw_amount = f"{mult.quantity.value} {mult.quantity.unit}"
        result.raw_units = str(int(mult.multiplier))
        return

    # Find primary amount candidate (mass/volume/length)
    amount_candidates = [
        c for c in result.candidates if c.candidate_type in ("mass", "volume", "length")
    ]
    count_candidates = [c for c in result.candidates if c.candidate_type == "count"]

    if amount_candidates:
        primary = amount_candidates[0]
        if primary.is_range and primary.range_values:
            avg = int((primary.range_values[0] + primary.range_values[1]) / 2)
            result.raw_amount = f"{avg} {primary.unit}"
        else:
            result.raw_amount = f"{int(primary.value) if primary.value == int(primary.value) else primary.value} {primary.unit}"

    if count_candidates:
        primary = count_candidates[0]
        if primary.is_range and primary.range_values:
            avg = int((primary.range_values[0] + primary.range_values[1]) / 2)
            result.raw_units = str(avg)
        else:
            result.raw_units = str(int(primary.value))
    else:
        # Default to "1" if no count found
        result.raw_units = "1"
