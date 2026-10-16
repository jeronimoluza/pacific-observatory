"""Senegal CRSE 4-weekly petroleum price structures (scanned PDFs, OCR).

The Commission de Régulation du Secteur de l'Énergie publishes a "Structure
des prix des produits pétroliers" every four weeks, effective on a Saturday.
The PDFs are scans without a text layer; page 3 holds the TTC table whose row
12 "Prix de vente au consommateur" gives, per m3, the prices of super, essence
ordinaire, essence pirogue, pétrole lampant and gasoil.

Discovery uses the WordPress media endpoint, because many document posts have
no attachment linked by ``parent``. Titles and filenames carry wrong years
(a "28 février 2025" that is 2026, a "samedi 4 janvier 2024" that is 2025), so
the effective date is the OCR'd "A compter du" date, else the filename date,
moved to the nearest year in which it falls on a Saturday. The same structure
is uploaded several times (-1, -2, _rotated); copies are grouped by date and
must agree.

Page 3 is rendered at 300 dpi (then 200 and 400 while a product is still
unread), turned upright (four rotations tried) and deskewed. The
consumer price row is in F CFA per m3 (409 999 = 410 F CFA/L once rounded);
older structures add a per-litre row. Each product is read by independent
sources: the page OCR line, the cell cropped wide and tight and OCR'd alone,
and the per-litre row. A price is kept only when two or more sources read it,
every in-range reading agrees and it lies inside 300-2000 F CFA/L; otherwise
it is logged and dropped, leaving a gap rather than a wrong level.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

import pandas as pd

from core.http import make_session
from fuel.fetchers.ssa.west_africa.senegal.crse_ocr import (
    PRODUCTS,
    accept,
    ascii_lower,
    deskew,
    read_page,
    render_page3,
)

logger = logging.getLogger(__name__)

_MEDIA_URL = "https://www.crse.sn/wp-json/wp/v2/media"
_COUNTRY = "Senegal"
_CURRENCY = "XOF"
_SOURCE_KEY = "crse_sn_4weekly"
_THROTTLE_S = 0.5
_DPIS = (300, 200, 400)
_ROTATIONS = (0, 270, 90, 180)
_CACHE_VERSION = "v12"
_CACHE_DIR = (
    Path(__file__).resolve().parents[6]
    / "data"
    / "fuel"
    / "ssa"
    / "west_africa"
    / "senegal"
    / "crse"
    / "_ocr_cache"
)
_MONTHS = {
    "janv": 1,
    "fevr": 2,
    "mars": 3,
    "avri": 4,
    "mai": 5,
    "juin": 6,
    "juil": 7,
    "aout": 8,
    "sept": 9,
    "octo": 10,
    "oct": 10,
    "nove": 11,
    "nov": 11,
    "dece": 12,
    "dec": 12,
    "jan": 1,
    "fev": 2,
    "avr": 4,
    "sep": 9,
}
_DATE_RE = re.compile(r"(\d{1,2})\s*(?:er)?[\s\-_]*([a-z]{3,9})\.?[\s\-_]*(20\d{2})")


def _month(word: str) -> int | None:
    for n in (4, 3):
        if word[:n] in _MONTHS:
            return _MONTHS[word[:n]]
    return None


def _dates(text: str) -> list[date]:
    out = []
    for d, m, y in _DATE_RE.findall(ascii_lower(text)):
        month = _month(m)
        if month:
            try:
                out.append(date(int(y), month, int(d)))
            except ValueError:
                continue
    return out


def _saturday(d: date) -> date | None:
    """The date itself if a Saturday, else the same day-month one year off."""
    for year in (d.year, d.year + 1, d.year - 1):
        try:
            cand = d.replace(year=year)
        except ValueError:
            continue
        if cand.weekday() == 5:
            return cand
    return None


def _list_pdfs(session) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        resp = session.get(
            _MEDIA_URL,
            params={"search": "structure", "per_page": 100, "page": page},
            timeout=120,
        )
        if resp.status_code == 400 and page > 1:
            break
        resp.raise_for_status()
        batch = resp.json()
        for m in batch:
            url = m.get("source_url", "")
            name = ascii_lower(unquote(urlparse(url).path.rsplit("/", 1)[-1]))
            if name.endswith(".pdf") and "structure" in name and "decret" not in name:
                items.append({"url": url, "name": name, "uploaded": m["date"][:10]})
        if len(batch) < 100:
            break
        page += 1
        time.sleep(_THROTTLE_S)
    return items


def _ocr_doc(pdf_bytes: bytes) -> dict:
    digest = hashlib.sha256(pdf_bytes).hexdigest()[:16]
    path = _CACHE_DIR / f"{digest}.{_CACHE_VERSION}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    result: dict = {"text": "", "passes": []}
    for dpi in _DPIS:
        page = render_page3(pdf_bytes, dpi)
        for angle in _ROTATIONS:
            found = read_page(
                deskew(page.rotate(angle, expand=True) if angle else page)
            )
            if found is not None:
                result["text"] += found["text"] + "\n"
                result["passes"].append({"dpi": dpi, "readings": found["readings"]})
                break
        passes = result["passes"]
        if passes and all(
            accept(r) is not None for r in passes[-1]["readings"].values()
        ):
            break
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    except OSError:
        logger.debug("[crse_sn] could not write OCR cache %s", path)
    return result


def _effective(text: str, name: str) -> date | None:
    for d in _dates(text) + _dates(re.sub(r"[-_]", " ", name)):
        if (sat := _saturday(d)) is not None:
            return sat
    return None


def _download(session, url: str) -> bytes | None:
    try:
        resp = session.get(url, timeout=(20, 180))
    except Exception:
        logger.warning("[crse_sn] download failed: %s", url)
        return None
    if resp.status_code != 200 or not resp.content.startswith(b"%PDF"):
        logger.warning("[crse_sn] HTTP %d / not a PDF: %s", resp.status_code, url)
        return None
    return resp.content


def _collect(session, cutoff: date) -> dict[date, dict[str, list[int]]]:
    """Accepted prices per effective date and product, one entry per copy."""
    by_date: dict[date, dict[str, list[int]]] = {}
    seen: set[str] = set()
    for item in sorted(_list_pdfs(session), key=lambda x: x["url"]):
        hint = _effective("", item["name"])
        if hint is not None and hint <= cutoff:
            continue
        time.sleep(_THROTTLE_S)
        pdf_bytes = _download(session, item["url"])
        if pdf_bytes is None:
            continue
        digest = hashlib.sha256(pdf_bytes).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        doc = _ocr_doc(pdf_bytes)
        eff = _effective(doc["text"], item["name"])
        if eff is None or eff > date.fromisoformat(item["uploaded"]) + timedelta(
            days=14
        ):
            logger.warning(
                "[crse_sn] no plausible effective date (%s), dropped: %s",
                eff,
                item["url"],
            )
            continue
        if not doc["passes"]:
            logger.warning(
                "[crse_sn] %s price row not found, dropped: %s", eff, item["url"]
            )
            continue
        slot = by_date.setdefault(eff, {})
        for product in PRODUCTS:
            values = [
                v
                for ps in doc["passes"]
                if (v := accept(ps["readings"][product])) is not None
            ]
            if not values:
                logger.warning(
                    "[crse_sn] %s %s dubious OCR, dropped from %s: %s",
                    eff,
                    product,
                    item["url"],
                    [ps["readings"][product] for ps in doc["passes"]],
                )
            slot.setdefault(product, []).extend(values)
    return by_date


def fetch_crse_sn(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    by_date = _collect(session, cutoff)
    rows: list[dict] = []
    for eff in sorted(d for d in by_date if d > cutoff):
        for product in PRODUCTS:
            values = by_date[eff].get(product, [])
            if not values:
                logger.warning("[crse_sn] %s %s: no clean reading, gap", eff, product)
                continue
            if any(v != values[0] for v in values[1:]):
                logger.warning(
                    "[crse_sn] %s %s copies disagree %s, dropped", eff, product, values
                )
                continue
            rows.append(
                {
                    "observation_date": eff.isoformat(),
                    "country": _COUNTRY,
                    "fuel_product": product,
                    "price_local": float(values[0]),
                    "currency": _CURRENCY,
                    "unit": "L",
                    "source_key": _SOURCE_KEY,
                    "city": None,
                    "station_type": "national",
                }
            )
    dates = sorted(by_date)
    off_grid = [(a, b) for a, b in zip(dates, dates[1:]) if (b - a).days % 7]
    if off_grid:
        logger.warning("[crse_sn] effective dates off the weekly grid: %s", off_grid)
    if not rows:
        logger.info("[crse_sn] no rows after cutoff %s", cutoff)
        return None
    df = pd.DataFrame(rows)
    logger.info(
        "[crse_sn] %d rows, %d structures (%s -> %s)",
        len(df),
        df["observation_date"].nunique(),
        df["observation_date"].min(),
        df["observation_date"].max(),
    )
    return df


__all__ = ["fetch_crse_sn"]
