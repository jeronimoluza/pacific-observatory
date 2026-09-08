"""Nauru Utilities Corporation (NUC) -- electricity tariff.

The "Tariffs & Rates" page (`/services-4`, a Wix rich-text block) lists
per-kWh electricity rates as plain `<li>` bullet text grouped under
`<h3>`-level customer-class headings (Residential, Commercial, Industrial,
Government) -- e.g. "Residential" > "Lifeline&nbsp;...$0.17 kWh". Confirmed
server-rendered (Wix SSR) 2026-09-06, no JS needed for this text.

Each customer-class section also lists water-consumption-band flat charges
(e.g. "4000L $38.60") on the SAME page -- deliberately NOT parsed here. A
banded flat fee tied to a consumption tier is a different tariff shape than
a straightforward $/kWh rate (it's not clear what customer behaviour maps
to which band without more context than the page gives), so per the
onboarding skill's "two shapes on one site" guidance this would need its
own manifest and its own modelling decision -- left as a follow-up rather
than force-fit into a per-unit price.

Nauru uses AUD (no local currency) per countries.yaml -- confirmed by the
page's own "$" figures being in the same magnitude as other AUD-priced
NUC/Digicel Nauru sources already in the corpus.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.nuc.com.nr/services-4"
_COUNTRY = "Nauru"
_CURRENCY = "AUD"
_SOURCE_KEY = "nr_nuc_electricity_tariff"
_COICOP = "04.5.1.0"
_UNIT = "kWh"
_IDENT = ["source_key", "item_name", "price_local"]

_CLASS_HEADINGS = {"residential", "commercial", "industrial", "government"}
_RATE_RE = re.compile(r"^(.+?)\s*\$([\d.]+)\s*k?wh$", re.IGNORECASE)


def _parse_rates(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    current_class: str | None = None
    out: list[dict] = []

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "li"]):
        text = tag.get_text(" ", strip=True).replace("\xa0", " ")
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue

        if tag.name.startswith("h") and text.lower() in _CLASS_HEADINGS:
            current_class = text
            continue
        if tag.name.startswith("h"):
            # Any other heading (Hire Services, Other Services, ...) ends
            # the customer-class electricity block for this page.
            if text.lower() not in _CLASS_HEADINGS:
                current_class = None
            continue

        if current_class is None or tag.name != "li":
            continue

        m = _RATE_RE.match(text)
        if not m:
            continue  # water-band lines ("4000L $38.60") don't match this shape
        plan_name, rate_text = m.group(1).strip(), m.group(2)
        try:
            rate = float(rate_text)
        except ValueError:
            continue
        if rate <= 0:
            continue

        out.append(
            {
                "item_name": f"{current_class} – {plan_name}",
                "price_local": rate,
            }
        )

    return out


def fetch_nr_nuc_electricity_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()

    parsed = _parse_rates(resp.text)
    if not parsed:
        logger.warning("[%s] No electricity rate rows found at %s", _SOURCE_KEY, _URL)
        return None

    observation_date = datetime.now(timezone.utc).date()
    if observation_date <= cutoff:
        return None

    rows = []
    seen = set()
    for item in parsed:
        row = {
            "observation_date": observation_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item["item_name"],
            "price_local": item["price_local"],
            "currency": _CURRENCY,
            "unit": _UNIT,
            "coicop_code": _COICOP,
            "source_url": _URL,
            "notes": (
                "NUC per-kWh electricity rate by customer class, snapshot "
                "at fetch time (no published effective date on the page)."
            ),
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        if row["observation_hash"] in seen:
            continue
        seen.add(row["observation_hash"])
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
