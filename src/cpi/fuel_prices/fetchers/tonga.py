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
    if not pdf_urls:
        return None
    preferred = [
        "notification-petroleum-prices",
        "notification-petroleum",
        "petroleum-price",
        "petroleum",
    ]
    for pref in preferred:
        for u in pdf_urls:
            if pref in u.lower():
                return u
    return pdf_urls[0]


def _ocr_pdf_first_page(pdf_bytes: bytes, tmp_dir: Path) -> str:
    try:
        import pdfplumber
    except Exception as e:
        raise RuntimeError(f"pdfplumber not available: {e}")

    tmp_dir.mkdir(exist_ok=True)
    pdf_path = tmp_dir / "to_mted_notice.pdf"
    img_path = tmp_dir / "to_mted_notice.png"
    out_stem = tmp_dir / "to_mted_notice_ocr"
    pdf_path.write_bytes(pdf_bytes)

    with pdfplumber.open(str(pdf_path)) as pdf:
        if not pdf.pages:
            return ""
        page = pdf.pages[0]
        page.to_image(resolution=260).save(str(img_path), format="PNG")

    result = subprocess.run(
        [_TESSERACT_BIN, str(img_path), str(out_stem), "-l", "eng", "--psm", "6"],
        capture_output=True,
        timeout=45,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")[:200]
        raise RuntimeError(f"Tesseract failed: {stderr}")

    txt_path = Path(str(out_stem) + ".txt")
    if not txt_path.exists():
        return ""
    return txt_path.read_text(encoding="utf-8", errors="replace")


def _parse_prices_from_ocr(ocr_text: str) -> dict[str, tuple[float, float, float]]:
    """Return {area: (petrol, kerosene, diesel)} in TOP/L."""
    if not ocr_text:
        return {}

    lines = [ln.strip() for ln in (ocr_text or "").splitlines() if ln.strip()]
    # Join adjacent lines to mitigate OCR line breaks.
    joined: list[str] = []
    buf = ""
    for ln in lines:
        if (
            buf
            and ("PRICES FOR" in buf.upper())
            and not _NUM_RE.search(buf)
            and _NUM_RE.search(ln)
        ):
            buf = buf + " " + ln
            joined.append(buf)
            buf = ""
            continue
        if "PRICES FOR" in ln.upper() and buf:
            joined.append(buf)
            buf = ln
            continue
        if buf:
            # keep short spillovers for rows
            if _NUM_RE.search(ln) and _NUM_RE.search(buf) is None and len(buf) < 120:
                buf = buf + " " + ln
                joined.append(buf)
                buf = ""
                continue
        joined.append(ln)
    if buf:
        joined.append(buf)

    results: dict[str, tuple[float, float, float]] = {}
    for ln in joined:
        if "PRICES FOR" not in ln.upper() and "TONGATAPU" not in ln.upper():
            continue
        area_name = None
        for name, are_re in _AREAS:
            if are_re.search(ln):
                area_name = name
                break
        if not area_name:
            continue

        nums = [float(x) for x in _NUM_RE.findall(ln.replace(",", " "))]
        if len(nums) < 3:
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

    # Crawl WordPress posts that match petroleum price notices.
    per_page = 100
    page = 1
    posts: list[dict] = []
    while True:
        try:
            resp = session.get(
                _WP_API,
                params={
                    "search": "petroleum",
                    "per_page": per_page,
                    "page": page,
                },
                timeout=30,
            )
        except Exception as e:
            print(f"  [to_mted] WP API request failed: {e}")
            break

        if resp.status_code != 200:
            break
        try:
            batch = resp.json()
        except Exception:
            batch = []
        if not batch:
            break
        posts.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
        if page > 20:
            break
        time.sleep(0.2)

    candidates: list[tuple[date, str, str]] = []
    for p in posts:
        title = (p.get("title") or {}).get("rendered", "")
        link = p.get("link") or ""
        if not title or "price" not in title.lower():
            continue
        obs_date = _parse_obs_date_from_title(title)
        if obs_date is None or obs_date <= cutoff:
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
            ocr_text = _ocr_pdf_first_page(pdf_resp.content, tmp_dir)
        except Exception as e:
            print(f"  [to_mted] OCR failed: {e}")
            continue

        area_prices = _parse_prices_from_ocr(ocr_text)
        if not area_prices:
            print("  [to_mted] No prices parsed from OCR")
            continue

        eff_to = _month_end(obs_date)
        for area, (petrol, ker, diesel) in area_prices.items():
            for fam, prod, qg, val in [
                ("gasoline", "Petrol", "standard", petrol),
                ("kerosene", "Kerosene", "standard", ker),
                ("diesel", "Diesel", "standard", diesel),
            ]:
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
                        "observation_date": str(obs_date),
                        "source_url": post_url or pdf_url,
                        "notes": f"Parsed from MTED PDF notice ({pdf_url}).",
                    }
                )
                r["observation_hash"] = make_hash(r)
                all_rows.append(r)

        time.sleep(0.3)

    try:
        # keep tmp dir only if empty
        if tmp_dir.exists() and not any(tmp_dir.iterdir()):
            tmp_dir.rmdir()
    except Exception:
        pass

    print(f"  [to_mted] {len(all_rows)} rows fetched (cutoff {cutoff})")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
