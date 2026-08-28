"""Rami Levy (Israel) -- statutory price-transparency feed via the shared
publishedprices.co.il FTPS portal. Israel's #2 supermarket chain by branch
count (discount-format, ~150+ stores). Verified live 2026-08-06: login
"RamiLevi", branch 001 store 001 PriceFull snapshot, 13,023 real items
(e.g. 'רביעיית פחיות שוופס' Schweppes 4-pack ILS 12.50).
"""

from datetime import date

import pandas as pd

from prices.fetchers._shared.menaap.israel_publishedprices import (
    fetch_publishedprices_chain,
)

_SOURCE_KEY = "il_rami_levy"
_FTP_USERNAME = "RamiLevi"


def fetch_il_rami_levy(cutoff: date) -> pd.DataFrame | None:
    return fetch_publishedprices_chain(
        source_key=_SOURCE_KEY,
        ftp_username=_FTP_USERNAME,
        cutoff=cutoff,
    )
