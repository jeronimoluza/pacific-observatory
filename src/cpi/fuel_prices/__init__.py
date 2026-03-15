"""Pacific Observatory fuel prices module."""

from .fetchers import FETCHER_REGISTRY
from .loader import load_fuel_data, merge_new_rows
from .process import build_enriched_frame, frame_to_country_series
from .visualize import gen_fuel_html

__all__ = [
    "FETCHER_REGISTRY",
    "build_enriched_frame",
    "frame_to_country_series",
    "gen_fuel_html",
    "load_fuel_data",
    "merge_new_rows",
]
