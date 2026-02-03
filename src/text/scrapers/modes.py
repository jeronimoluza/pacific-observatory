"""
Scrape mode definitions and utilities.

This module defines the different scraping modes available in the system
and provides utilities for working with them.
"""

from enum import Enum


class ScrapeMode(Enum):
    """
    Scraping modes for newspaper scraper.

    Modes:
    - UPDATE: Incremental update mode (discover + scrape new articles)
    - RESUME: Resume scraping articles from existing URLs
    - FULL_DISCOVERY: Full discovery of all URLs (overwrites urls.csv)
    - FULL_FROM_SCRATCH: Full scrape from scratch (legacy mode)
    """

    UPDATE = "update"  # Default smart update mode
    RESUME = "resume"  # Resume scraping from urls.csv
    FULL_DISCOVERY = "full_discovery"  # Full URL discovery
    FULL_FROM_SCRATCH = "full_from_scratch"  # Legacy full scrape


def mode_from_string(mode_str: str) -> ScrapeMode:
    """
    Convert CLI string to ScrapeMode enum.

    Args:
        mode_str: Mode string from CLI (e.g., "update", "resume", "discover-full")

    Returns:
        ScrapeMode enum value

    Raises:
        ValueError: If mode string is not recognized
    """
    # Normalize the mode string
    mode_str = mode_str.lower().strip()

    # Map CLI strings to enum values
    mode_map = {
        "update": ScrapeMode.UPDATE,
        "default": ScrapeMode.UPDATE,
        "resume": ScrapeMode.RESUME,
        "full-discovery": ScrapeMode.FULL_DISCOVERY,
        "full_discovery": ScrapeMode.FULL_DISCOVERY,  # underscore variant
        "full": ScrapeMode.FULL_FROM_SCRATCH,
        "full-scrape": ScrapeMode.FULL_FROM_SCRATCH,
        "full_from_scratch": ScrapeMode.FULL_FROM_SCRATCH,  # underscore variant
    }

    if mode_str not in mode_map:
        valid_modes = ", ".join(sorted(mode_map.keys()))
        raise ValueError(f"Unknown mode '{mode_str}'. Valid modes: {valid_modes}")

    return mode_map[mode_str]
