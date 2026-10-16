"""Family key for the USD family aggregate.

A series_key ending in ``_regulated`` is an official regulated price published next
to a market series of the same family (Guinea-Bissau: BCEAO next to the WB RTEP
market median). It is averaged into its own family, ``<family>_regulated``, never
into the market family; every other series keeps its plain family.
"""

from __future__ import annotations

import pandas as pd

REGULATED_SUFFIX = "_regulated"


def family_key(df: pd.DataFrame) -> pd.Series:
    regulated = df["series_key"].astype(str).str.endswith(REGULATED_SUFFIX)
    return df["fuel_family"].where(~regulated, df["fuel_family"] + REGULATED_SUFFIX)


def base_family(families: pd.Series) -> pd.Series:
    return families.str.removesuffix(REGULATED_SUFFIX)
