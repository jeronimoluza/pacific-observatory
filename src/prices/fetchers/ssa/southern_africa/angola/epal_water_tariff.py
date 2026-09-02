"""EPAL (Empresa Publica de Aguas de Luanda) -- household/commercial water
tariff, Angola.

EPAL's "comercial.php" page (a static Bootstrap page, not a JS app) embeds
a "Tarifario" HTML table directly in server-rendered markup -- no PDF, no
API, no JS rendering needed. The table lists 7 tariff categories:
"Domesticos" (three consumption-bracket rows: Tarifa Basica 0-10 m3,
Tarifa de Transicao 10-15 m3, Tarifa Basica >15 m3), "Comercio e Servicos",
"Industria", "Chafariz" (public standpipe) and "Girafa" (water-kiosk/tanker
fill point). Each row carries a variable per-m3 rate ("Tarifario variavel")
and a fixed monthly charge ("Tarifa fixa mensal"); only the variable rate
is emitted here (same scope choice as seeg_electricity_tariff_ga.py for
Gabon's separate fixed F/kW charge) since PriceObservation has one
price_local slot and the per-m3 rate is what varies with consumption.

CURRENCY TRAP (see the wave-10 Angola brief): EPAL prints its fixed
monthly charges with Portuguese formatting -- period as thousands
separator, comma as decimal ("3.900 Kz" = three thousand nine hundred, NOT
3.9). The variable per-m3 rates on this specific table happen to be small
enough to have no separator either way ("59 Kz/m3"), but
`_parse_aoa_kz` is written to handle both forms uniformly rather than
relying on that being true forever.

No effective/decree date is printed anywhere on the page (unlike SEEG's
PDF cover sheet), so `period_kind` is `snapshot` (today's scrape date),
not `effective_from` -- this is "whatever EPAL currently publishes as
live", re-fetched fresh every run, not a dated tariff order.

The page is Luanda-only (EPAL = "Empresa Publica de Aguas de Luanda",
~499,478 clients per its own "Ao Servico do Cliente" copy; its Facebook
handle is literally "epaldeluanda") -- `subnational_area` is set to
"Luanda" on every row rather than left null.

TLS note: www.epal.co.ao (like several other .ao / .ug utility sites in
this repo) serves without a complete certificate chain -- `verify=False`
is required, same workaround as ubos_cpi.py.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.epal.co.ao/comercial.php"
_COUNTRY = "Angola"
_CURRENCY = "AOA"
_SOURCE_KEY = "epal_water_tariff_ao"
_COICOP_CODE = "04.4.1"
_SUBNATIONAL = "Luanda"
_IDENT = ["source_key", "observation_date", "item_name"]

_AOA_RE = re.compile(r"([\d.,]+)\s*Kz")


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text) if text else text


def _parse_aoa_kz(text: str) -> float | None:
    """Parse a Portuguese-formatted AOA amount: '.' = thousands separator,
    ',' = decimal separator. '3.900 Kz' -> 3900.0; '59 Kz/m3' -> 59.0."""
    m = _AOA_RE.search(text or "")
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_table(html_text: str) -> list[dict]:
    soup = BeautifulSoup(html_text, "html.parser")
    anchor = soup.find(id="tarf")
    if anchor is None:
        return []
    table = anchor.find("table")
    if table is None:
        return []

    rows: list[dict] = []
    for tr in table.find_all("tr", class_="tablebody"):
        cells = tr.find_all(["th", "td"])
        texts = [_nfc(c.get_text(" ", strip=True)) for c in cells]
        if len(texts) < 5:
            continue
        # colspan=2 rows (Comercio/Industria/Chafariz/Girafa) collapse the
        # category+subcategory columns into one cell -> only 4 data cells
        # after the ordinal; 3-column "Domesticos" rows keep them separate.
        if len(texts) == 6:
            _, category, subcategory, variable, fixed, rule = texts
            label = f"{category} - {subcategory}" if subcategory else category
        else:
            _, category, variable, fixed, rule = texts[:5]
            label = category
        variable_price = _parse_aoa_kz(variable)
        if variable_price is None:
            continue
        item_name = f"EPAL {label} ({rule})"
        rows.append(
            {
                "item_name": item_name,
                "price_local": variable_price,
                "unit": "m3",
                "notes": (
                    f"Tarifario variavel per m3; fixed monthly charge "
                    f"({fixed}) excluded -- rule: {rule}"
                ),
            }
        )
    return rows


def fetch_epal_water_tariff_ao(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30, verify=False)
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %d for %s", _SOURCE_KEY, resp.status_code, _URL)
        return None

    parsed = _parse_table(resp.text)
    if not parsed:
        logger.warning(
            "[%s] No tariff rows parsed from %s -- page layout may have changed",
            _SOURCE_KEY,
            _URL,
        )
        return None

    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    ts = get_scrape_ts()
    rows = []
    for item in parsed:
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "subnational_area": _SUBNATIONAL,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": item["item_name"],
            "price_local": item["price_local"],
            "currency": _CURRENCY,
            "unit": item["unit"],
            "source_url": _URL,
            "notes": item["notes"],
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
