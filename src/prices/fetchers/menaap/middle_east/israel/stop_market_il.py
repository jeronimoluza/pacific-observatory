"""Stop Market (Israel) -- statutory price-transparency feed via the shared
publishedprices.co.il FTPS portal. Verified live 2026-08-06: login
"Stop_Market", 14,837 real items (e.g. wine, frozen goods), plausible
ILS prices.
"""

from datetime import date

import pandas as pd

from prices.fetchers._shared.menaap.israel_publishedprices import (
    fetch_publishedprices_chain,
)

_SOURCE_KEY = "il_stop_market"
_FTP_USERNAME = "Stop_Market"


def fetch_il_stop_market(cutoff: date) -> pd.DataFrame | None:
    return fetch_publishedprices_chain(
        source_key=_SOURCE_KEY,
        ftp_username=_FTP_USERNAME,
        cutoff=cutoff,
    )
