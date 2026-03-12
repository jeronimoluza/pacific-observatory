"""Pacific Observatory fuel prices module."""

from .loader import load_fuel_data, merge_new_rows
from .visualize import gen_fuel_html
from .fetchers import FETCHER_REGISTRY

__all__ = ["load_fuel_data", "merge_new_rows", "gen_fuel_html", "FETCHER_REGISTRY"]
