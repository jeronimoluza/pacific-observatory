"""Liechtensteinische Kraftwerke (LKW) -- domestic household electricity
tariff schedule ("LKWclassic" fixed-price product), snapshot.

LKW is Liechtenstein's own electricity utility (not a Swiss re-export --
LKW operates the domestic grid and publishes its own household tariff
page). Verified live 2026-09-01:
https://www.lkw.li/angebot-und-leistungen/strom-und-waerme/stromtarife.html
-> 200, plain server-rendered HTML (no JS hydration needed).

The page publishes THREE distinct products (LKWclassic fixed-price,
LKWflex market-time-of-use, LKWfree hourly-dynamic); this fetcher covers
**LKWclassic** only -- the standard fixed-annual-price product, which is
the one genuinely tabular across two dated periods:

  Preise (gueltig bis 31.12.2025): Hochtarif 12.80 / Niedertarif 10.90 Rp/kWh
  Preise (gueltig ab 1.1.2026): Hochtarif 11.26 / Niedertarif 10.55,
    Einheitstarif (flat, no day/night split) 10.70 Rp/kWh

Each period/band is additionally offered in three product tiers sharing the
same base price: **Basisstrom** (plain grid mix), **LiStrom natur**
(Basisstrom + 1.00 Rp/kWh green-energy surcharge), and **LiStrom natur
plus** (Basisstrom + 5.00 Rp/kWh). This fetcher emits the full computed
per-kWh price for all three tiers (not just the surcharge) -- 9 rows for
the current period (3 bands x 3 tiers) + 6 for the prior period (2 bands x
3 tiers, no Einheitstarif existed pre-2026) = 15 rows total, a genuine
2025-to-2026 household electricity price comparison, not a single
snapshot. LKWflex (time-of-use, adjusted monthly, +1.70 Rp/kWh handling
fee) and LKWfree (hourly EPEX-indexed) are descriptive/non-tabular on this
page and are out of scope for this fetcher.

CURRENCY: Rp./kWh (Rappen, CHF cents) -- divided by 100 before emitting
price_local in CHF/kWh, per the CHF centime-pricing convention.

This is a genuinely different data source from `eurostat_electricity`
(dataset nrg_pc_204, a Eurostat cross-country household electricity price
STATISTIC) -- LKW is the utility's own published rate schedule at the
band/tier granularity Eurostat does not report. No shared backend, no
shared product_id namespace.

period_kind: effective_from, keyed to each period's stated start date. No
earlier LKWclassic archive was found on the page; a re-run will pick up
the NEXT dated period once LKW republishes for 2027, but is otherwise
static -- do not expect new rows every run.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Liechtenstein"
_SOURCE_KEY = "lkw_stromtarife"
_URL = "https://www.lkw.li/angebot-und-leistungen/strom-und-waerme/stromtarife.html"
_COICOP_CODE = "04.5.1"
_IDENT = ["source_key", "observation_date", "item_name"]
_FALLBACK_DATE = date(2015, 1, 1)

_TIERS = [
    ("Basisstrom", 0.0),
    ("LiStrom natur", 1.0),
    ("LiStrom natur plus", 5.0),
]

_PERIOD_RE = re.compile(
    r"Preise \(g(?:ü|ue)ltig (bis|ab) ([\d.]+)\)\s*"
    r"Basisstrom LiStrom natur LiStrom natur plus\s*"
    r"Hoch-\s*/\s*Niedertarif \(Rp\./kWh\)\s*([\d.]+)\s*/\s*([\d.]+)\s*"
    r"\+\s*([\d.]+)\*\s*\+\s*([\d.]+)\*"
    r"(?:\s*Einheitstarif \(Rp\./kWh\)\s*([\d.]+)\s*\+\s*([\d.]+)\*\s*\+\s*([\d.]+)\*)?"
)


def _de_date(raw: str) -> date:
    d, m, y = raw.split(".")
    return date(int(y), int(m), int(d))


def _strip_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    return re.sub(r"\s+", " ", text)


def fetch_lkw_stromtarife(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        resp = session.get(_URL, timeout=30)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] fetch failed: %s", _SOURCE_KEY, exc)
        return None

    text = _strip_tags(resp.text)
    matches = list(_PERIOD_RE.finditer(text))
    if not matches:
        logger.warning("[%s] LKWclassic price blocks not found", _SOURCE_KEY)
        return None

    parsed: list[dict] = []
    for m in matches:
        direction, period_raw, hoch, nieder, natur_add, plus_add = m.group(
            1, 2, 3, 4, 5, 6
        )
        einheit, e_natur_add, e_plus_add = m.group(7, 8, 9)
        period_date = _de_date(period_raw)
        # "bis" marks the END of a period; approximate its start as the
        # start of that same tariff year (LKW republishes annually).
        obs_date = (
            date(period_date.year - 1, 1, 1) if direction == "bis" else period_date
        )

        bands = {"Hochtarif": float(hoch), "Niedertarif": float(nieder)}
        if einheit is not None:
            bands["Einheitstarif"] = float(einheit)

        for band_name, base_rp in bands.items():
            for tier_name, surcharge_rp in _TIERS:
                parsed.append(
                    {
                        "observation_date": obs_date,
                        "item_name": f"LKWclassic {tier_name} {band_name}",
                        "price_rp": base_rp + surcharge_rp,
                        "period_label": f"gueltig {direction} {period_raw}",
                    }
                )

    if not parsed:
        logger.warning("[%s] no tariff rows parsed", _SOURCE_KEY)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for p in parsed:
        if p["observation_date"] <= cutoff:
            continue
        price_chf = round(p["price_rp"] / 100.0, 6)
        row = {
            "observation_date": p["observation_date"].isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": p["item_name"],
            "price_local": price_chf,
            "currency": "CHF",
            "unit": "kWh",
            "source_url": _URL,
            "notes": (
                f"LKW household electricity tariff, LKWclassic fixed-price "
                f"product, {p['period_label']}."
            ),
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        logger.info("[%s] no new rows past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows)
