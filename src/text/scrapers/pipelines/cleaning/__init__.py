"""
Data cleaning functions for scraped content.

This package contains cleaning functions organized by country/newspaper
that can be referenced in newspaper configuration files to normalize extracted data.

The package uses a registry system to auto-register cleaning functions, allowing
dynamic lookup by name.
"""

import inspect
import logging
from typing import Any, Optional

# Import registry functions first
from .registry import get_cleaning_func, register_cleaner, get_all_registered_functions

# Import all country/region modules to trigger registration
# These imports populate the registry with all cleaning functions

logger = logging.getLogger(__name__)

# Export public API
__all__ = [
    "get_cleaning_func",
    "register_cleaner",
    "apply_cleaning",
    # Re-export commonly used functions for backwards compatibility
    "handle_mixed_dates",
    "clean_html_text",
    "normalize_tags",
    "clean_url",
    "clean_title",
    "normalize_date",
    "handle_unix_timestamp_ms",
    "handle_unix_timestamp_ms_or_iso",
    "join_body_list",
    "clean_wp_html_body",
    "clean_frontier_myanmar_body",
    # Country-specific cleaners
    "clean_kosmo_body",
    "clean_the_independent_body",
    "clean_laotian_times_body",
    "clean_ann_body",
    "clean_philstar_body",
    "clean_inquirer_body",
    "clean_nz_herald_body",
    "clean_island_times_body",
    "clean_jakarta_post_body",
    "clean_antara_body",
    "clean_sibc_date",
    "clean_sibc_body",
    "clean_solomon_star_date",
    "clean_solomon_star_content",
    "clean_solomon_star_tags",
    "clean_solomon_times_date",
    "clean_solomon_times_content",
    "clean_solomon_times_tags",
    "clean_matangi_url",
    "filter_abc_au_articles",
    # Ukraine cleaners
    "clean_ukrainska_pravda_date",
    "clean_ukrainska_pravda_eng_date",
    "clean_spaced_html",
    # Legacy compatibility
    "CLEANING_FUNCTIONS",
]


def apply_cleaning(
    data: Any,
    cleaning_config: dict,
    base_url: Optional[str] = None,
    page_url: Optional[str] = None,
    **kwargs,
) -> Any:
    """
    Apply cleaning functions to data based on configuration.

    Args:
        data: Data dictionary to clean
        cleaning_config: Dictionary mapping field names to cleaning function names
        base_url: Base URL for URL cleaning
        page_url: Page URL for context-aware cleaning (e.g., date extraction from URLs)
        **kwargs: Additional context for cleaning functions

    Returns:
        Cleaned data dictionary
    """
    if not cleaning_config or not isinstance(data, dict):
        return data

    cleaned_data = data.copy()

    for field_name, function_name in cleaning_config.items():
        if field_name in cleaned_data:
            cleaning_func = get_cleaning_func(function_name)
            if cleaning_func:
                try:
                    # Build context kwargs based on what the function accepts
                    sig = inspect.signature(cleaning_func)
                    params = sig.parameters
                    extra = {}
                    if "page_url" in params and page_url is not None:
                        extra["page_url"] = page_url
                    if "base_url" in params and base_url is not None:
                        extra["base_url"] = base_url
                    if any(
                        p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
                    ):
                        extra.update(kwargs)
                    cleaned_data[field_name] = cleaning_func(
                        cleaned_data[field_name], **extra
                    )
                except Exception as e:
                    logger.error(
                        f"Error applying cleaning function '{function_name}' to field '{field_name}': {e}"
                    )
            else:
                logger.warning(f"Cleaning function '{function_name}' not found")

    return cleaned_data


# Import and re-export all cleaning functions for backwards compatibility
# This allows: from text.scrapers.pipelines.cleaning import clean_kosmo_body
from .common import (  # noqa: E402
    handle_mixed_dates,
    clean_html_text,
    normalize_tags,
    clean_url,
    clean_title,
    normalize_date,
    handle_unix_timestamp_ms,
    handle_unix_timestamp_ms_or_iso,
    join_body_list,
    clean_wp_html_body,
)

from .malaysia import clean_kosmo_body  # noqa: E402
from .singapore import clean_the_independent_body  # noqa: E402
from .laos import clean_laotian_times_body  # noqa: E402
from .philippines import clean_ann_body, clean_philstar_body, clean_inquirer_body  # noqa: E402
from .new_zealand import clean_nz_herald_body  # noqa: E402
from .palau import clean_island_times_body  # noqa: E402
from .indonesia import clean_jakarta_post_body, clean_antara_body  # noqa: E402
from .solomon_islands import (  # noqa: E402
    clean_sibc_date,
    clean_sibc_body,
    clean_solomon_star_date,
    clean_solomon_star_content,
    clean_solomon_star_tags,
    clean_solomon_times_date,
    clean_solomon_times_content,
    clean_solomon_times_tags,
)
from .tonga import clean_matangi_url  # noqa: E402
from .australia import filter_abc_au_articles  # noqa: E402
from .myanmar import clean_frontier_myanmar_body  # noqa: E402
from .ukraine import (  # noqa: E402
    clean_ukrainska_pravda_date,
    clean_ukrainska_pravda_eng_date,
    clean_spaced_html,
)

# Legacy compatibility: Provide CLEANING_FUNCTIONS dict
CLEANING_FUNCTIONS = get_all_registered_functions()
