"""Côte d'Ivoire DGH monthly "Prix maxima de détail des produits pétroliers".

The DGH site lists its documents through a JSON API; the monthly maximum
pump-price notes sit in the "Prix maxima à la pompe" section, one scanned PDF
(or image) per period, since September 2020. Each note is OCR'd several times
(two resolutions, grayscale and thresholded, two page-segmentation modes) and
each product price is the majority vote across those passes. A month whose
vote is unclear, that lacks super or gasoil, or that jumps more than 25 %
without the other products moving with it is logged and skipped.
"""

from __future__ import annotations

import hashlib
import logging
import re
import subprocess
import tempfile
import time
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import pandas as pd
from PIL import Image, ImageOps

from core.http import make_session

logger = logging.getLogger(__name__)

_LIST_URL = (
    "https://apisite.dgh.ci/?section=select%20data"
    "&collection=documentation&zone=zone&method=GET"
)
_OCR_CACHE_DIR = (
    Path(__file__).resolve().parents[6]
    / "data"
    / "fuel"
    / "ssa"
    / "west_africa"
    / "cote_divoire"
    / "dgh"
    / "_ocr_cache"
)
_COUNTRY = "Cote d'Ivoire"
_SOURCE_KEY = "dgh_ci_monthly"
_SEP = "\n\f=====\n"
_SUPER = "Super sans plomb"
_GASOIL = "Gasoil moteur"
_KERO = "Pétrole lampant"
_MAIN = (_SUPER, _GASOIL)
_PRODUCT_RES = {
    _SUPER: re.compile(r"s\s*u\s*p\s*e\s*r\s*s\s*a\s*n\s*s\s*p\s*l\s*o\s*m\s*b", re.I),
    _GASOIL: re.compile(r"g\s*a\s*s\s*o\s*i\s*l\s*m\s*o\s*t\s*e\s*u\s*r", re.I),
    _KERO: re.compile(
        r"p\s*[ée]\s*t\s*r\s*o\s*l\s*e\s*l\s*a\s*m\s*p\s*a\s*n\s*t", re.I
    ),
}
_UNIT_SPLIT_RE = re.compile(r"F\s*C\s*F\s*A|CFA|Litre|/", re.I)
_PRICE_MIN, _PRICE_MAX = 300, 2000
_MIN_VOTES, _MIN_SHARE = 3, 0.5
_JUMP, _COHERENT_MOVE = 0.25, 0.10
_ATTEMPTS = 3
_MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}
_MONTH_YEAR_RE = re.compile(r"(" + "|".join(_MONTHS) + r")\s*(20\d{2})")
_PERIOD_RE = re.compile(
    r"periode\s+du\s+(\d{1,2})\D{0,6}\s+au\s+\d{1,2}\s+("
    + "|".join(_MONTHS)
    + r")\s+(20\d{2})"
)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower())


def _title_date(title: str) -> date | None:
    folded = _fold(title)
    match = _MONTH_YEAR_RE.search(folded)
    if not match:
        return None
    day = re.search(r"\bdu\s+(\d{1,2})\s+au\b", folded)
    try:
        return date(
            int(match.group(2)),
            _MONTHS[match.group(1)],
            int(day.group(1)) if day else 1,
        )
    except ValueError:
        return None


def _period_start(text: str, hint: date) -> date:
    """Start day of the note's own "Période du .. au .." when it matches the title."""
    for match in _PERIOD_RE.finditer(_fold(text)):
        if (int(match.group(3)), _MONTHS[match.group(2)]) != (hint.year, hint.month):
            continue
        day = int(match.group(1))
        if 1 <= day <= 28:
            return hint.replace(day=day)
    return hint


def _list_notes(session) -> list[tuple[date, str, str]]:
    resp = session.get(_LIST_URL, timeout=60)
    resp.raise_for_status()
    data = resp.json()["data"]["data"]
    sections = {
        s["SEC_LIST"]
        for s in data.get("seclist", [])
        if "prix maxima" in _fold(s.get("LIBELLE", ""))
    }
    notes = []
    for item in data.get("fileseclist", []):
        if item.get("SEC_LIST") not in sections:
            continue
        title = item.get("LIBELLE", "")
        obs = _title_date(title)
        if obs is None:
            logger.warning("[dgh_ci] undated note skipped: %r", title)
            continue
        parts = urlsplit(item["LIEN"])
        url = urlunsplit(("https", parts.netloc, quote(parts.path), "", ""))
        notes.append((obs, title, url))
    return sorted(notes)


def _ocr(image: Image.Image, psm: int, tmp: str) -> str:
    path = Path(tmp) / "ocr.png"
    image.save(path)
    result = subprocess.run(
        ["tesseract", str(path), "-", "-l", "fra", "--psm", str(psm)],
        capture_output=True,
        text=True,
    )
    return result.stdout


def _ocr_variants(body: bytes, url: str) -> list[str]:
    texts = []
    with tempfile.TemporaryDirectory() as tmp:
        images = []
        if body.startswith(b"%PDF"):
            pdf = Path(tmp) / "note.pdf"
            pdf.write_bytes(body)
            for dpi in (300, 400):
                prefix = Path(tmp) / f"p{dpi}"
                subprocess.run(
                    ["pdftoppm", "-r", str(dpi), "-png", "-f", "1", "-l", "1"]
                    + [str(pdf), str(prefix)],
                    check=True,
                    capture_output=True,
                )
                page = next(Path(tmp).glob(f"p{dpi}*.png"))
                images.append(Image.open(page).copy())
        else:
            src = Path(tmp) / ("note" + Path(urlsplit(url).path).suffix)
            src.write_bytes(body)
            images.append(Image.open(src).copy())
        for image in images:
            gray = ImageOps.grayscale(image)
            binary = gray.point(lambda x: 255 if x > 160 else 0)
            for variant in (gray, binary):
                for psm in (3, 6):
                    texts.append(_ocr(variant, psm, tmp))
    return texts


def _download(session, url: str) -> bytes | None:
    for attempt in range(1, _ATTEMPTS + 1):
        try:
            resp = session.get(url, timeout=(30, 120))
            resp.raise_for_status()
            return resp.content
        except Exception as exc:
            logger.info(
                "[dgh_ci] download attempt %d failed: %s (%s)", attempt, url, exc
            )
            time.sleep(5 * attempt)
    return None


def _cached_texts(body: bytes, url: str) -> list[str] | None:
    digest = hashlib.sha256(body).hexdigest()[:16]
    cache = _OCR_CACHE_DIR / f"{digest}.txt"
    if cache.exists():
        return cache.read_text(encoding="utf-8").split(_SEP)
    try:
        texts = _ocr_variants(body, url)
    except Exception:
        logger.warning("[dgh_ci] OCR failed: %s", url, exc_info=True)
        return None
    _OCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(_SEP.join(texts), encoding="utf-8")
    return texts


def _candidates(text: str) -> dict[str, int]:
    found: dict[str, int] = {}
    for line in text.splitlines():
        for product, pattern in _PRODUCT_RES.items():
            match = pattern.search(line)
            if not match:
                continue
            head = _UNIT_SPLIT_RE.split(line[match.end() :], maxsplit=1)[0]
            tokens = re.findall(r"\d+", head)
            if not tokens:
                continue
            token = tokens[-1]
            if len(token) == 4 and token[0] in "01":
                token = token[1:]
            value = int(token)
            if _PRICE_MIN <= value <= _PRICE_MAX and value % 5 == 0:
                found[product] = value
    return found


def _vote(texts: list[str]) -> tuple[dict[str, int], dict[str, Counter]]:
    votes = {product: Counter() for product in _PRODUCT_RES}
    for text in texts:
        for product, value in _candidates(text).items():
            votes[product][value] += 1
    prices = {}
    for product, counter in votes.items():
        if not counter:
            continue
        value, n = counter.most_common(1)[0]
        if n >= _MIN_VOTES and n / sum(counter.values()) > _MIN_SHARE:
            prices[product] = value
    return prices, votes


def _jumps(prices: dict[str, int], prev: dict[str, int]) -> tuple[bool, list[str]]:
    """(month incoherent, products to drop) for moves > _JUMP vs the previous note.

    A big move is coherent only when both main products move >= _COHERENT_MOVE
    in the same direction as it.
    """
    moves = {p: v / prev[p] - 1 for p, v in prices.items() if p in prev}
    main = [moves[p] for p in _MAIN if p in moves]
    up = len(main) == len(_MAIN) and all(m >= _COHERENT_MOVE for m in main)
    down = len(main) == len(_MAIN) and all(m <= -_COHERENT_MOVE for m in main)
    big = [p for p, m in moves.items() if abs(m) > _JUMP]
    bad = [p for p in big if not ((moves[p] > 0 and up) or (moves[p] < 0 and down))]
    return any(p in _MAIN for p in bad), bad


def _accept(
    obs: date, prices: dict[str, int], votes: dict, prev: dict[str, int], url: str
) -> dict[str, int] | None:
    missing = [p for p in _MAIN if p not in prices]
    if missing:
        logger.warning(
            "[dgh_ci] %s dropped: no clear OCR vote for %s (votes %s) %s",
            obs,
            missing,
            {p: dict(votes[p]) for p in missing},
            url,
        )
        return None
    incoherent, bad = _jumps(prices, prev)
    if incoherent:
        logger.warning(
            "[dgh_ci] %s dropped: incoherent jump %s vs previous %s %s",
            obs,
            prices,
            prev,
            url,
        )
        return None
    for product in bad:
        logger.warning(
            "[dgh_ci] %s %s dropped: jump %s -> %s",
            obs,
            product,
            prev[product],
            prices[product],
        )
        prices.pop(product)
    if _KERO not in prices:
        logger.info("[dgh_ci] %s: no clear vote for %s", obs, _KERO)
    return prices


def _row(obs: date, product: str, price: int) -> dict:
    return {
        "observation_date": obs.isoformat(),
        "country": _COUNTRY,
        "fuel_product": product,
        "price_local": float(price),
        "currency": "XOF",
        "unit": "L",
        "source_key": _SOURCE_KEY,
        "city": None,
        "station_type": "national",
    }


def fetch_dgh_ci(cutoff: date) -> pd.DataFrame | None:
    session = make_session()
    try:
        notes = _list_notes(session)
    except Exception:
        logger.warning("[dgh_ci] listing failed: %s", _LIST_URL, exc_info=True)
        return None
    anchor = [n for n in notes if n[0] <= cutoff][-1:]
    todo = anchor + [n for n in notes if n[0] > cutoff]
    if not any(n[0] > cutoff for n in todo):
        logger.info("[dgh_ci] no notes after cutoff %s", cutoff)
        return None
    bodies = []
    for note in todo:
        body = _download(session, note[2])
        if body is None:
            logger.warning("[dgh_ci] download failed, stopping before %s", note[2])
            break
        bodies.append((note, body))
    with ThreadPoolExecutor(max_workers=4) as pool:
        all_texts = list(pool.map(lambda nb: _cached_texts(nb[1], nb[0][2]), bodies))

    rows: list[dict] = []
    prev: dict[str, int] = {}
    for ((hint, title, url), _), texts in zip(bodies, all_texts):
        if texts is None:
            break
        obs = _period_start("\n".join(texts), hint)
        prices, votes = _vote(texts)
        accepted = _accept(obs, prices, votes, prev, url)
        if accepted is None:
            continue
        prev.update(accepted)
        if obs <= cutoff:
            continue
        rows.extend(_row(obs, p, v) for p, v in accepted.items())
        logger.info("[dgh_ci] %s %s -> %s", obs, title, accepted)

    if not rows:
        logger.info("[dgh_ci] no rows after cutoff %s", cutoff)
        return None
    return (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"], keep="last")
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )


__all__ = ["fetch_dgh_ci"]
