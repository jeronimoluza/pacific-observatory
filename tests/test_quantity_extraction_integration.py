"""Integration tests for quantity extraction pipeline."""

import pandas as pd


class TestQuantityExtractionPipeline:
    """Test the full extraction pipeline."""

    def test_tier_1_weight_extraction(self):
        """Test Tier 1 weight/volume extraction."""
        from src.cpi.coicopping.extract_quantities import extract_quantities

        # Create test DataFrame
        df = pd.DataFrame(
            {
                "product_name": ["Tuna Chunks 2x185g"],
                "price": [5.99],
                "currency": ["USD"],
                "source": ["test"],
                "country": ["test"],
                "product_url": ["http://test.com"],
                "url_hash": ["abc123"],
                "date": ["2026-01-21"],
                "scraped_at": ["2026-01-21"],
                "wayback": [False],
                "product_w_cat": ["Tuna Chunks 2x185g"],
            }
        )

        result = extract_quantities(df)

        assert result["usability_status"].iloc[0] == "resolved_weight_volume"
        assert result["extraction_tier"].iloc[0] == 1
        assert result["unit_value"].iloc[0] is not None

    def test_tier_2_count_extraction(self):
        """Test Tier 2 count extraction."""
        from src.cpi.coicopping.extract_quantities import extract_quantities

        df = pd.DataFrame(
            {
                "product_name": ["Eggs 12 pack"],
                "price": [4.99],
                "currency": ["USD"],
                "source": ["test"],
                "country": ["test"],
                "product_url": ["http://test.com"],
                "url_hash": ["def456"],
                "date": ["2026-01-21"],
                "scraped_at": ["2026-01-21"],
                "wayback": [False],
                "product_w_cat": ["Eggs 12 pack"],
            }
        )

        result = extract_quantities(df)

        assert result["usability_status"].iloc[0] == "resolved_count"
        assert result["extraction_tier"].iloc[0] == 2

    def test_tier_3_per_item_fallback(self):
        """Test Tier 3 per-item fallback."""
        from src.cpi.coicopping.extract_quantities import extract_quantities

        df = pd.DataFrame(
            {
                "product_name": ["Fresh Mango"],
                "price": [2.50],
                "currency": ["USD"],
                "source": ["test"],
                "country": ["test"],
                "product_url": ["http://test.com"],
                "url_hash": ["ghi789"],
                "date": ["2026-01-21"],
                "scraped_at": ["2026-01-21"],
                "wayback": [False],
                "product_w_cat": ["Fresh Mango"],
            }
        )

        result = extract_quantities(df)

        assert result["usability_status"].iloc[0] == "resolved_per_item"
        assert result["extraction_tier"].iloc[0] == 3
        assert result["unit_value"].iloc[0] == 2.50

    def test_promotion_exclusion(self):
        """Test promotion products are excluded."""
        from src.cpi.coicopping.extract_quantities import extract_quantities

        df = pd.DataFrame(
            {
                "product_name": ["Buy 1 Get 1 Free Chips 200g"],
                "price": [3.99],
                "currency": ["USD"],
                "source": ["test"],
                "country": ["test"],
                "product_url": ["http://test.com"],
                "url_hash": ["jkl012"],
                "date": ["2026-01-21"],
                "scraped_at": ["2026-01-21"],
                "wayback": [False],
                "product_w_cat": ["Buy 1 Get 1 Free Chips 200g"],
            }
        )

        result = extract_quantities(df)

        assert result["usability_status"].iloc[0] == "promotion_or_bundle"
        assert pd.isna(
            result["unit_value"].iloc[0]
        )  # Excluded products have no unit_value

    def test_contradictory_exclusion(self):
        """Test contradictory quantities are excluded."""
        from src.cpi.coicopping.extract_quantities import extract_quantities

        df = pd.DataFrame(
            {
                "product_name": ["Product 500g / 1kg conflicting"],
                "price": [9.99],
                "currency": ["USD"],
                "source": ["test"],
                "country": ["test"],
                "product_url": ["http://test.com"],
                "url_hash": ["mno345"],
                "date": ["2026-01-21"],
                "scraped_at": ["2026-01-21"],
                "wayback": [False],
                "product_w_cat": ["Product 500g / 1kg conflicting"],
            }
        )

        result = extract_quantities(df)

        assert result["usability_status"].iloc[0] == "contradictory"
        assert pd.isna(result["unit_value"].iloc[0])
