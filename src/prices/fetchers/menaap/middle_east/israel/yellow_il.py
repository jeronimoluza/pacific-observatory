"""Yellow (Israel) -- statutory price-transparency feed via the shared
publishedprices.co.il FTPS portal. Paz's fuel-forecourt convenience chain
(FTP login "Paz_bo"). Verified live 2026-08-06: 522 real items including
non-food (e.g. lighters), plausible ILS prices.
"""

from datetime import date

import pandas as pd

from prices.fetchers._shared.menaap.israel_publishedprices import (
    fetch_publishedprices_chain,
)

_SOURCE_KEY = "il_yellow"
_FTP_USERNAME = "Paz_bo"
_FTP_PASSWORD = "paz468"


def fetch_il_yellow(cutoff: date) -> pd.DataFrame | None:
    return fetch_publishedprices_chain(
        source_key=_SOURCE_KEY,
        ftp_username=_FTP_USERNAME,
        ftp_password=_FTP_PASSWORD,
        cutoff=cutoff,
    )
