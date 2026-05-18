"""El Salvador DGEHM biweekly reference fuel price fetcher.

Source: Dirección General de Energía, Hidrocarburos y Minas (estadísticas portal).
Front page: https://estadisticas.dgehm.gob.sv/combustibles/precios-referencia/

The user-facing chart is rendered inside an iframe at
`/wp-content/graficosEstadisticas/hidrocarburosPreciosReFiltro.php` which
fires a POST to `hidrocarburosPreciosReFi.php` with these form params:

  anio        : 2-digit year, "17"-"26" (the requested year)
  TipoRecurso : GS | GR | DO | DO-LS  (Gasolina Especial / Regular /
                Diesel / Diesel Bajo Azufre)
  TipoRe      : 1 | 2 | 3              (Zona Occidental / Central / Oriental)

The response is an HTML fragment containing `var datosGraficoN = {...}`
JavaScript objects. `datosGrafico2` carries the reference price series for
the requested combination:

  xAxis  : ["04-01-2011", "18-01-2011", ...]   biweekly DD-MM-YYYY (sometimes
                                               DD/MM/YYYY for newer entries)
  series : [{"name": "Prec.Referencia", "data": [2.46, 2.37, ...]}]   US$/gal

Each query returns roughly the last ~7 years ending at the requested year.
Two slices (anio=17 and anio=24) together cover 2011-01-04 → 2024-02-20.
We average the three zones to a national reference per (date, product).

Pricing regime: the FERE ("Fórmula de Estructura de Reajustes Económicos")
is a biweekly state-set reference; distributors set retail prices at or
below it. carry_forward=true at the YAML level since the reference applies
until the next biweekly resolución. The dataset is currently frozen at
2024-02-20.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, datetime
from statistics import mean

import pandas as pd
import urllib3

from core.http import make_session

# Server returns 200 but the cert chain isn't sent — same pattern as
# Acodeco / Bangladesh BPC / Nicaragua INE.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

_IFRAME_URL = (
    "https://estadisticas.dgehm.gob.sv/wp-content/"
    "graficosEstadisticas/hidrocarburosPreciosReFiltro.php"
)
_AJAX_URL = (
    "https://estadisticas.dgehm.gob.sv/wp-content/"
    "graficosEstadisticas/hidrocarburosPreciosReFi.php"
)
_REQUEST_DELAY_S = 0.4

_COUNTRY = "El Salvador"
_CURRENCY = "USD"
_SOURCE_KEY = "sv_dgehm_biweekly"

# Two year slices cover the full archive 2011-01 → 2024-02.
# anio=17 → 2011-2017, anio=24 → 2018-2024. Any later year just truncates
# from the same Feb-2024 tail.
_YEAR_SLICES = ("17", "24")
_ZONES = ("1", "2", "3")
_FUELS = {
    "GS": "Gasolina Especial",
    "GR": "Gasolina Regular",
    "DO": "Diesel",
    "DO-LS": "Diesel Bajo en Azufre",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept": "*/*",
    "Accept-Language": "es-SV,es;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": _IFRAME_URL,
}

# Match the `datosGrafico2 = { ... }` block and pull out its xAxis array
# and the first series.data array. We rely on JSON-parseable substrings
# rather than a full JS-to-Python translation since the block contains
# trailing commas etc.
_BLOCK_RE = re.compile(
    r"var\s+datosGrafico2\s*=\s*\{(.*?)\}\s*(?=var\s+datosGrafico|<|$)",
    re.DOTALL,
)
_XAXIS_RE = re.compile(r"xAxis\s*:\s*(\[[^\]]*\])", re.DOTALL)
_SERIES_DATA_RE = re.compile(r'"data"\s*:\s*(\[[^\]]*\])')


def _parse_grafico2(html: str) -> tuple[list[date], list[float]]:
    """Return (dates, prices) parsed from the AJAX HTML fragment.

    Returns empty lists if no usable series is present.
    """
    block_match = _BLOCK_RE.search(html)
    if not block_match:
        return [], []
    block = block_match.group(1)
    xaxis_match = _XAXIS_RE.search(block)
    data_match = _SERIES_DATA_RE.search(block)
    if not xaxis_match or not data_match:
        return [], []

    # xAxis is a JSON array of quoted strings; escape JS forward-slashes
    # ("08\/03\/2022") that requests already converted to literal "08/03/2022"
    # plus DD-MM-YYYY entries.
    try:
        date_tokens = json.loads(xaxis_match.group(1).replace(r"\/", "/"))
    except json.JSONDecodeError:
        return [], []
    try:
        price_tokens = json.loads(data_match.group(1))
    except json.JSONDecodeError:
        return [], []

    dates: list[date] = []
    prices: list[float] = []
    for d_tok, p_tok in zip(date_tokens, price_tokens):
        if not isinstance(d_tok, str) or not d_tok.strip():
            continue
        try:
            price = float(p_tok)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        d = _parse_date(d_tok)
        if d is None:
            continue
        dates.append(d)
        prices.append(price)
    return dates, prices


def _parse_date(token: str) -> date | None:
    token = token.strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    return None


def _query(session, year: str, fuel: str, zone: str) -> tuple[list[date], list[float]]:
    try:
        r = session.post(
            _AJAX_URL,
            data={"anio": year, "TipoRecurso": fuel, "TipoRe": zone},
            timeout=45,
            verify=False,
        )
        if r.status_code != 200:
            return [], []
    except Exception:
        logger.warning(
            "[sv_dgehm] AJAX failed anio=%s fuel=%s zone=%s", year, fuel, zone
        )
        return [], []
    return _parse_grafico2(r.text)


def fetch_sv_dgehm(cutoff: date) -> pd.DataFrame | None:
    """Fetch El Salvador DGEHM biweekly national-avg reference prices (USD/gal)."""
    session = make_session(**_HEADERS)

    # Per (fuel, date) accumulate observations from each zone, then
    # average across zones for a national figure.
    bucket: dict[tuple[str, str], list[float]] = {}
    for year in _YEAR_SLICES:
        for fuel_code, fuel_name in _FUELS.items():
            for zone in _ZONES:
                dates, prices = _query(session, year, fuel_code, zone)
                time.sleep(_REQUEST_DELAY_S)
                for d, p in zip(dates, prices):
                    if d <= cutoff:
                        continue
                    key = (fuel_name, d.strftime("%Y-%m-%d"))
                    bucket.setdefault(key, []).append(p)
                logger.info(
                    "[sv_dgehm] anio=%s fuel=%s zone=%s → %d obs",
                    year,
                    fuel_code,
                    zone,
                    len(dates),
                )

    if not bucket:
        logger.info("[sv_dgehm] No new rows after cutoff %s", cutoff)
        return None

    rows: list[dict] = []
    for (fuel_name, date_str), zone_prices in bucket.items():
        # National average = simple mean across the available zones for that
        # (fuel, date). If a zone happened to miss this date, we still emit
        # the row with the remaining zones — this is the same convention the
        # DGEHM chart uses when a zone reports late.
        nat_avg = mean(zone_prices)
        rows.append(
            {
                "observation_date": date_str,
                "country": _COUNTRY,
                "fuel_product": fuel_name,
                "price_local": round(nat_avg, 4),
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": "GAL",
            }
        )

    out = (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info("[sv_dgehm] Returning %d rows (cutoff: %s)", len(out), cutoff)
    return out
