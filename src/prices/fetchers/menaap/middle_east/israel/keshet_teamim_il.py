"""Keshet Teamim (Israel) -- statutory price-transparency feed via the
shared publishedprices.co.il FTPS portal. Verified live 2026-08-06: login
"Keshet", 2,365 real items (e.g. baked goods), plausible ILS prices. Note:
the newest PriceFull file available at probe time was dated 2024-03-28 --
this chain's feed appears to update infrequently or has since gone stale;
report if repeated runs never advance past that snapshot.
"""

from datetime import date

import pandas as pd

from prices.fetchers._shared.menaap.israel_publishedprices import (
    fetch_publishedprices_chain,
)

_SOURCE_KEY = "il_keshet_teamim"
_FTP_USERNAME = "Keshet"


def fetch_il_keshet_teamim(cutoff: date) -> pd.DataFrame | None:
    return fetch_publishedprices_chain(
        source_key=_SOURCE_KEY,
        ftp_username=_FTP_USERNAME,
        cutoff=cutoff,
    )
