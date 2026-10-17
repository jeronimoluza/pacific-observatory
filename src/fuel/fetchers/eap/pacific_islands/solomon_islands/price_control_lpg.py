"""LPG rows of the legacy Solomon Islands fetcher, which emits two source_keys."""

from datetime import date

import pandas as pd

from fuel.fetchers._shared.eap.solomon_islands import fetch_solomon_islands


def fetch_sb_lpg(cutoff: date) -> pd.DataFrame:
    df = fetch_solomon_islands(cutoff)
    if df.empty:
        return df
    return df[df["source_key"] == "sb_price_control_lpg_2025"]
