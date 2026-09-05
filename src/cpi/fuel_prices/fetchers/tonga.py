"""Tonga MTED monthly petroleum price notices (PDF + OCR).

MTED posts monthly petroleum price notices as PDFs embedded in WordPress posts.
The PDFs are image-based; we render the page and OCR via Tesseract.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from datetime import date, timedelta
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd

from ..utils import MONTH_MAP_EN, get_session, make_hash, make_template


SOURCE_META = [
    {
        "fetcher_fn": "fetch_to_mted_petroleum_prices",
        "country": "Tonga",
        "source_name": "Tonga Ministry of Trade and Economic Development (MTED)",
        "url": "https://www.mted.gov.to/",
        "description": "Monthly maximum petroleum retail prices (PMS petrol, DPK kerosene, ADO diesel) published by MTED as embedded PDFs.",
        "extraction_method": ["Web scraping", "PDF (image)", "OCR"],
        "products": ["Petrol", "Diesel", "Kerosene"],
        "source_keys": ["to_mted_petroleum_prices_monthly"],
        "publishes_on": "Monthly",
        "notes": "Requires Tesseract OCR (/opt/homebrew/bin/tesseract or PATH). Uses WordPress REST API to locate posts, extracts embedded PDF URLs, renders first page, OCRs table, and parses max retail prices (typically reported in seniti per litre; stored as TOP/L).",
    }
]


_WP_API = "https://www.mted.gov.to/wp-json/wp/v2/posts"
_TMPL_TO = make_template(
    country="Tonga",
    wb_iso3="TON",
    source_key="to_mted_petroleum_prices_monthly",
    source_name="Tonga MTED Petroleum Price Notices",
    source_url="https://www.mted.gov.to/",
    source_type="official",
    currency="TOP",
    unit="L",
    subnational_area=None,
    publication_frequency="monthly",
    observation_method="reported",
)

_TESSERACT_BIN = "/opt/homebrew/bin/tesseract"
if not Path(_TESSERACT_BIN).exists():
    _TESSERACT_BIN = shutil.which("tesseract") or _TESSERACT_BIN


_TITLE_MONTH_YEAR_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b\s+(\d{4})",
    re.IGNORECASE,
)

_NUM_RE = re.compile(r"\b\d{2,3}\.\d{1,2}\b")

# Prose markers found in MTED press-release narrative (page 1 of multi-page
# notices). Lines containing any of these must NEVER be treated as a price-table
# row, even if they happen to mention an area name like "Tongatapu".
_PROSE_RE = re.compile(
    r"\b(increase|seniti/litre|wholesale|retail prices|equivalent to)\b|%",
    re.IGNORECASE,
)

# Table-row anchors used by MTED notifications.
#   - "PRICES FOR <AREA>"          (English notices; OCR sometimes drops the
#                                    space and yields "PRICESFOR")
#   - "TOTONGI 'A <AREA>"          (Tongan notices — various apostrophe forms)
_ROW_ANCHOR_RE = re.compile(
    # Trailing boundary on "FOR" omitted on purpose — OCR collapses spaces and
    # produces tokens like "PRICESFORVAVA'U".
    r"\bPRICES\s*FOR|\bTOTONGI\b",
    re.IGNORECASE,
)

_AREAS: list[tuple[str, re.Pattern]] = [
    ("Tongatapu", re.compile(r"\bTONGATAPU\b", re.IGNORECASE)),
    ("Eua", re.compile(r"\b(?:'|\u2018|\u2019)?EUA\b", re.IGNORECASE)),
    ("Ha'apai", re.compile(r"\bHA(?:'|\u2018|\u2019)?APAI\b", re.IGNORECASE)),
    ("Vava'u", re.compile(r"\bVAVA(?:'|\u2018|\u2019)?U\b", re.IGNORECASE)),
    ("Niuatoputapu", re.compile(r"\bNIUATOPUTAPU\b", re.IGNORECASE)),
    ("Niuafo'ou", re.compile(r"\bNIUAFO(?:'|\u2018|\u2019)?OU\b", re.IGNORECASE)),
]


def _month_end(d: date) -> date:
    next_m = d.replace(day=28) + timedelta(days=4)
    return next_m - timedelta(days=next_m.day)


def _parse_obs_date_from_title(title: str) -> date | None:
    m = _TITLE_MONTH_YEAR_RE.search(title or "")
    if not m:
        return None
    mon = m.group(1).lower()
    year = int(m.group(2))
    month = MONTH_MAP_EN.get(mon)
    if not month:
        return None
    try:
        return date(year, month, 1)
    except ValueError:
        return None


def _extract_pdf_urls_from_html(html: str) -> list[str]:
    # 1) Embedded viewer iframes: ...admin-ajax.php?...&file=http%3A%2F%2F...pdf
    urls: list[str] = []
    for m in re.finditer(r"admin-ajax\.php\?[^\"']+", html or ""):
        frag = unescape(m.group(0))
        try:
            qs = parse_qs(urlparse("https://www.mted.gov.to/" + frag).query)
            if "file" in qs and qs["file"]:
                urls.append(unquote(qs["file"][0]))
        except Exception:
            continue

    # 2) Direct links
    for m in re.finditer(
        r"href=\"([^\"]+\.pdf)(?:\?[^\"]*)?\"", html or "", re.IGNORECASE
    ):
        urls.append(m.group(1))

    # Dedup
    out: list[str] = []
    seen: set[str] = set()
    for u in urls:
        if not u:
            continue
        if u.startswith("//"):
            u = "https:" + u
        if u.startswith("/"):
            u = "https://www.mted.gov.to" + u
        if not u.lower().endswith(".pdf"):
            continue
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _pick_petroleum_notice_pdf(pdf_urls: list[str]) -> str | None:
    """Pick the PDF most likely to contain the price tables.

    MTED posts often attach BOTH a narrative press release AND a separate
    notification PDF that carries the actual "PRICES FOR <AREA>" tables.
    Strongly prefer the notification and exclude press releases when any
    other candidate exists.
    """
    if not pdf_urls:
        return None

    pool = [u for u in pdf_urls if "press-release" not in u.lower()]
    if not pool:
        pool = pdf_urls

    preferred = [
        "notification-petroleum-prices",
        "notification-petroleum",
        "notification",  # e.g. "Notification-New-April-Oil-Prices-2026.pdf"
        "petroleum-price",
        "oil-price",
        "petroleum",
        "oil",
    ]
    for pref in preferred:
        for u in pool:
            if pref in u.lower():
                return u
    return pool[0]


def _ocr_pdf_all_pages(pdf_bytes: bytes, tmp_dir: Path) -> str:
    """OCR every page of the PDF and return the concatenated text.

    MTED price notices have evolved from single-page tables to multi-page
    documents that prepend a press-release narrative — the actual
    "PRICES FOR <area>" tables now live on pages 2–3. Rendering only page 1
    silently dropped the data.
    """
    try:
        import pdfplumber
    except Exception as e:
        raise RuntimeError(f"pdfplumber not available: {e}")

    tmp_dir.mkdir(exist_ok=True)
    pdf_path = tmp_dir / "to_mted_notice.pdf"
    pdf_path.write_bytes(pdf_bytes)

    parts: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages):
            img_path = tmp_dir / f"to_mted_notice_p{i}.png"
            out_stem = tmp_dir / f"to_mted_notice_p{i}_ocr"
            page.to_image(resolution=260).save(str(img_path), format="PNG")

            result = subprocess.run(
                [
                    _TESSERACT_BIN,
                    str(img_path),
                    str(out_stem),
                    "-l",
                    "eng",
                    "--psm",
                    "6",
                ],
                capture_output=True,
                timeout=45,
            )
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")[:200]
                print(f"  [to_mted] Tesseract failed on page {i + 1}: {stderr}")
                continue

            txt_path = Path(str(out_stem) + ".txt")
            if not txt_path.exists():
                continue
            page_text = txt_path.read_text(encoding="utf-8", errors="replace")
            parts.append(f"--- PAGE {i + 1} ---\n{page_text}")

    return "\n\n".join(parts)


def _parse_prices_from_ocr(ocr_text: str) -> dict[str, tuple[float, float, float]]:
    """Return {area: (petrol, kerosene, diesel)} in TOP/L."""
    if not ocr_text:
        return {}

    lines = [ln.strip() for ln in (ocr_text or "").splitlines() if ln.strip()]

    # OCR commonly splits a single table row across 2-3 lines: an anchor line
    # ("PRICES FOR <AREA> via" or "TOTONGI 'A <AREA>"), zero or more garbage
    # continuation lines, and a numeric line with the prices. Walk forward and
    # join an anchor line with subsequent lines until we hit one that contains
    # numbers (or until we hit the next anchor / a hard boundary).
    joined: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        if _ROW_ANCHOR_RE.search(ln) and not _NUM_RE.search(ln):
            buf = ln
            j = i + 1
            while j < n and j - i <= 4:
                nxt = lines[j]
                if _ROW_ANCHOR_RE.search(nxt):
                    break
                buf = buf + " " + nxt
                if _NUM_RE.search(nxt):
                    j += 1
                    break
                j += 1
            joined.append(buf)
            i = j
            continue
        joined.append(ln)
        i += 1

    results: dict[str, tuple[float, float, float]] = {}
    for ln in joined:
        # Only true table rows are anchored by an English ("PRICES FOR") or
        # Tongan ("TOTONGI") header — never prose.
        if not _ROW_ANCHOR_RE.search(ln):
            continue
        # Reject prose lines that happen to mention an area name (e.g. April
        # 2026 press-release: "Tongatapu wholesale prices ... will increase by
        # 64.04 seniti/litre, 130.23 ..., and 132.89").
        if _PROSE_RE.search(ln):
            continue
        # Normalize OCR quirks before area matching:
        #   - Reinsert spaces around "FOR" ("PRICESFORVAVA'U").
        #   - Collapse underscores/trailing punctuation to spaces so area
        #     regex word boundaries fire on the closing `U`/`I` etc.
        #   - Convert decimal commas between digits to dots ("315,00" → "315.00").
        ln_norm = re.sub(r"PRICES\s*FOR\s*", " PRICES FOR ", ln, flags=re.IGNORECASE)
        ln_norm = re.sub(r"_+", " ", ln_norm)
        ln_norm = re.sub(r"(\d),(\d)", r"\1.\2", ln_norm)

        # The notifications list village-level rows as
        #   "PRICES FOR <VILLAGE> via <MAIN_AREA>" (English) or
        #   "TOTONGI 'A <VILLAGE> MEI <MAIN_AREA>" (Tongan).
        # These must NOT be assigned to <MAIN_AREA> — their real area is the
        # village (which isn't in our 6-area schema). Match the area only in
        # the segment BEFORE any "via <X>" / "MEI <X>" route waypoint.
        row_area_segment = re.split(
            r"\b(?:via|MEI)\b", ln_norm, maxsplit=1, flags=re.IGNORECASE
        )[0]

        area_name = None
        for name, are_re in _AREAS:
            if are_re.search(row_area_segment):
                area_name = name
                break
        if not area_name:
            continue

        # First-match wins: do not let a later "PRICES FOR NIUATOPUTAPU via
        # VAVA'U" row overwrite the earlier primary row for NIUATOPUTAPU.
        if area_name in results:
            continue

        nums = [float(x) for x in _NUM_RE.findall(ln_norm.replace(",", " "))]
        # Real notification rows always have ≥4 numeric columns
        # (wholesale + 3 retail at minimum); reject anything shorter to keep
        # stray sentences from sneaking through.
        if len(nums) < 4:
            continue

        # Use the last three columns (typically max retail prices incl. tax): PMS, DPK, ADO.
        petrol_raw, ker_raw, diesel_raw = nums[-3], nums[-2], nums[-1]

        def to_top(v: float) -> float:
            # PDFs commonly report seniti per litre (e.g. 305.00); store TOP/L.
            return round(v / 100.0, 4) if v >= 20 else round(v, 4)

        petrol = to_top(petrol_raw)
        ker = to_top(ker_raw)
        diesel = to_top(diesel_raw)

        if not (0.5 <= petrol <= 10.0 and 0.5 <= diesel <= 10.0 and 0.5 <= ker <= 10.0):
            continue

        results[area_name] = (petrol, ker, diesel)
    return results


def fetch_to_mted_petroleum_prices(cutoff: date) -> pd.DataFrame:
    """Fetch Tonga MTED monthly petroleum prices via WP API + OCR."""
    print("  [to_mted] Fetching Tonga MTED petroleum notices (OCR)...")
    print(f"  [to_mted] Cutoff: {cutoff}")
    if not Path(_TESSERACT_BIN).exists():
        print(f"  [to_mted] Tesseract not found at {_TESSERACT_BIN}")
        return pd.DataFrame()

    session = get_session()

    def _wp_get(params: dict, *, max_retries: int = 3) -> dict | None:
        for attempt in range(max_retries):
            try:
                resp = session.get(_WP_API, params=params, timeout=60)
                if resp.status_code != 200:
                    return None
                return resp.json()
            except Exception as e:
                wait = 2 * (attempt + 1)
                print(f"  [to_mted] WP API request failed (attempt {attempt + 1}): {e}")
                time.sleep(wait)
        return None

    # Crawl WordPress posts that match petroleum price notices.
    per_page = 100
    page = 1
    posts: list[dict] = []
    while True:
        batch = _wp_get(
            {
                "search": "petroleum",
                "per_page": per_page,
                "page": page,
            }
        )
        if not batch:
            break
        posts.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
        if page > 20:
            break
        time.sleep(0.2)

    today = date.today()
    candidates: list[tuple[date, str, str]] = []
    for p in posts:
        title = (p.get("title") or {}).get("rendered", "")
        link = p.get("link") or ""
        if not title or "price" not in title.lower():
            continue
        obs_date = _parse_obs_date_from_title(title)
        if obs_date is None:
            continue
        eff_to = _month_end(obs_date)
        if eff_to <= cutoff:
            continue
        content = (p.get("content") or {}).get("rendered", "")
        pdfs = _extract_pdf_urls_from_html(content)
        pdf_url = _pick_petroleum_notice_pdf(pdfs)
        if not pdf_url:
            continue
        candidates.append((obs_date, link, pdf_url))

    if not candidates:
        print("  [to_mted] No new posts")
        return pd.DataFrame()

    candidates = sorted(set(candidates), key=lambda x: x[0])
    tmp_dir = Path(__file__).resolve().parent / "_to_mted_tmp"

    all_rows: list[dict] = []
    for obs_date, post_url, pdf_url in candidates:
        print(f"  [to_mted] {obs_date}: {pdf_url}")
        try:
            pdf_resp = session.get(pdf_url, timeout=60)
            pdf_resp.raise_for_status()
        except Exception as e:
            print(f"  [to_mted] PDF download failed: {e}")
            continue

        try:
            ocr_text = _ocr_pdf_all_pages(pdf_resp.content, tmp_dir)
        except Exception as e:
            print(f"  [to_mted] OCR failed: {e}")
            continue

        area_prices = _parse_prices_from_ocr(ocr_text)
        if not area_prices:
            print("  [to_mted] No prices parsed from OCR")
            continue

        eff_to = _month_end(obs_date)

        # Prices are state-controlled for the month. Forward-fill daily observations.
        fill_start = max(obs_date, cutoff + timedelta(days=1))
        fill_end = min(eff_to, today)
        if fill_end < fill_start:
            continue

        for area, (petrol, ker, diesel) in area_prices.items():
            for fam, prod, qg, val in [
                ("gasoline", "Petrol", "standard", petrol),
                ("kerosene", "Kerosene", "standard", ker),
                ("diesel", "Diesel", "standard", diesel),
            ]:
                d = fill_start
                while d <= fill_end:
                    r = _TMPL_TO.copy()
                    r.update(
                        {
                            "subnational_area": area,
                            "fuel_family": fam,
                            "fuel_product": prod,
                            "quality_group": qg,
                            "price_local": val,
                            "effective_from": str(obs_date),
                            "effective_to": str(eff_to),
                            "observation_date": str(d),
                            "source_url": post_url or pdf_url,
                            "notes": f"Parsed from MTED PDF notice ({pdf_url}).",
                        }
                    )
                    r["observation_hash"] = make_hash(r)
                    all_rows.append(r)
                    d += timedelta(days=1)

        time.sleep(0.3)

    # Always wipe the tmp workdir; pdfplumber + per-page Tesseract leave
    # PDF/PNG/TXT artifacts that the previous "rmdir if empty" guard never
    # cleaned up.
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"  [to_mted] {len(all_rows)} rows fetched (cutoff {cutoff})")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
