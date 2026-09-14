"""Prices FX: one tracked home for the rate cache, its provider, and its audit.

Layout:

* :mod:`prices.fx.paths`       cache location and the history floor
* :mod:`prices.fx.aliases`     scraped currency code -> ISO 4217
* :mod:`prices.fx.cache`       cache schema, atomic load/save, provenance
* :mod:`prices.fx.frankfurter` the provider client (api.frankfurter.dev **v2**)
* :mod:`prices.fx.pegs`        currencies derived from EUR, not fetched
* :mod:`prices.fx.attach`      offline attach of rates and USD prices
* :mod:`prices.fx.audit`       order-of-magnitude contamination detection
* :mod:`prices.fx.refresh`     the only module that touches the network

Build and render import from :mod:`prices.fx.attach` and never reach the
network; refreshing the cache is an explicit CLI step.
"""

from prices.fx.aliases import CURRENCY_TO_ISO, normalize_currency, normalize_currency_safe
from prices.fx.attach import attach_fx_and_usd, build_fx_table
from prices.fx.audit import find_contaminated_blocks, flag_rate_outliers, suspect_keys
from prices.fx.cache import FX_COLUMNS, coverage, load_cache, save_cache
from prices.fx.paths import FX_HISTORY_FLOOR, PRICES_FX_CACHE

__all__ = [
    "CURRENCY_TO_ISO",
    "FX_COLUMNS",
    "FX_HISTORY_FLOOR",
    "PRICES_FX_CACHE",
    "attach_fx_and_usd",
    "build_fx_table",
    "coverage",
    "find_contaminated_blocks",
    "flag_rate_outliers",
    "load_cache",
    "normalize_currency",
    "normalize_currency_safe",
    "save_cache",
    "suspect_keys",
]
