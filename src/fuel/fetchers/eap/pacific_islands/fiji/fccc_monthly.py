"""Fiji FCCC monthly price list, 2025-01-01 to 2025-10-31: data without a fetcher.

Legacy pacific-observatory kept ``fiji/fiji_fccc_monthly_prices/observations.csv``
but had no fetcher or FETCHER_REGISTRY entry for it. The rows are moved as-is and
this stub keeps the source loadable; it never returns new rows.
"""

from datetime import date

import pandas as pd


def fetch_fj_fccc_monthly(cutoff: date) -> pd.DataFrame | None:
    print("  [fj_fccc_monthly] No fetcher: legacy data only")
    return None
