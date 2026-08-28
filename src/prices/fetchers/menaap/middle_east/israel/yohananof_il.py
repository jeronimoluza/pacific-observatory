"""Yohananof (Israel) -- statutory price-transparency feed via the shared
publishedprices.co.il FTPS portal. Mid-size supermarket chain. Verified
live 2026-08-06: login "yohananof", 10,846 real items (e.g. cheeses),
plausible ILS prices.
"""

from datetime import date

import pandas as pd

from prices.fetchers._shared.menaap.israel_publishedprices import (
    fetch_publishedprices_chain,
)

_SOURCE_KEY = "il_yohananof"
_FTP_USERNAME = "yohananof"


def fetch_il_yohananof(cutoff: date) -> pd.DataFrame | None:
    return fetch_publishedprices_chain(
        source_key=_SOURCE_KEY,
        ftp_username=_FTP_USERNAME,
        cutoff=cutoff,
    )
