"""
Registry system for cleaning functions.

This module provides a decorator-based registry that allows cleaning functions
to be automatically registered and looked up by name.
"""

from typing import Callable, Optional

# Global registry for cleaning functions
_CLEANER_REGISTRY: dict[str, Callable] = {}


def register_cleaner(func: Callable) -> Callable:
    """
    Decorator to register a cleaning function.

    Args:
        func: The cleaning function to register

    Returns:
        The same function (unchanged)
    """
    _CLEANER_REGISTRY[func.__name__] = func
    return func


def get_cleaning_func(name: str) -> Optional[Callable]:
    """
    Get a registered cleaning function by name.

    Args:
        name: Name of the cleaning function

    Returns:
        Cleaning function or None if not found
    """
    return _CLEANER_REGISTRY.get(name)


def get_all_registered_functions() -> dict[str, Callable]:
    """
    Get all registered cleaning functions.

    Returns:
        Dictionary mapping function names to functions
    """
    return _CLEANER_REGISTRY.copy()
