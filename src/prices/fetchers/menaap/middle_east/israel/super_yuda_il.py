"""Super Yuda (Israel) -- statutory price-transparency feed via the shared
publishedprices.co.il FTPS portal. Note this login uses a non-default FTP
subdirectory (/Yuda) and a non-blank password, unlike most other chains on
this portal. Verified live 2026-08-06: login "yuda_ho", 5,486 real items,
plausible ILS prices.
"""

from datetime import date

import pandas as pd

from prices.fetchers._shared.menaap.israel_publishedprices import (
    fetch_publishedprices_chain,
)

_SOURCE_KEY = "il_super_yuda"
_FTP_USERNAME = "yuda_ho"
_FTP_PASSWORD = "Yud@147"
_FTP_PATH = "/Yuda"


def fetch_il_super_yuda(cutoff: date) -> pd.DataFrame | None:
    return fetch_publishedprices_chain(
        source_key=_SOURCE_KEY,
        ftp_username=_FTP_USERNAME,
        ftp_password=_FTP_PASSWORD,
        ftp_path=_FTP_PATH,
        cutoff=cutoff,
    )
