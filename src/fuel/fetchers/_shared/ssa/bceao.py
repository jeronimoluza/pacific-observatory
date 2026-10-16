"""BCEAO statistical bulletins: end-of-month pump prices for the 8 UEMOA countries.

The BCEAO "Bulletin mensuel des statistiques" and "Bulletin trimestriel des
statistiques" carry two tables "Prix à la pompe de l'essence super / du
gazoil dans les pays de l'UEMOA (FCFA/Litre)" (section "Evolution des prix en
fin de mois des carburants"), one column per country, one row per month.

Editions are discovered through the publications listing searched for
"bulletin" (``/fr/publications?field_description_value=bulletin&page=N``); each
edition page links one PDF. PDFs and their ``pdftotext -layout`` text are
cached by sha256 under ``data/fuel/ssa/west_africa/_bceao_cache/``.

Editions overlap and sometimes disagree; for each (country, month, product)
the most recently published edition wins and every disagreement with an
older edition is logged. Cells outside 300-2000 XOF/L, rows that do not split
into one value per country, and months out of order are dropped.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import tempfile
import time
from datetime import date
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd

from core.http import make_session
from fuel.fetchers._shared.ssa.bceao_parse import (
    COUNTRIES,
    MONTHS,
    fold,
    month_end,
    parse_edition,
)

logger = logging.getLogger(__name__)

_BASE = "https://www.bceao.int"
_LIST_URL = _BASE + "/fr/publications"
_CACHE_DIR = (
    Path(__file__).resolve().parents[5]
    / "data"
    / "fuel"
    / "ssa"
    / "west_africa"
    / "_bceao_cache"
)
_INDEX = _CACHE_DIR / "editions.json"
_MAX_PAGES = 60
_ATTEMPTS = 3

_QUARTERS = {"premier": 3, "deuxieme": 6, "second": 6, "troisieme": 9, "quatrieme": 12}
_TITLE_RE = re.compile(
    r"bulletin\s+(mensuel|trimestriel)\s+d(?:e|es)\s+statistiques(?!\s+econom)"
)
_PERIOD_RE = re.compile(r"(" + "|".join(MONTHS) + r")\s+(20\d{2})")
_QUARTER_RE = re.compile(r"(" + "|".join(_QUARTERS) + r")\s+trimestre\s+(20\d{2})")
_PUB_RE = re.compile(r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(20\d{2})")
_ITEM_RE = re.compile(
    r'<a href="(/fr/publications/[^"]+)"[^>]*>\s*<span class="theme">.*?</span>'
    r'\s*<span class="desc">(.*?)</span>\s*<span class="date">(.*?)</span>',
    re.S,
)
_DOC_LINK_RE = re.compile(r'class="docLink">\s*<a href="([^"]+\.pdf)"', re.I)


def _edition_meta(desc: str, pub: str) -> dict | None:
    folded = fold(desc)
    kind = _TITLE_RE.search(folded)
    if not kind:
        return None
    period = _PERIOD_RE.search(folded)
    if period:
        ref = month_end(int(period.group(2)), MONTHS[period.group(1)])
    else:
        quarter = _QUARTER_RE.search(folded)
        if not quarter:
            logger.warning("[bceao] undated edition skipped: %r", desc)
            return None
        ref = month_end(int(quarter.group(2)), _QUARTERS[quarter.group(1)])
    published = _PUB_RE.search(fold(pub))
    pub_date = (
        date(
            int(published.group(3)),
            MONTHS[published.group(2)],
            int(published.group(1)),
        )
        if published
        else ref
    )
    tag = "BMS" if kind.group(1) == "mensuel" else "BTS"
    return {"kind": tag, "ref": ref, "published": pub_date, "desc": desc}


def _get(session, url: str, **kwargs):
    for attempt in range(1, _ATTEMPTS + 1):
        try:
            resp = session.get(url, timeout=(30, 120), **kwargs)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            logger.info("[bceao] attempt %d failed: %s (%s)", attempt, url, exc)
            time.sleep(5 * attempt)
    return None


def _list_editions(session) -> dict[str, dict]:
    editions: dict[str, dict] = {}
    for page in range(_MAX_PAGES):
        resp = _get(
            session,
            _LIST_URL,
            params={"field_description_value": "bulletin", "page": page},
        )
        if resp is None:
            raise RuntimeError(f"BCEAO listing page {page} failed")
        items = _ITEM_RE.findall(resp.text)
        if not items:
            break
        for href, desc, pub in items:
            desc = re.sub(r"<[^>]+>", "", desc).strip()
            meta = _edition_meta(desc, " ".join(pub.split()))
            if meta is not None:
                editions.setdefault(href.strip(), meta)
    return editions


def _load_index() -> dict:
    if _INDEX.exists():
        return json.loads(_INDEX.read_text(encoding="utf-8"))
    return {}


def _save_index(index: dict) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _INDEX.write_text(json.dumps(index, indent=1, sort_keys=True), encoding="utf-8")


def _edition_pdf_url(session, slug: str) -> str | None:
    """The edition page's own "Télécharger PDF" link; the site intermittently
    serves its home page instead, so retry."""
    for attempt in range(1, _ATTEMPTS + 1):
        resp = _get(session, urljoin(_BASE, slug))
        if resp is None:
            return None
        match = _DOC_LINK_RE.search(resp.text)
        if match:
            return urljoin(_BASE, match.group(1))
        time.sleep(5 * attempt)
    return None


def _pdf_text(body: bytes) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "bulletin.pdf"
        pdf.write_bytes(body)
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf), "-"],
            capture_output=True,
            check=True,
        )
    return result.stdout.decode("utf-8", errors="replace")


def _edition_text(session, slug: str, index: dict) -> str | None:
    entry = index.get(slug, {})
    digest = entry.get("sha256")
    text_path = _CACHE_DIR / "text" / f"{(digest or '')[:16]}.txt"
    if digest and text_path.exists():
        return text_path.read_text(encoding="utf-8")
    url = entry.get("pdf_url") or _edition_pdf_url(session, slug)
    if url is None:
        logger.warning("[bceao] no PDF link on %s", slug)
        return None
    resp = _get(session, url)
    if resp is None or not resp.content.startswith(b"%PDF"):
        logger.warning("[bceao] PDF download failed: %s", url)
        return None
    digest = hashlib.sha256(resp.content).hexdigest()
    pdf_path = _CACHE_DIR / "pdf" / f"{digest[:16]}.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(resp.content)
    try:
        text = _pdf_text(resp.content)
    except Exception:
        logger.warning("[bceao] pdftotext failed: %s", url, exc_info=True)
        return None
    text_path = _CACHE_DIR / "text" / f"{digest[:16]}.txt"
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(text, encoding="utf-8")
    index[slug] = {"pdf_url": url, "sha256": digest}
    _save_index(index)
    return text


@lru_cache(maxsize=1)
def bceao_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(winning cells, conflicts) across every edition, newest edition wins."""
    session = make_session()
    editions = _list_editions(session)
    index = _load_index()
    records = []
    for slug, meta in editions.items():
        text = _edition_text(session, slug, index)
        if text is None:
            continue
        label = f"{meta['kind']} {meta['ref']:%Y-%m} (pub {meta['published']})"
        for cc, obs, prod, value in parse_edition(text, label, meta["ref"]):
            records.append(
                {
                    "cc": cc,
                    "month": obs,
                    "product": prod,
                    "value": value,
                    "edition": label,
                    "_key": (meta["published"], meta["ref"], meta["kind"]),
                }
            )
    cols = ["cc", "month", "product", "value", "edition"]
    if not records:
        return pd.DataFrame(columns=cols), pd.DataFrame()
    df = pd.DataFrame(records).sort_values("_key", ascending=False, kind="stable")
    latest = df.drop_duplicates(["cc", "month", "product"], keep="first")
    merged = df.merge(
        latest[["cc", "month", "product", "value", "edition"]],
        on=["cc", "month", "product"],
        suffixes=("_other", "_latest"),
    )
    conflicts = merged[merged["value_other"] != merged["value_latest"]]
    conflicts = conflicts[
        ["cc", "month", "product", "value_latest", "edition_latest"]
        + ["value_other", "edition_other"]
    ].reset_index(drop=True)
    return latest[cols].reset_index(drop=True), conflicts


def _scrape_country(cc: str, meta: dict, cutoff: date) -> pd.DataFrame | None:
    latest, conflicts = bceao_panel()
    for row in conflicts[conflicts["cc"] == cc].itertuples(index=False):
        logger.warning(
            "[bceao_%s] conflict %s %s: %s in %s (kept) vs %s in %s",
            cc,
            row.month,
            row.product,
            row.value_latest,
            row.edition_latest,
            row.value_other,
            row.edition_other,
        )
    own = latest[(latest["cc"] == cc) & (latest["month"] > cutoff)]
    if own.empty:
        logger.info("[bceao_%s] no months after cutoff %s", cc, cutoff)
        return None
    rows = [
        {
            "observation_date": r.month.isoformat(),
            "country": meta["name"],
            "fuel_product": r.product,
            "price_local": float(r.value),
            "currency": "XOF",
            "unit": "L",
            "source_key": f"bceao_{cc}_monthly",
            "city": None,
            "station_type": "national",
        }
        for r in own.itertuples(index=False)
    ]
    return (
        pd.DataFrame(rows)
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )


def _make_fetcher(cc: str):
    meta = COUNTRIES[cc]

    def _fetch(cutoff: date) -> pd.DataFrame | None:
        return _scrape_country(cc, meta, cutoff)

    _fetch.__name__ = f"fetch_bceao_{cc}"
    _fetch.__doc__ = f"Fetch BCEAO end-of-month pump prices for {meta['name']}."
    return _fetch


fetch_bceao_bj = _make_fetcher("bj")
fetch_bceao_bf = _make_fetcher("bf")
fetch_bceao_ci = _make_fetcher("ci")
fetch_bceao_gw = _make_fetcher("gw")
fetch_bceao_ml = _make_fetcher("ml")
fetch_bceao_ne = _make_fetcher("ne")
fetch_bceao_sn = _make_fetcher("sn")
fetch_bceao_tg = _make_fetcher("tg")
