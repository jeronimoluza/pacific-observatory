"""DTRH (Departamento del Trabajo y Recursos Humanos, Puerto Rico) —
Indice de Precios al Consumidor (IPC), headline all-items index.

The publication page (mercadolaboral.pr.gov/Publicaciones/Otras_Publicaciones/
Indice_Precio.aspx) is a classic ASP.NET WebForms year/month picker with
__VIEWSTATE postback, but the postback resolves to a **predictable, directly
GET-able static PDF URL** — verified live 2026-09-01 by submitting the form
once and reading the resulting redirect:

    https://www.mercadolaboral.pr.gov/lmi/pdf/IPC/<year>/Indice de Precios
    al Consumidor <month>.pdf   (month is a bare 1-12 integer, no zero-pad)

No postback simulation needed at run time — the fetcher builds this URL
directly per (year, month) and GETs it. Confirmed working back to at least
2011-01 (the earliest year offered by the page's own dropdown) through
2026-07 (latest at probe time), across a PDF layout that stayed stable
across that whole span.

Each monthly PDF's "Tabla 1 / Table 1" page states the headline All-Items
index (base December 2006=100) as the first of three index values on one
line: current month, prior month, same month prior year — e.g. for July
2026: "143.805 143.701 138.297 0.1 4.0". Only the current-month value
(first number) is emitted; the other two are the same index for months
already fetched on prior runs.

This fetcher deliberately extracts ONLY the headline all-items index, not
the ~15 group/subgroup sub-indices further into the PDF (Table 2) — that
table is a genuine two-column bilingual layout where pdfplumber's
extract_text() interleaves the Spanish and English cells unpredictably,
and getting it right is a separate, harder parsing effort not attempted
this pass.

analytical_role: cpi_benchmark -> IndexObservation rows.
coicop_classification: publisher_labeled. Per the skill's open design
question ("Headline CPI has no slot in IndexObservation"), this fetcher
uses the documented workaround: coicop_code="00" for the all-items series,
since the schema's coicop_code field is otherwise required.
"""

from __future__ import annotations

import io
import logging
import re
import urllib.parse
from datetime import date

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Puerto Rico"
_SOURCE_KEY = "pr_dtrh_ipc"
_BASE_PERIOD = "December 2006=100"
_PDF_URL_TMPL = (
    "https://www.mercadolaboral.pr.gov/lmi/pdf/IPC/{year}/"
    "Indice de Precios al Consumidor {month}.pdf"
)
_EARLIEST_YEAR = 2011

# Matches the Tabla 1 headline row: current, prior-month, prior-year index
# values followed by two percent-change figures, e.g.
# "143.805143.701138.2970.14.0" (words are joined with no separator - see
# _row_text below - since some years render one character per PDF word).
_HEADLINE_RE = re.compile(
    r"(\d{2,3}\.\d{3})\s*(\d{2,3}\.\d{3})\s*(\d{2,3}\.\d{3})\s*"
    r"(-?\d+\.\d)\s*(-?\d+\.\d)"
)

_IDENT = ["source_key", "observation_date", "coicop_code"]


def _month_url(year: int, month: int) -> str:
    path = _PDF_URL_TMPL.format(year=year, month=month)
    return urllib.parse.quote(path, safe=":/")


def _row_lines(page) -> list[str]:
    """Reconstruct visual text rows from word positions, not extract_text().

    Some publication years (2018-2023, confirmed on the 2022-06 PDF) render
    Table 1's number grid as one PDF "word" per CHARACTER with unusual
    spacing, which makes `page.extract_text()` interleave characters into
    garbage (e.g. "3 0 .1 7 2 1 2 8 .6 6 0 ..." instead of "130.172128.660
    ..."). `extract_words()` still clusters correctly by position; grouping
    those by rounded `top` and joining with no separator reconstructs the
    intended row text in both the one-word-per-character years and the
    normal one-word-per-token years (2011, 2024-2026, confirmed).
    """
    rows: dict[int, list] = {}
    for w in page.extract_words():
        rows.setdefault(round(w["top"]), []).append(w)
    lines = []
    for top in sorted(rows):
        lines.append(
            "".join(w["text"] for w in sorted(rows[top], key=lambda w: w["x0"]))
        )
    return lines


def _extract_headline(pdf_bytes: bytes) -> float | None:
    # Detect on "Todos los Grupos" / "All Items" rather than the "Tabla 1"
    # caption: the caption text box isn't always merged onto the same page
    # by pdfplumber's reading order (confirmed on the 2025-08 PDF, where
    # the Table-1 page has no "Tabla 1" text anywhere on it), while the row
    # header is present every month. The header and the number grid land on
    # different visual rows (confirmed: "TodosLosGrupos"/"AllItems" at one
    # `top`, the numbers a few rows below), so scan forward from the header
    # row rather than requiring a same-row match.
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            lines = _row_lines(page)
            anchor_idx = None
            for i, line in enumerate(lines):
                if "TodoslosGrupos" in line or "AllItems" in line:
                    anchor_idx = i
                    break
            if anchor_idx is None:
                continue
            for line in lines[anchor_idx:]:
                if "Poderadquisitivo" in line:
                    break
                m = _HEADLINE_RE.search(line)
                if m:
                    return float(m.group(1))
    return None


def fetch_pr_dtrh_ipc(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    today = date.today()
    ts = get_scrape_ts()
    rows: list[dict] = []

    year, month = today.year, today.month
    while (year, month) >= (_EARLIEST_YEAR, 1):
        obs_date = date(year, month, 1)
        if obs_date <= cutoff:
            break
        url = _month_url(year, month)
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 200 and resp.headers.get(
                "Content-Type", ""
            ).startswith("application/pdf"):
                value = _extract_headline(resp.content)
                if value is not None:
                    rec = {
                        "observation_date": obs_date.isoformat(),
                        "period_kind": "monthly_avg",
                        "country": _COUNTRY,
                        "source_key": _SOURCE_KEY,
                        "coicop_code": "00",
                        "index_value": value,
                        "index_base_period": _BASE_PERIOD,
                        "source_url": url,
                        "scrape_ts": ts,
                        "observation_hash": None,
                    }
                    rec["observation_hash"] = make_hash(rec, _IDENT)
                    rows.append(rec)
                else:
                    logger.warning(
                        "[%s] could not find headline index in %s", _SOURCE_KEY, url
                    )
            else:
                logger.warning(
                    "[%s] unexpected response for %s: %s",
                    _SOURCE_KEY,
                    url,
                    resp.status_code,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] fetch failed for %s: %s", _SOURCE_KEY, url, exc)

        month -= 1
        if month == 0:
            month = 12
            year -= 1

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
