"""Dor Alon (Israel) -- statutory price-transparency feed via the shared
publishedprices.co.il FTPS portal. Fuel-forecourt convenience chain (AM:PM
brand). Verified live 2026-08-06: login "doralon", 5,045 real items (e.g.
frozen peas), plausible ILS prices.
"""

from datetime import date

import pandas as pd

from prices.fetchers._shared.menaap.israel_publishedprices import (
    fetch_publishedprices_chain,
)

_SOURCE_KEY = "il_dor_alon"
_FTP_USERNAME = "doralon"


def fetch_il_dor_alon(cutoff: date) -> pd.DataFrame | None:
    return fetch_publishedprices_chain(
        source_key=_SOURCE_KEY,
        ftp_username=_FTP_USERNAME,
        cutoff=cutoff,
    )
