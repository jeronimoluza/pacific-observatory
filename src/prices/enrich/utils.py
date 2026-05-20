"""
Shared utility functions for the coicopping module.

This module provides common utilities used across multiple files in the
COICOP classification pipeline.
"""

from pathlib import Path


def get_project_root(current_file: Path = None) -> Path:
    """
    Get the project root directory.

    Infers the project root from this file's location:
    src/prices/enrich/utils.py -> project_root

    Args:
        current_file: Optional path to a file to use as reference.
                     If None, uses this file's location.

    Returns:
        Path to the project root directory.
    """
    if current_file is None:
        current_file = Path(__file__)
    return current_file.parent.parent.parent.parent
