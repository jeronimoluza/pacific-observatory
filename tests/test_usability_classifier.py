"""Tests for usability classification with new status model."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class MockQuantityCandidate:
    """Mock for QuantityCandidate."""

    value: float
    unit: str
    candidate_type: str
    is_range: bool = False


@dataclass
class MockExtractionResult:
    """Mock for QuantityExtractionResult."""

    product_name: str
    candidates: List[MockQuantityCandidate]
    raw_amount: Optional[str] = None
    raw_units: Optional[str] = None
    has_additive_pattern: bool = False

    @property
    def n_candidates(self) -> int:
        return len(self.candidates)

    @property
    def has_conflicting_quantities(self) -> bool:
        types = set(c.candidate_type for c in self.candidates)
        return len(types) > 1 and len(self.candidates) > 1

    @property
    def primary_candidate(self):
        if self.candidates:
            return self.candidates[0]
        return None


class TestNewStatusModel:
    """Test the new 6-status model from design document."""

    def test_resolved_weight_volume_mass(self):
        """Mass products should get resolved_weight_volume status."""
        # Import here to test actual module
        from src.cpi.coicopping.usability_classifier import (
            classify_usability,
            UsabilityStatus,
        )
        from src.cpi.coicopping.quantity_candidates import extract_all_candidates

        result = extract_all_candidates("Tuna Chunks 500g")
        status, reason = classify_usability(result, "Tuna Chunks 500g")
        assert status == UsabilityStatus.RESOLVED_WEIGHT_VOLUME
        assert reason is None

    def test_resolved_weight_volume_volume(self):
        """Volume products should get resolved_weight_volume status."""
        from src.cpi.coicopping.usability_classifier import (
            classify_usability,
            UsabilityStatus,
        )
        from src.cpi.coicopping.quantity_candidates import extract_all_candidates

        result = extract_all_candidates("Orange Juice 1L")
        status, reason = classify_usability(result, "Orange Juice 1L")
        assert status == UsabilityStatus.RESOLVED_WEIGHT_VOLUME
        assert reason is None

    def test_resolved_count(self):
        """Count-based products should get resolved_count status."""
        from src.cpi.coicopping.usability_classifier import (
            classify_usability,
            UsabilityStatus,
        )
        from src.cpi.coicopping.quantity_candidates import extract_all_candidates

        result = extract_all_candidates("Eggs 12 pack")
        status, reason = classify_usability(
            result, "Eggs 12 pack", coicop_code="01.1.4"
        )
        assert status == UsabilityStatus.RESOLVED_COUNT
        assert reason is None

    def test_resolved_per_item_fallback(self):
        """Products with no quantity should get resolved_per_item status."""
        from src.cpi.coicopping.usability_classifier import (
            classify_usability,
            UsabilityStatus,
        )
        from src.cpi.coicopping.quantity_candidates import extract_all_candidates

        result = extract_all_candidates("Fresh Mango")
        status, reason = classify_usability(result, "Fresh Mango")
        assert status == UsabilityStatus.RESOLVED_PER_ITEM
        assert reason is None

    def test_contradictory_signals(self):
        """Conflicting quantities should get contradictory status."""
        from src.cpi.coicopping.usability_classifier import (
            classify_usability,
            UsabilityStatus,
        )
        from src.cpi.coicopping.quantity_candidates import extract_all_candidates

        result = extract_all_candidates("Product 500g / 1kg")
        status, reason = classify_usability(result, "Product 500g / 1kg")
        assert status == UsabilityStatus.CONTRADICTORY
        assert reason is not None

    def test_promotion_detection(self):
        """Promotional products should get promotion_or_bundle status."""
        from src.cpi.coicopping.usability_classifier import (
            classify_usability,
            UsabilityStatus,
        )
        from src.cpi.coicopping.quantity_candidates import extract_all_candidates

        result = extract_all_candidates("Buy 1 Get 1 Free Chips")
        status, reason = classify_usability(result, "Buy 1 Get 1 Free Chips")
        assert status == UsabilityStatus.PROMOTION_OR_BUNDLE
        assert "promotion" in reason.lower()


class TestExtractionTier:
    """Test extraction tier assignment."""

    def test_tier_1_weight(self):
        """Weight patterns should be Tier 1."""
        from src.cpi.coicopping.usability_classifier import get_extraction_tier

        assert get_extraction_tier("resolved_weight_volume") == 1

    def test_tier_2_count(self):
        """Count patterns should be Tier 2."""
        from src.cpi.coicopping.usability_classifier import get_extraction_tier

        assert get_extraction_tier("resolved_count") == 2

    def test_tier_3_per_item(self):
        """Per-item fallback should be Tier 3."""
        from src.cpi.coicopping.usability_classifier import get_extraction_tier

        assert get_extraction_tier("resolved_per_item") == 3
