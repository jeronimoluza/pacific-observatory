"""Salach Dabach (Israel) -- statutory price-transparency feed via the shared
publishedprices.co.il FTPS portal. Regional full-line supermarket chain
(Jerusalem / centre). Verified live 2026-09-05: login "SalachD", 20 files
listed / 6 PriceFull, branch snapshot 13,044 real items with plausible ILS
prices (grocery plus a housewares aisle).
"""

from datetime import date

import pandas as pd

from prices.fetchers._shared.menaap.israel_publishedprices import (
    fetch_publishedprices_chain,
)

_SOURCE_KEY = "il_salach_dabach"
_FTP_USERNAME = "SalachD"


def fetch_il_salach_dabach(cutoff: date) -> pd.DataFrame | None:
    return fetch_publishedprices_chain(
        source_key=_SOURCE_KEY,
        ftp_username=_FTP_USERNAME,
        cutoff=cutoff,
    )
