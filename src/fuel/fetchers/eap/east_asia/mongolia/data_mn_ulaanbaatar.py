"""data.mn Mongolia weekly fuel prices in Ulaanbaatar (legacy mn_data_mn_fuel_ulaanbaatar).

Legacy fetch_mongolia_data_mn returns all three data.mn datasets at once; keep this
source's rows only, as legacy collect did when it split rows by source_key.
"""

from datetime import date

import pandas as pd

from fuel.fetchers._shared.eap.mongolia import fetch_mongolia_data_mn


def fetch_mn_data_mn_fuel_ulaanbaatar(cutoff: date) -> pd.DataFrame:
    df = fetch_mongolia_data_mn(cutoff)
    if df is None or df.empty:
        return df
    return df[df["source_key"] == "mn_data_mn_fuel_ulaanbaatar"].reset_index(drop=True)
