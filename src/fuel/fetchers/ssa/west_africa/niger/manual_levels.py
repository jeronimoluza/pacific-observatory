from datetime import date

import pandas as pd

from fuel.fetchers._shared.manual_levels import read_manual_levels, table_path


def fetch_manual_ne(cutoff: date) -> pd.DataFrame | None:
    return read_manual_levels(table_path("niger"), cutoff)


__all__ = ["fetch_manual_ne"]
