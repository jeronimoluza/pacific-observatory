"""Farm to Table Guam -- CSA (Community Supported Agriculture) share pricing.

https://farmtotableguam.org/csa-app/ is a WordPress site running the
WooCommerce plugin, but the CSA shares themselves are NOT exposed as
WooCommerce products -- the Store API (/wp-json/wc/store/products) returns
zero rows for this site. The eight share tiers (Small/Large share x
Weekly/Every-Other-Week x Pickup/Delivery) are fixed prices hard-coded into
a <select> dropdown on the sign-up form, e.g.:

    <option value="Small Share Weekly Pick-up">Small Share Weekly Pick-up :
    $140.00 USD &#8211; monthly</option>

All eight tiers are farm produce (vegetables grown on Guam); COICOP 01.1.7
(vegetables) is the closest single narrow class and is treated as the whole
source's code per the narrowness rule. Cadence is irregular -- there is no
publication schedule, this is a snapshot of the current sign-up page.
"""

import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://farmtotableguam.org/csa-app/"
_COUNTRY = "Guam"
_CURRENCY = "USD"
_SOURCE_KEY = "gu_farmtotableguam_csa"
_COICOP = "01.1.7"

# label ": $" price " USD"
_OPTION_RE = re.compile(r'<option value="[^"]+">([^<:]+?)\s*:\s*\$([\d.]+)\s*USD', re.I)

_IDENT = ["source_key", "observation_date", "item_name"]


def fetch_gu_farmtotableguam_csa(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()

    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    rows = []
    for label, price in _OPTION_RE.findall(resp.text):
        item_name = f"CSA {label.strip()}"
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item_name,
            "price_local": float(price),
            "currency": _CURRENCY,
            "unit": "month",
            "coicop_code": _COICOP,
            "source_url": _URL,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        logger.warning(
            "gu_farmtotableguam_csa: no CSA share options parsed from %s", _URL
        )
        return None

    return pd.DataFrame(rows)
