"""INE STP (Instituto Nacional de Estatística) — Consumer Price Index, monthly.

INE STP (ine.st) publishes its "Índice de Preços no Consumidor" (IPC) as a Joomla +
Phoca Download document tree: /informacoes-estatisticas/ipc links a category "IPC Ano"
(id 78) containing one subcategory per year (2018-2026, discovered dynamically), each
containing one subcategory per month (Janeiro..Dezembro), each holding 2-3 files: a
"Nota_Explicativa" PDF and one or two "Resultado_IPC_<Mes><Year>" spreadsheets. When two
Resultado files exist for a month, "Publicação2" is a class-level (4/5-digit COICOP-ish
code) breakdown and the other ("Publicação1", or the sole file when there is only one) is
the division-level (01-12) table used here.

Verified live 2026-09-01. Two format quirks discovered:
1. Phoca Download's per-file download is a POST, not a GET — the file's detail page
   embeds a <form name="phocaDownloadForm"> whose hidden anti-abuse field NAME itself is
   a random hex string that changes every page load (not a fixed field name), so it must
   be re-parsed from a fresh GET on every download rather than cached.
2. Each month's "Resultado" spreadsheet for the LATEST available month of a given year is
   cumulative — its columns run from the prior year's December (a reference column) through
   every month of the current year published so far, not just that one month. This fetcher
   therefore only ever downloads the one, most-recent-month file per year (not all 12), and
   extracts every month column from it — one file buys a whole year's series, same trick as
   the Tunisia INS fetcher (ins_ipc.py) in the MENAAP shard.

Division labels carry their own COICOP-1999-style 2-digit code as a literal prefix
("01 - Produtos Alimentares...", "02 - Bebidas Alcoolicas...", ... "12 - Bens e Serviços
Diversos") — 12 divisions, no division 13, matching the same pre-2018-revision scheme used
by Jordan's DOS CPI and Tunisia's INS CPI fetchers already in this repo. The code is parsed
directly off the label rather than hand-mapped, so coicop_classification is still
publisher_labeled (INE's own numbering, not this fetcher's judgement).

Base period is 2014=100 (printed on every sheet as "BASE (2014=100)"). Headline "IPC
GERAL" / "IPC Geral" rows are dropped — no sanctioned all-items COICOP sentinel (same
open design question noted in the skill for SingStat's headline series).

Month columns are identified by matching the header row against Portuguese month names
(tolerating the source's own typos: "Feveiro" for "Fevereiro", "Marco" for "Março"), not
by trying to parse the merged/irregular "ANO <year>" super-header cells, which are not
laid out consistently between sample files (sometimes "ANO 2026" is one merged cell,
sometimes "ANO" and "2025" land in two separate adjacent cells). The one prior-year
comparison column (December) that precedes the first "Janeiro" in a cumulative sheet is
dropped instead of parsed, since that observation is already emitted by the prior year's
own fetch pass.

analytical_role: cpi_benchmark -> IndexObservation, not PriceObservation.
coicop_classification: publisher_labeled.
coicop_divisions: 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from datetime import date
from urllib.parse import urljoin

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Sao Tome and Principe"
_SOURCE_KEY = "stp_ine_ipc"
_IDENT = ["source_key", "observation_date", "coicop_code"]
_BASE_PERIOD = "2014=100"
_BASE_URL = "https://ine.st"
_YEAR_LIST_URL = f"{_BASE_URL}/index.php/component/phocadownload/category/78-ipc-ano"
_MIN_YEAR = 2018

_MONTH_MAP = {
    "janeiro": 1,
    "fevereiro": 2,
    "feveiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", "", s).lower()


def _match_month(header_cell: str) -> int | None:
    """Match a header cell to a month number, tolerating abbreviations.

    End-of-year cumulative sheets (many month columns) abbreviate headers to fit
    ("Jan.", "Setemb.", "Deze.") instead of spelling the month out. Every abbreviation
    observed so far is a plain prefix (>=3 letters) of the full lowercase, unaccented
    name, and the 12 canonical names have distinct 3-letter prefixes, so a prefix match
    is unambiguous.
    """
    token = re.sub(r"[^a-z]", "", _norm(header_cell))
    if len(token) < 3:
        return None
    for name, num in _MONTH_MAP.items():
        if name.startswith(token):
            return num
    return None


def _get_year_categories(session) -> dict[int, str]:
    """{year: category href} for every 'ano-YYYY'-slugged subcategory."""
    r = session.get(_YEAR_LIST_URL, timeout=30)
    r.raise_for_status()
    out: dict[int, str] = {}
    for href, _label, _count in re.findall(
        r'<div class="pd-subcategory"><a href="([^"]+)">([^<]+)</a>\s*<small>\((\d+)\)</small></div>',
        r.text,
    ):
        m = re.search(r"ano-(\d{4})$", href)
        if m:
            out[int(m.group(1))] = href
    return out


def _get_month_categories(session, year_href: str) -> list[tuple[str, str, int]]:
    """[(category href, label, file count)].

    NOT reliably in Jan..Dec document order -- some years (2022, 2023 confirmed live)
    list subcategories in creation-id order, which desyncs from calendar order (e.g.
    2022 lists "...outubro, dezembro, novembro" and 2023 is fully scrambled). Callers
    must resolve the calendar month from the label text (see `_match_month`), never
    from position in this list.
    """
    r = session.get(urljoin(_BASE_URL, year_href), timeout=30)
    r.raise_for_status()
    return [
        (href, label, int(count))
        for href, label, count in re.findall(
            r'<div class="pd-subcategory"><a href="([^"]+)">([^<]+)</a>\s*<small>\((\d+)\)</small></div>',
            r.text,
        )
    ]


def _get_files(session, month_href: str) -> list[tuple[str, str]]:
    """[(file detail href, filename)] for a month category page."""
    r = session.get(urljoin(_BASE_URL, month_href), timeout=30)
    r.raise_for_status()
    return [
        (href, filename)
        for _title, href, filename in re.findall(
            r'<div class="pd-title">([^<]+)</div><div class="pd-filename">'
            r'<div class="pd-document\d+"[^>]*><div class="pd-float">'
            r'<a class="" href="([^"]+)"\s*>([^<]+)</a>',
            r.text,
        )
    ]


def _download_pd_file(session, file_href: str) -> bytes | None:
    """Phoca Download is a POST whose hidden token field NAME changes per page load."""
    url = urljoin(_BASE_URL, file_href)
    g = session.get(url, timeout=30)
    g.raise_for_status()
    m = re.search(
        r'<form action="[^"]*" method="post" name="phocaDownloadForm"[^>]*>(.*?)</form>',
        g.text,
        re.S,
    )
    if not m:
        logger.warning("[%s] no download form found at %s", _SOURCE_KEY, url)
        return None
    data = dict(
        re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', m.group(1))
    )
    p = session.post(url, data=data, headers={"Referer": url}, timeout=30)
    p.raise_for_status()
    if "html" in (p.headers.get("content-type") or "").lower():
        logger.warning(
            "[%s] download POST returned HTML, not a file: %s", _SOURCE_KEY, url
        )
        return None
    return p.content


def _pick_resultado_file(files: list[tuple[str, str]]) -> tuple[str, str] | None:
    candidates = [
        (href, name)
        for href, name in files
        if "resultado" in _norm(name) and "publicacao2" not in _norm(name)
    ]
    return candidates[0] if candidates else None


def _rows_from_xlsx(content: bytes, year: int, url: str, cutoff: date) -> list[dict]:
    try:
        df = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] could not parse spreadsheet %s: %s", _SOURCE_KEY, url, exc)
        return []

    hdr_row = hdr_col = None
    for r in range(len(df)):
        for c in range(df.shape[1]):
            v = df.iat[r, c]
            if isinstance(v, str) and _norm(v) == "gruposdeprodutos":
                hdr_row, hdr_col = r, c
                break
        if hdr_row is not None:
            break
    if hdr_row is None:
        logger.warning("[%s] header row not found in %s", _SOURCE_KEY, url)
        return []

    month_cols: list[tuple[int, int]] = []
    for c in range(hdr_col + 1, df.shape[1]):
        v = df.iat[hdr_row, c]
        if isinstance(v, str):
            month_num = _match_month(v)
            if month_num is not None:
                month_cols.append((c, month_num))

    jan_positions = [i for i, (_c, mnum) in enumerate(month_cols) if mnum == 1]
    if jan_positions:
        month_cols = month_cols[jan_positions[0] :]

    ts_scrape = get_scrape_ts()
    out: list[dict] = []
    for r in range(hdr_row + 1, len(df)):
        label = df.iat[r, hdr_col]
        if not isinstance(label, str):
            continue
        m = re.match(r"^\s*(\d{2})\s*-", label.strip())
        if not m:
            continue
        code = m.group(1)
        if not (1 <= int(code) <= 12):
            continue
        for c, month_num in month_cols:
            val = df.iat[r, c]
            if pd.isna(val):
                continue
            try:
                index_value = float(val)
            except (TypeError, ValueError):
                continue
            obs_date = date(year, month_num, 1)
            if obs_date <= cutoff:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": code,
                "index_value": round(index_value, 4),
                "index_base_period": _BASE_PERIOD,
                "source_url": url,
                "notes": f"category={label.strip()}",
                "scrape_ts": ts_scrape,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            out.append(row)
    return out


def fetch_stp_ine_ipc(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        year_cats = _get_year_categories(session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] could not list year categories: %s", _SOURCE_KEY, exc)
        return None

    today = date.today()
    start_year = max(_MIN_YEAR, cutoff.year - 1)
    all_rows: list[dict] = []
    for year in range(start_year, today.year + 1):
        year_href = year_cats.get(year)
        if not year_href:
            continue
        try:
            month_cats = _get_month_categories(session, year_href)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] year %d month listing failed: %s", _SOURCE_KEY, year, exc
            )
            continue
        best: tuple[int, str] | None = None  # (month_num, href) — max month_num wins
        for href, label, count in month_cats:
            if count <= 0:
                continue
            month_num = _match_month(label)
            if month_num is None:
                continue
            if best is None or month_num > best[0]:
                best = (month_num, href)
        if not best:
            continue
        target_month_href = best[1]
        try:
            files = _get_files(session, target_month_href)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] year %d file listing failed: %s", _SOURCE_KEY, year, exc
            )
            continue
        picked = _pick_resultado_file(files)
        if not picked:
            logger.warning(
                "[%s] no Resultado file found for year %d", _SOURCE_KEY, year
            )
            continue
        file_href, _filename = picked
        content = _download_pd_file(session, file_href)
        if not content:
            continue
        file_url = urljoin(_BASE_URL, file_href)
        all_rows.extend(_rows_from_xlsx(content, year, file_url, cutoff))

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(all_rows), cutoff)
    return pd.DataFrame(all_rows) if all_rows else None
