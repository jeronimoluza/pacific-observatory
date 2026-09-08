"""Politzer (Israel) -- statutory price-transparency feed via the shared
publishedprices.co.il FTPS portal. Verified live 2026-09-05: login
"politzer", 62 files listed / 9 PriceFull, branch snapshot 10,844 real items
(fresh produce, nuts, packaged grocery) with plausible ILS prices.
"""

from datetime import date

import pandas as pd

from prices.fetchers._shared.menaap.israel_publishedprices import (
    fetch_publishedprices_chain,
)

_SOURCE_KEY = "il_politzer"
_FTP_USERNAME = "politzer"


def fetch_il_politzer(cutoff: date) -> pd.DataFrame | None:
    return fetch_publishedprices_chain(
        source_key=_SOURCE_KEY,
        ftp_username=_FTP_USERNAME,
        cutoff=cutoff,
    )
