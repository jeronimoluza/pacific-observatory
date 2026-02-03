"""Tests for cleaning package split."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def test_registry_works():
    """Test that registry auto-registers cleaners."""
    from text.scrapers.pipelines.cleaning import get_cleaning_func

    # Test that common cleaning functions are registered
    assert get_cleaning_func("clean_url") is not None
    assert get_cleaning_func("handle_mixed_dates") is not None
    assert get_cleaning_func("clean_html_text") is not None


def test_all_functions_registered():
    """Test that all cleaning functions from original module are registered."""
    from text.scrapers.pipelines.cleaning import get_cleaning_func

    # Test country-specific cleaners
    expected_functions = [
        # Malaysia
        "clean_kosmo_body",
        # Singapore
        "clean_the_independent_body",
        # Laos
        "clean_laotian_times_body",
        # Philippines
        "clean_ann_body",
        "clean_philstar_body",
        "clean_inquirer_body",
        # New Zealand
        "clean_nz_herald_body",
        # Palau
        "clean_island_times_body",
        # Indonesia
        "clean_jakarta_post_body",
        "clean_antara_body",
        # Solomon Islands
        "clean_sibc_date",
        "clean_sibc_body",
        "clean_solomon_star_date",
        "clean_solomon_star_content",
        "clean_solomon_star_tags",
        "clean_solomon_times_date",
        "clean_solomon_times_content",
        "clean_solomon_times_tags",
        # Tonga
        "clean_matangi_url",
        # Australia
        "filter_abc_au_articles",
        # Common utilities
        "handle_mixed_dates",
        "clean_html_text",
        "normalize_tags",
        "clean_url",
        "clean_title",
        "normalize_date",
        "handle_unix_timestamp_ms",
        "join_body_list",
    ]

    for func_name in expected_functions:
        func = get_cleaning_func(func_name)
        assert func is not None, f"Function {func_name} not found in registry"
        assert callable(func), f"Function {func_name} is not callable"


def test_country_modules_exist():
    """Test that country modules are imported."""
    from text.scrapers.pipelines import cleaning

    # Check that sub-modules exist as attributes
    assert hasattr(cleaning, "common")
    assert hasattr(cleaning, "solomon_islands")
    assert hasattr(cleaning, "indonesia")
    assert hasattr(cleaning, "philippines")


def test_backwards_compatibility():
    """Test that existing imports still work."""
    from text.scrapers.pipelines.cleaning import (
        handle_mixed_dates,
        clean_html_text,
        normalize_tags,
        clean_url,
        clean_title,
        clean_kosmo_body,
        clean_the_independent_body,
        clean_philstar_body,
        clean_inquirer_body,
        get_cleaning_func,
        apply_cleaning,
    )

    # All imports should succeed
    assert handle_mixed_dates is not None
    assert clean_html_text is not None
    assert normalize_tags is not None
    assert clean_url is not None
    assert clean_title is not None
    assert clean_kosmo_body is not None
    assert clean_the_independent_body is not None
    assert clean_philstar_body is not None
    assert clean_inquirer_body is not None
    assert get_cleaning_func is not None
    assert apply_cleaning is not None
