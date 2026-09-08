"""Osher Ad (Israel) -- statutory price-transparency feed via the shared
publishedprices.co.il FTPS portal. Large discount supermarket chain.

CORRECTION to the note in ``_shared/menaap/israel_publishedprices.py``: that
docstring records osherad as probed-and-rejected on 2026-08-06 for listing a
Stores-only directory with zero Price/PriceFull files, and presumes the feed
retired. Re-probed live 2026-09-05 and that is no longer true -- the login
lists 141 files including 67 PriceFull; branch snapshot parses 6,771 real
items (spices, sweets, dry grocery) with plausible ILS prices. The earlier
verdict was either a transient empty listing or a since-restored feed.
"""

from datetime import date

import pandas as pd

from prices.fetchers._shared.menaap.israel_publishedprices import (
    fetch_publishedprices_chain,
)

_SOURCE_KEY = "il_osher_ad"
_FTP_USERNAME = "osherad"


def fetch_il_osher_ad(cutoff: date) -> pd.DataFrame | None:
    return fetch_publishedprices_chain(
        source_key=_SOURCE_KEY,
        ftp_username=_FTP_USERNAME,
        cutoff=cutoff,
    )
