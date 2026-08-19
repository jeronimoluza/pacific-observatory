"""Tiv Taam (Israel) -- statutory price-transparency feed via the shared
publishedprices.co.il FTPS portal. A general-merchandise chain known for
carrying non-kosher/imported goods alongside standard grocery. Verified
live 2026-08-06: login "TivTaam", 21,366 real items (e.g. cling film,
cheeses), plausible ILS prices.
"""

from datetime import date

import pandas as pd

from prices.fetchers._shared.menaap.israel_publishedprices import (
    fetch_publishedprices_chain,
)

_SOURCE_KEY = "il_tiv_taam"
_FTP_USERNAME = "TivTaam"


def fetch_il_tiv_taam(cutoff: date) -> pd.DataFrame | None:
    return fetch_publishedprices_chain(
        source_key=_SOURCE_KEY,
        ftp_username=_FTP_USERNAME,
        cutoff=cutoff,
    )
