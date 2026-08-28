"""ANP (Brazil) -- weekly per-station fuel price survey, aggregated to state level.

ANP (Agencia Nacional do Petroleo, Gas Natural e Biocombustiveis) publishes a
statutory weekly price survey of individual fuel stations nationwide as CSV
downloads linked from a public gov.br page -- semicolon-delimited,
Brazilian-locale decimal commas, one row per (station, product, collection
date). The raw files are enormous (single-month gasolina/etanol file ~8MB,
tens of thousands of station-level rows) so this fetcher aggregates to a
national-avg-per-state daily observation rather than emitting every station
row, mirroring the ODEPA Chile wholesale pattern (collapse per-outlet rows to
a state-level average per product/day).

Known gotcha for future maintainers: the CSV filenames under
.../arquivos/shpc/dsan/{year}/ are NOT consistently named month to month
(e.g. 2026 has "01-dados-abertos-precos-glp.csv" but also a typo'd
"02-cados-abertos-preco-gasolina-etanol.csv", and April 2026 is simply
missing from the index). Do not construct URLs from a fixed pattern --
always re-scrape the index page and match on the fuel-type substring in the
href, restricted to the current year's directory segment (which IS a
reliable path component, unlike the filename).
"""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_INDEX_URL = (
    "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/"
    "serie-historica-de-precos-de-combustiveis"
)
_COUNTRY = "Brazil"
_CURRENCY = "BRL"
_SOURCE_KEY = "br_anp_fuel"

# Substring match on href (lowercased) -> COICOP code for every "Produto" value
# that substring's file can contain.
_FUEL_TYPE_SUBSTR = ("diesel", "gasolina", "glp")

_COICOP_MAP = {
    "GASOLINA": "07.2.2",
    "GASOLINA ADITIVADA": "07.2.2",
    "ETANOL": "07.2.2",
    "DIESEL": "07.2.2",
    "DIESEL S10": "07.2.2",
    "GNV": "07.2.2",
    "GLP": "04.5.4",  # bottled cooking gas
}

_IDENT = ["source_key", "observation_date", "subnational_area", "item_name"]
_MAX_FILES_PER_RUN = 6  # safety cap; current-year dir typically has <= ~20 links


def _discover_urls(session) -> list[str]:
    try:
        r = session.get(_INDEX_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] index page fetch failed: %s", _SOURCE_KEY, exc)
        return []
    year = date.today().year
    pattern = re.compile(rf'href="([^"]*dsan/{year}/[^"]*\.csv)"', re.IGNORECASE)
    hrefs = pattern.findall(r.text)
    urls = []
    for h in hrefs:
        low = h.lower()
        if any(s in low for s in _FUEL_TYPE_SUBSTR):
            urls.append(h if h.startswith("http") else f"https://www.gov.br{h}")
    # de-dup, keep order
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:_MAX_FILES_PER_RUN]


def _parse_price(s: str) -> float | None:
    if not s:
        return None
    try:
        return float(s.strip().replace(",", "."))
    except ValueError:
        return None


def _aggregate_csv(raw_bytes: bytes, url: str, cutoff: date) -> list[dict]:
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    # groups[(estado, produto, obs_date)] -> {"sum": float, "n": int, "unidade": str}
    groups: dict[tuple, dict] = {}
    for row in reader:
        estado = (row.get("Estado - Sigla") or "").strip()
        produto = (row.get("Produto") or "").strip().upper()
        data_str = (row.get("Data da Coleta") or "").strip()
        preco = _parse_price(row.get("Valor de Venda", ""))
        unidade = (row.get("Unidade de Medida") or "").strip()
        if not (estado and produto and data_str and preco and preco > 0):
            continue
        try:
            day, month, yr = data_str.split("/")
            obs_date = date(int(yr), int(month), int(day))
        except (ValueError, AttributeError):
            continue
        if obs_date <= cutoff:
            continue
        key = (estado, produto, obs_date)
        g = groups.setdefault(key, {"sum": 0.0, "n": 0, "unidade": unidade})
        g["sum"] += preco
        g["n"] += 1

    ts = get_scrape_ts()
    rows: list[dict] = []
    for (estado, produto, obs_date), g in groups.items():
        coicop = _COICOP_MAP.get(produto)
        if not coicop:
            logger.warning(
                "[%s] no COICOP mapping for produto %r -- dropping",
                _SOURCE_KEY,
                produto,
            )
            continue
        avg_price = round(g["sum"] / g["n"], 4)
        unit = g["unidade"].replace("R$", "").replace("/", "").strip().lower() or None
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "weekly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "subnational_area": estado,
            "item_name": produto.title(),
            "price_local": avg_price,
            "currency": _CURRENCY,
            "unit": unit,
            "coicop_code": coicop,
            "source_url": url,
            "notes": f"state avg of {g['n']} station observations",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_br_anp_fuel(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    urls = _discover_urls(session)
    if not urls:
        logger.warning("[%s] no CSV links discovered on index page", _SOURCE_KEY)
        return None

    frames: list[dict] = []
    for url in urls:
        try:
            r = session.get(url, timeout=120)
            r.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] CSV fetch failed for %s: %s", _SOURCE_KEY, url, exc)
            continue
        rows = _aggregate_csv(r.content, url, cutoff)
        frames.extend(rows)

    if not frames:
        return None
    logger.info(
        "[%s] %d state-avg rows from %d files (cutoff=%s)",
        _SOURCE_KEY,
        len(frames),
        len(urls),
        cutoff,
    )
    return pd.DataFrame(frames)
