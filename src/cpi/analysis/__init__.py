"""
CPI Analysis Module.

Constructs consumer price indices using COICOP-classified price data
and HIES expenditure weights.

Main entry point:
    from src.cpi.analysis.pipeline import construct_cpi

    results = construct_cpi(
        price_data_path="data/cpi/analysis/all_countries_supermarket_prices.csv",
        country="fiji",
        reference_month="2025-11",
    )

CLI usage:
    python -m src.cpi.analysis.pipeline --country fiji --reference-month 2025-11
"""

from .pipeline import construct_cpi
from .data_loader import load_and_prepare, load_price_data
from .elementary_aggregates import compute_elementary_aggregates
from .higher_aggregation import compute_higher_aggregation, load_weights
from .output import export_all
from .redistribute_weights import redistribute_weights, validate_weights

__all__ = [
    "construct_cpi",
    "load_and_prepare",
    "load_price_data",
    "compute_elementary_aggregates",
    "compute_higher_aggregation",
    "load_weights",
    "export_all",
    "redistribute_weights",
    "validate_weights",
]
