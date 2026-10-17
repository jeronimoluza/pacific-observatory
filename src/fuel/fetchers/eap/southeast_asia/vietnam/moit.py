"""Vietnam MOIT fuel prices: 2025 archive migrated from legacy, no fetcher.

Legacy pacific-observatory holds ``viet_nam/vn_moit_fuel/observations.csv`` but never
registered a fetcher for it, so this source only serves the stored rows.
"""

from datetime import date

import pandas as pd


def fetch_vn_moit(cutoff: date) -> pd.DataFrame | None:
    return None


__all__ = ["fetch_vn_moit"]
