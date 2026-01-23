"""
DEPRECATED: Migrated to cleaning/ package.

This module is maintained for backwards compatibility only.
Import from text.scrapers.pipelines.cleaning (package) instead.

All functionality has been moved to the cleaning package, organized by country/newspaper.
"""

import warnings

warnings.warn(
    "cleaning.py is deprecated. Import from text.scrapers.pipelines.cleaning package instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the new package for backwards compatibility
from .cleaning import *  # noqa: F401, F403, E402
