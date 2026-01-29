"""Inflation indicators and metrics."""

from .inflation import aggregate_inflation, compute_price_levels
from .diffusion import compute_diffusion

__all__ = [
    "aggregate_inflation",
    "compute_price_levels",
    "compute_diffusion",
]
