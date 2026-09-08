"""Puerto Rico -- AAA (Autoridad de Acueductos y Alcantarillados) water and
sewer tariff, residential, snapshot.

AAA's "Nuestra estructura tarifaria" page
(acueductospr.com/servicios/nuestra-estructura-tarifaria) is a Webflow
site with the actual rate schedule laid out as CSS-grid `<div>`s (class
`grid-table-6`), not `<table>` elements -- `pandas.read_html` sees nothing.
Parsed here with BeautifulSoup instead.

The page covers four customer classes (Residencial / Comercial /
Industrial / Gobierno), each introduced by its own `<h2>` heading, each
with two grids: a "base charge by meter diameter" grid and a "consumption
charge by usage block" grid. This fetcher walks the page in DOM order,
tracks which `<h2>` section it's currently inside, and keeps only the two
grids under "Cargo Base Residencial" -- the household-relevant class; the
other three customer classes are out of scope for the PPP household
basket, same convention as sp_group_tariff.py excluding Singapore's
commercial/industrial electricity supplies.

Verified live 2026-09-06: the Residencial base-charge grid has 11 meter
sizes (½"/⅝" through 12"), the consumption grid has 3 usage blocks
(>10-15 m3, >15-25 m3, >25 m3) -- each row carries three dollar columns
"Agua" (water), "Alcantarillado" (sewer), "Agua y Alc." (combined). The
combined column is the literal sum of the other two (spot-checked:
$17.47 + $13.01 = $30.48) and is skipped as a derived duplicate, same
convention as the DACO fuel fetcher skipping its "Promedio" blend column.
28 rows emitted (11 diameters + 3 blocks, x2 for water/sewer).

Water and sewer are different COICOP classes (04.4.1.1 network water
supply vs 04.4.3.1 sewer collection) but are combined into ONE
manifest/source_key here -- each row carries its own correct leaf code
set in this fetcher, matching the puc_tariff.py (Micronesia) convention
for combining thin-but-related utility tariffs rather than forcing two
manifests for what is one page, one customer class, one effective date.

No historical archive exists on the page -- snapshots the CURRENT
schedule each run (period_kind: effective_from), using the page's own
"Efectiva desde el 1 de julio de 2026" heading text.

Currency: USD, matches countries.yaml (PR's own currency).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_PAGE_URL = "https://www.acueductospr.com/servicios/nuestra-estructura-tarifaria"
_COUNTRY = "Puerto Rico"
_CURRENCY = "USD"
_SOURCE_KEY = "pr_aaa_water_tariff"
_IDENT = ["source_key", "observation_date", "item_name"]
_TARGET_SECTION = "Cargo Base Residencial"

_EFFECTIVE_RE = re.compile(r"Efectiva desde el (\d{1,2}) de (\w+) de (\d{4})", re.I)
_MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
    "diciembre": 12,
}
_DOLLAR_RE = re.compile(r"\$\s*([\d,]+\.\d+)")


def _residential_grids(html: str) -> list[list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    elems = soup.find_all(
        lambda tag: (tag.name == "h2" and "heading" in (tag.get("class") or []))
        or (tag.name == "div" and "grid-table-6" in (tag.get("class") or []))
    )
    grids: list[list[str]] = []
    in_target = False
    for e in elems:
        if e.name == "h2":
            in_target = e.get_text(strip=True) == _TARGET_SECTION
        elif in_target:
            texts = [c.get_text(strip=True) for c in e.find_all(recursive=False)]
            grids.append(texts)
    return grids


def _parse_effective_date(html: str) -> date | None:
    m = _EFFECTIVE_RE.search(html)
    if not m:
        return None
    day, month_es, year = m.groups()
    month = _MONTHS_ES.get(month_es.lower())
    if not month:
        return None
    return date(int(year), month, int(day))


def fetch_pr_aaa_water_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        resp = session.get(_PAGE_URL, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] page fetch failed: %s", _SOURCE_KEY, exc)
        return None

    effective_from = _parse_effective_date(resp.text) or date.today()
    if effective_from <= cutoff:
        logger.info("[%s] no new release past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    grids = _residential_grids(resp.text)
    if len(grids) < 2:
        logger.warning(
            "[%s] expected 2 residential grids, found %d on %s",
            _SOURCE_KEY, len(grids), _PAGE_URL,
        )
        return None

    parsed: list[dict] = []

    # Grid 1: base charge by meter diameter. Cells run
    # [title, "Diámetro","Agua","Alcantarillado","Agua y Alc."] then
    # repeating groups of 4: [diameter, water_$, sewer_$, combined_$].
    base_cells = grids[0][5:]
    for i in range(0, len(base_cells) - 3, 4):
        diameter, water_raw, sewer_raw = base_cells[i], base_cells[i + 1], base_cells[i + 2]
        water_m, sewer_m = _DOLLAR_RE.search(water_raw), _DOLLAR_RE.search(sewer_raw)
        if not (water_m and sewer_m):
            continue
        parsed.append({
            "item_name": f'Water base charge, {diameter} meter',
            "price_local": float(water_m.group(1).replace(",", "")),
            "coicop_code": "04.4.1.1",
        })
        parsed.append({
            "item_name": f'Sewer base charge, {diameter} meter',
            "price_local": float(sewer_m.group(1).replace(",", "")),
            "coicop_code": "04.4.3.1",
        })

    # Grid 2: consumption charge by usage block. Cells run
    # [title,"Bloques","Consumo","Agua","Alcantarillado","Agua y Alc."]
    # then repeating groups of 4: [block_name, range, water_$, sewer_$, combined_$]
    # -- note this group is 5 wide, not 4.
    block_cells = grids[1][6:]
    for i in range(0, len(block_cells) - 4, 5):
        block, usage_range, water_raw, sewer_raw = (
            block_cells[i], block_cells[i + 1], block_cells[i + 2], block_cells[i + 3]
        )
        water_m, sewer_m = _DOLLAR_RE.search(water_raw), _DOLLAR_RE.search(sewer_raw)
        if not (water_m and sewer_m):
            continue
        parsed.append({
            "item_name": f"Water consumption charge, {block} ({usage_range})",
            "price_local": float(water_m.group(1).replace(",", "")),
            "coicop_code": "04.4.1.1",
        })
        parsed.append({
            "item_name": f"Sewer consumption charge, {block} ({usage_range})",
            "price_local": float(sewer_m.group(1).replace(",", "")),
            "coicop_code": "04.4.3.1",
        })

    if not parsed:
        logger.warning("[%s] no rate rows parsed from %s", _SOURCE_KEY, _PAGE_URL)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for p in parsed:
        row = {
            "observation_date": effective_from.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": p["coicop_code"],
            "item_name": p["item_name"],
            "price_local": p["price_local"],
            "currency": _CURRENCY,
            "unit": "month" if "base charge" in p["item_name"] else "1000gal",
            "source_url": _PAGE_URL,
            "notes": "AAA residential water/sewer tariff; 'Agua y Alc.' combined column skipped as a derived sum",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
