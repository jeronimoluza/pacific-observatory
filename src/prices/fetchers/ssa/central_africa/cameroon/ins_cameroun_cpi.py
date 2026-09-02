"""Institut National de la Statistique du Cameroun (INS) -- monthly Consumer
Price Index note ("Note mensuelle sur l'evolution des prix a la consommation
finale des menages au Cameroun").

INS publishes one PDF per month at ins-cameroun.cm. Each PDF's "Tableau 2 :
Evolution de l'Indice Harmonise des Prix a la Consommation (Base 100 annee
2022)" carries a trailing 12-month window of index levels per COICOP
division -- e.g. the May 2026 note carries Jun-2025 through May-2026 -- so a
single, most-recent PDF backfills a year of history in one fetch, mirroring
the Sierra Leone Stats SL CPI fetcher's design
(ssa/west_africa/sierra_leone/statssl_cpi.py).

Site is wide open with a realistic browser UA / curl_cffi impersonation --
confirmed live 2026-09-01, no WAF on ins-cameroun.cm itself (unlike the
Knoema/OpenDataForAfrica embed the INS homepage links to, which sits behind
a Cloudflare Turnstile challenge and was not pursued).

INS's own 12 "FONCTION DE CONSOMMATION" division rows map 1:1 onto
COICOP-2018 divisions 01-12 (division 13, insurance/financial services, is
absent from this publication -- the same gap seen in Stats SL and most
national CPI series in the region):

  Produits alimentaires et boissons non alcoolisees        -> 01
  Boissons alcoolisees, tabacs et stupefiants               -> 02
  Habillement et chaussures                                 -> 03
  Logement, eau, gaz, electricite et autres combustibles    -> 04
  Meubles, articles de menage et d'entretien courant        -> 05
  Sante                                                     -> 06
  Transports                                                -> 07
  Communications                                            -> 08
  Loisirs et culture                                        -> 09
  Enseignement                                               -> 10
  Restaurants et hotels                                      -> 11
  Biens et services divers                                  -> 12

The "INDICE GENERAL" headline row is dropped (no sanctioned sentinel COICOP
code yet for an all-items row -- see the skill's open design question).
Sub-item rows nested under division 01 (Pains et cereales, Viandes, ...) are
also dropped -- this fetcher emits division-level rows only, matching the
Stats SL precedent.

Table extraction note: pdfplumber's word order follows each visual TEXT
LINE top-to-bottom, so a division label that wraps onto two lines (e.g.
"Produits alimentaires et boissons non\\nalcoolisees") has its second word
("alcoolisees") appear AFTER the row's 15 numeric cells in reading order,
not before -- confirmed live on the Tableau 2 page. This fetcher matches on
each label's first (unique) line only, which always precedes its row's
numbers.

No currency involved (index values, not price levels).
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import pdfplumber
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_LISTING_URL = "https://ins-cameroun.cm/statistiques/"
_COUNTRY = "Cameroon"
_SOURCE_KEY = "ins_cameroun_cpi"
_BASE_PERIOD = "Base 100 annee 2022"
_IDENT = ["source_key", "observation_date", "coicop_code"]

# (coicop_code, label as it appears -- unique, unwrapped first line of the
# row in Tableau 2's word-reading-order text)
_DIVISIONS = [
    ("01", "Produits alimentaires et boissons non"),
    ("02", "Boissons alcoolisées, tabacs et stupéfiants"),
    ("03", "Habillement et chaussures"),
    ("04", "Logement, eau, gaz, électricité et autres"),
    ("05", "Meubles, articles de ménage et d’entretien"),
    ("06", "Santé"),
    ("07", "Transports"),
    ("08", "Communications"),
    ("09", "Loisirs et culture"),
    ("10", "Enseignement"),
    ("11", "Restaurants et hôtels"),
    ("12", "Biens et services divers"),
]

_LABELS_BY_CODE = {code: label for code, label in _DIVISIONS}

_MONTH_NUM_FR = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}

# e.g. ".../note-mensuelle-sur-levolution-des-prix-a-la-consommation-finale-
# des-menages-au-cameroun-en-mai-2026/"
_ARTICLE_MONTH_YEAR_RE = re.compile(
    r"en-([a-zéû]+)-(\d{4})/?$",
    re.IGNORECASE,
)

_NUM_TOKEN_RE = re.compile(r"-?\d+,\d+%?")

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _get(url: str) -> curl_requests.Response:
    return curl_requests.get(
        url, impersonate="chrome124", headers={"User-Agent": _UA}, timeout=30
    )


def _list_article_urls(html: str) -> list[str]:
    hrefs = re.findall(
        r'href="(https://ins-cameroun\.cm/statistique/note-mensuelle-sur-levolution-des-prix[^"]+)"',
        html,
        re.IGNORECASE,
    )
    return sorted(set(hrefs))


def _pick_latest_article(urls: list[str]) -> tuple[str, date] | None:
    best: tuple[str, date] | None = None
    for u in urls:
        m = _ARTICLE_MONTH_YEAR_RE.search(u)
        if not m:
            continue
        month_num = _MONTH_NUM_FR.get(m.group(1).lower())
        if month_num is None:
            continue
        year = int(m.group(2))
        d = date(year, month_num, 1)
        if best is None or d > best[1]:
            best = (u, d)
    return best


def _find_pdf_url(article_html: str) -> str | None:
    m = re.search(r'href="([^"]+\.pdf)"', article_html, re.IGNORECASE)
    return m.group(1) if m else None


def _find_table_page(pdf) -> object | None:
    for page in pdf.pages:
        text = page.extract_text() or ""
        if "Tableau 2" in text and "Indice Harmonis" in text:
            return page
    return None


def _month_sequence_ending(ref: date, n: int = 12) -> list[date]:
    months: list[date] = []
    y, m = ref.year, ref.month
    for _ in range(n):
        months.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(months))


def _extract_divisions(page) -> dict[str, list[float]]:
    words = page.extract_words()
    text = " ".join(w["text"] for w in words)
    out: dict[str, list[float]] = {}
    for code, label in _DIVISIONS:
        idx = text.find(label)
        if idx == -1:
            logger.warning("[%s] label not found in Tableau 2: %r", _SOURCE_KEY, label)
            continue
        rest = text[idx + len(label) :]
        tokens = _NUM_TOKEN_RE.findall(rest)[:15]
        if len(tokens) < 12:
            logger.warning(
                "[%s] only %d numeric tokens after label %r (need >=12)",
                _SOURCE_KEY,
                len(tokens),
                label,
            )
            continue
        index_values = [float(t.rstrip("%").replace(",", ".")) for t in tokens[:12]]
        out[code] = index_values
    return out


def fetch_ins_cameroun_cpi(cutoff: date) -> pd.DataFrame | None:
    resp = _get(_LISTING_URL)
    if resp.status_code != 200:
        logger.warning("[%s] listing fetch failed (%s)", _SOURCE_KEY, resp.status_code)
        return None

    urls = _list_article_urls(resp.text)
    if not urls:
        logger.warning(
            "[%s] no monthly-note articles found on listing page", _SOURCE_KEY
        )
        return None

    picked = _pick_latest_article(urls)
    if picked is None:
        logger.warning(
            "[%s] could not parse month/year from any article URL", _SOURCE_KEY
        )
        return None
    article_url, ref_month = picked

    art_resp = _get(article_url)
    if art_resp.status_code != 200:
        logger.warning(
            "[%s] article fetch failed (%s): %s",
            _SOURCE_KEY,
            art_resp.status_code,
            article_url,
        )
        return None

    pdf_url = _find_pdf_url(art_resp.text)
    if pdf_url is None:
        logger.warning(
            "[%s] no PDF link found on article page: %s", _SOURCE_KEY, article_url
        )
        return None

    pdf_resp = _get(pdf_url)
    if pdf_resp.status_code != 200:
        logger.warning(
            "[%s] PDF fetch failed (%s): %s", _SOURCE_KEY, pdf_resp.status_code, pdf_url
        )
        return None

    with pdfplumber.open(io.BytesIO(pdf_resp.content)) as pdf:
        table_page = _find_table_page(pdf)
        if table_page is None:
            logger.warning("[%s] Tableau 2 page not found in %s", _SOURCE_KEY, pdf_url)
            return None
        divisions = _extract_divisions(table_page)

    if not divisions:
        logger.warning("[%s] no division rows parsed from %s", _SOURCE_KEY, pdf_url)
        return None

    months = _month_sequence_ending(ref_month, n=12)

    rows: list[dict] = []
    for code, values in divisions.items():
        if len(values) != len(months):
            logger.warning(
                "[%s] division %s: %d values vs %d expected months, skipping",
                _SOURCE_KEY,
                code,
                len(values),
                len(months),
            )
            continue
        for obs_date, idx_val in zip(months, values):
            if obs_date <= cutoff:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly_avg",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": code,
                "index_value": idx_val,
                "index_base_period": _BASE_PERIOD,
                "source_url": pdf_url,
                "notes": _LABELS_BY_CODE[code],
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        return None
    return pd.DataFrame(rows)
