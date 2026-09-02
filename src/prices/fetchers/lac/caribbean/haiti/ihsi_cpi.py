"""IHSI (Institut Haitien de Statistique et d'Informatique) -- monthly CPI (IPC).

The public IPC page (`_PAGE_URL`) is a server-rendered Laravel Livewire
component. Its visible HTML `<table id="table_ipc">` (the homepage widget)
and the on-page comparison table both render division index levels with the
decimal point silently stripped by the page's own number formatting (e.g.
"629.4" displays/parses as "6294") -- confirmed against the page's own prose
("l'IPC ... chiffre a 624.0 en juin, est passe a 629.4 en juillet"), so
`pandas.read_html` on those tables would ship prices 10x too high. Instead,
this fetcher regex-extracts the Livewire `serverMemo` payload embedded in
the page (`"divisionData":[...]`), which carries the same values as clean,
correctly-decimalled JSON strings ("629.4") before any display formatting is
applied. That payload is HTML-entity-escaped (&quot; for the quotes) so it
is unescaped before `json.loads`.

Base period stated in the page's own prose: "IPC, base 100 en 2017-2018".

`divisionData` carries 13 rows: the "INDICE GENERAL" headline (all-items;
dropped -- no sanctioned headline sentinel, per onboarding doctrine, same
as statsdiv_cpi.py/eso_cpi.py) plus 12 COICOP-labelled divisions matching
the *standard* pre-2018 12-division scheme 1:1 (no separate division 13 --
"Biens et services divers" is IHSI's division 12, same shape as Antigua and
Barbuda's statsdiv_cpi.py). Each division's `indices` dict holds ~4 rolling
months keyed by abbreviated French month + 2-digit year ("juil. 26"); only
the latest (max year, month) column is emitted per run.

Verified live 2026-09-01: 13 divisions parsed, latest column "juil. 26"
(July 2026), INDICE GENERAL 629.4, matches the page's own prose exactly.
"""

from __future__ import annotations

import html
import json
import logging
import unicodedata
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_PAGE_URL = "https://ihsi.gouv.ht/statistiques/statistiques_economiques/ipc"
_COUNTRY = "Haiti"
_SOURCE_KEY = "ihsi_cpi"
_BASE_PERIOD = "2017-2018=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_DIVISION_COICOP = {
    "produits alimentaires et boissons non alcoolisees": "01",
    "boissons alcoolisees, tabac et stupefiants": "02",
    "articles d'habillement et chaussures": "03",
    "logement, eau, gaz, electricite, et autres combustibles": "04",
    "meubles, articles de menage et entretien courant du foyer": "05",
    "sante": "06",
    "transport": "07",
    "communication": "08",
    "loisirs": "09",
    "enseignement": "10",
    "restaurants": "11",
    "biens et services divers": "12",
}

_MONTH_NUM = {
    "janv": 1,
    "fevr": 2,
    "mars": 3,
    "avr": 4,
    "mai": 5,
    "juin": 6,
    "juil": 7,
    "aout": 8,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def _parse_month_key(key: str) -> tuple[int, int] | None:
    """'juil. 26' -> (2026, 7); returns None if unparseable."""
    norm = _strip_accents(key.lower()).replace(".", "").strip()
    parts = norm.split()
    if len(parts) != 2:
        return None
    mon, yr = parts
    mon = mon[:4] if mon[:4] in _MONTH_NUM else mon[:3]
    if mon not in _MONTH_NUM or not yr.isdigit():
        return None
    return (2000 + int(yr), _MONTH_NUM[mon])


def _extract_division_data(html_text: str) -> list[dict] | None:
    # The payload sits inside a Livewire wire:snapshot HTML attribute, so its
    # quotes are HTML-entity-escaped (&quot;divisionData&quot;) in the raw
    # response -- do not search for a literal '"divisionData"'.
    idx = html_text.find("divisionData")
    if idx < 0:
        return None
    start = html_text.find("[", idx)
    if start < 0:
        return None
    depth = 0
    end = None
    for i in range(start, len(html_text)):
        c = html_text[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return None
    try:
        return json.loads(html.unescape(html_text[start:end]))
    except (ValueError, TypeError) as exc:
        logger.warning("[%s] divisionData JSON parse failed: %s", _SOURCE_KEY, exc)
        return None


def fetch_ihsi_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_PAGE_URL, timeout=30)
    resp.raise_for_status()

    data = _extract_division_data(resp.text)
    if not data:
        logger.warning(
            "[%s] no divisionData payload found on %s", _SOURCE_KEY, _PAGE_URL
        )
        return None

    # Latest (year, month) shared across every division's `indices` dict.
    all_keys: set[str] = set()
    for row in data:
        all_keys.update((row.get("indices") or {}).keys())
    parsed_keys = [(k, _parse_month_key(k)) for k in all_keys]
    parsed_keys = [(k, ym) for k, ym in parsed_keys if ym is not None]
    if not parsed_keys:
        logger.warning("[%s] no parseable month columns", _SOURCE_KEY)
        return None
    latest_key, (year, month) = max(parsed_keys, key=lambda t: t[1])
    obs_date = date(year, month, 1)

    if obs_date <= cutoff:
        logger.info(
            "[%s] latest release %s is not newer than cutoff", _SOURCE_KEY, obs_date
        )
        return None

    rows = []
    for entry in data:
        name = str(entry.get("name") or "").strip()
        norm_name = _strip_accents(name.lower())
        coicop = _DIVISION_COICOP.get(norm_name)
        if coicop is None:
            continue  # drops "INDICE GENERAL" headline -- no sanctioned sentinel
        raw_val = (entry.get("indices") or {}).get(latest_key)
        if raw_val is None:
            continue
        try:
            idx_val = float(str(raw_val).replace(",", "."))
        except ValueError:
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop,
            "index_value": idx_val,
            "index_base_period": _BASE_PERIOD,
            "source_url": _PAGE_URL,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] %d division rows for %s", _SOURCE_KEY, len(rows), obs_date)
    return pd.DataFrame(rows) if rows else None
