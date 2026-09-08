"""Fresh Market (Israel) -- statutory price-transparency feed via the shared
publishedprices.co.il FTPS portal. Verified live 2026-09-05: login
"freshmarket", 147 files listed / 51 PriceFull, branch snapshot 10,167 real
items (dairy, dry grocery, personal care) with plausible ILS prices.
"""

from datetime import date

import pandas as pd

from prices.fetchers._shared.menaap.israel_publishedprices import (
    fetch_publishedprices_chain,
)

_SOURCE_KEY = "il_fresh_market"
_FTP_USERNAME = "freshmarket"


def fetch_il_fresh_market(cutoff: date) -> pd.DataFrame | None:
    return fetch_publishedprices_chain(
        source_key=_SOURCE_KEY,
        ftp_username=_FTP_USERNAME,
        cutoff=cutoff,
    )
