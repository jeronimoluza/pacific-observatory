"""China fuel price fetcher (official NDRC price-cap notices).

Source: National Development and Reform Commission (NDRC) price department news
releases titled like "国内成品油价格按机制调整" (or "不作调整"). Each notice
includes an attached image table of maximum retail prices for standard gasoline
and diesel by province/center city, in CNY per ton.

This fetcher OCRs the attached table and records a single national series per
product by taking an unweighted mean across all listed regions in the table.
"""

from __future__ import annotations

import csv
import re
import subprocess
import time
from datetime import date
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup
from bs4.element import Tag
from PIL import Image, ImageOps

from ..utils import get_session, make_hash, make_template


SOURCE_META = [
    {
        "fetcher_fn": "fetch_cn_ndrc_max_retail_prices",
        "country": "China",
        "source_name": "NDRC maximum retail prices (gasoline/diesel)",
        "url": "https://www.ndrc.gov.cn/xwdt/xwfb/",
        "description": "Official government (NDRC Price Department). Biweekly-ish notices with attached table image of max retail prices by province/center city, unit CNY/ton.",
        "extraction_method": ["Web scraping", "OCR"],
        "products": ["Gasoline (standard)", "Diesel (standard)"],
        "source_keys": ["cn_ndrc_max_retail_prices_biweekly"],
        "publishes_on": "~biweekly",
        "notes": "OCRs attached table image; computes unweighted mean across listed regions to create a national series. Keeps unit as CNY/ton per the official table.",
    }
]


_TMPL_CN = make_template(
    country="China",
    wb_iso3="CHN",
    subnational_area="National average",
    source_key="cn_ndrc_max_retail_prices_biweekly",
    source_name="China NDRC — Max Retail Prices (Gasoline/Diesel)",
    source_url="https://www.ndrc.gov.cn/xwdt/xwfb/",
    source_type="official_notice",
    currency="CNY",
    unit="ton",
    publication_frequency="biweekly",
    observation_method="reported",
    tax_status="tax_inclusive",
)


_LISTING_BASE = "https://www.ndrc.gov.cn/xwdt/xwfb/"
_NOTICE_TITLE_KWS = ("国内成品油价格按机制", "国内成品油价格调整")
_LISTING_DATE_RE = re.compile(r"\b(\d{4})/(\d{2})/(\d{2})\b")

_TMP_DIR = Path("_cn_ndrc_tmp")
_TESSERACT_BIN = "/opt/homebrew/bin/tesseract"


def _iter_listing_pages(max_pages: int = 50) -> Iterable[str]:
    """Yield listing page URLs in descending recency order."""
    yield _LISTING_BASE
    for i in range(1, max_pages):
        yield urljoin(_LISTING_BASE, f"index_{i}.html")


_PUBDATE_RE = re.compile(r"发布时间\s*[:：]\s*(\d{4})/(\d{2})/(\d{2})")


def _parse_pub_date(text: str) -> date | None:
    m = _PUBDATE_RE.search(text or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _find_table_image_url(article_url: str, soup: BeautifulSoup) -> str | None:
    # Heuristic: the table attachment is typically a W020...png under the same
    # directory as the article. Pick the first matching image.
    for img in soup.find_all("img"):
        if not isinstance(img, Tag):
            continue
        src = str(img.get("src") or "").strip()  # type: ignore[attr-defined]
        if not src:
            continue
        if "W020" in src and any(
            src.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")
        ):
            return urljoin(article_url, src)
    return None


def _preprocess_numeric_region(img: Image.Image) -> Image.Image:
    """Crop + enhance the table numeric columns for OCR."""
    img_l = img.convert("L")
    w, h = img_l.size

    # Template-based crop tuned for NDRC attachments.
    # Keep both numeric columns, exclude province names.
    x0 = int(w * 0.47)
    y0 = int(h * 0.11)
    x1 = int(w * 0.985)
    y1 = int(h * 0.90)
    x0 = max(0, min(x0, w - 1))
    y0 = max(0, min(y0, h - 1))
    x1 = max(x0 + 1, min(x1, w))
    y1 = max(y0 + 1, min(y1, h))

    region = img_l.crop((x0, y0, x1, y1))
    region = region.resize((region.size[0] * 4, region.size[1] * 4))
    region = ImageOps.autocontrast(region)

    # Binarize. The table is black-on-white; a conservative threshold works.
    def _thresh(p) -> int:
        v = int(p)
        return 0 if v < 160 else 255

    region = region.point(_thresh)
    return region


def _ocr_table_values(processed_img_path: Path) -> list[tuple[int, int]]:
    """Return list of (gasoline, diesel) values (CNY/ton) from a processed image."""
    if Path(_TESSERACT_BIN).exists():
        tesseract = _TESSERACT_BIN
    else:
        tesseract = "tesseract"

    out_base = processed_img_path.with_suffix("")
    tsv_path = out_base.with_suffix(".tsv")

    cmd = [
        tesseract,
        str(processed_img_path),
        str(out_base),
        "--psm",
        "12",
        "-l",
        "snum",
        "tsv",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0 or not tsv_path.exists():
        err = proc.stderr.decode("utf-8", "ignore")[:500].strip()
        raise RuntimeError(f"tesseract failed: {err}")

    tokens: list[dict] = []
    with tsv_path.open("r", encoding="utf-8", errors="ignore") as fh:
        rdr = csv.DictReader(fh, delimiter="\t")
        for r in rdr:
            txt = (r.get("text") or "").strip()
            if not re.fullmatch(r"\d{4,5}", txt):
                continue
            try:
                conf = float(r.get("conf") or -1)
                left = int(r.get("left") or 0)
                top = int(r.get("top") or 0)
            except Exception:
                continue
            if conf < 40:
                continue
            tokens.append({"left": left, "top": top, "conf": conf, "value": int(txt)})

    if len(tokens) < 20:
        return []

    # Split into two columns by x position. Using a min/max midpoint is more
    # stable than a median split when one column has slightly more tokens.
    left_vals = [t["left"] for t in tokens]
    mid = (min(left_vals) + max(left_vals)) / 2
    col_a = [t for t in tokens if t["left"] <= mid]
    col_b = [t for t in tokens if t["left"] > mid]
    if not col_a or not col_b:
        return []

    def collapse_rows(col: list[dict], row_tol: int = 60) -> list[tuple[int, int]]:
        # Return sorted list of (top, value) by grouping near-identical tops.
        col = sorted(col, key=lambda t: (t["top"], t["left"]))
        out: list[tuple[int, int]] = []
        cur: list[dict] = []
        last_top: int | None = None
        for t in col:
            if last_top is None or abs(t["top"] - last_top) <= row_tol:
                cur.append(t)
                last_top = (
                    t["top"] if last_top is None else int((last_top + t["top"]) / 2)
                )
                continue
            best = max(cur, key=lambda x: x["conf"])
            out.append((best["top"], best["value"]))
            cur = [t]
            last_top = t["top"]
        if cur:
            best = max(cur, key=lambda x: x["conf"])
            out.append((best["top"], best["value"]))
        return sorted(out, key=lambda x: x[0])

    rows_a = collapse_rows(col_a)
    rows_b = collapse_rows(col_b)

    # Align rows by nearest y coordinate.
    pairs: list[tuple[int, int]] = []
    used_b: set[int] = set()
    for top_a, val_a in rows_a:
        best_j = None
        best_dt = 999999
        for j, (top_b, val_b) in enumerate(rows_b):
            if j in used_b:
                continue
            dt = abs(top_a - top_b)
            if dt < best_dt:
                best_dt = dt
                best_j = j
        if best_j is None or best_dt > 120:
            continue
        used_b.add(best_j)
        val_b = rows_b[best_j][1]

        # Determine which column is gasoline vs diesel by magnitude.
        g, d = (val_a, val_b) if val_a > val_b else (val_b, val_a)
        if not (8500 <= g <= 11000 and 7000 <= d <= 10000 and d < g):
            continue
        pairs.append((g, d))

    return pairs


def fetch_cn_ndrc_max_retail_prices(cutoff: date) -> pd.DataFrame:
    """Fetch China NDRC max retail gasoline/diesel prices (national mean)."""
    print("  [cn_ndrc] Fetching NDRC max retail price notices...")
    print(f"  [cn_ndrc] Cutoff: {cutoff}")

    session = get_session()
    _TMP_DIR.mkdir(exist_ok=True)

    candidates: list[tuple[date | None, str]] = []
    seen: set[str] = set()
    for page_url in _iter_listing_pages(max_pages=60):
        try:
            r = session.get(page_url, timeout=30)
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.content, "lxml")
            page_hit_cutoff = False
            for a in soup.find_all("a", href=True):
                if not isinstance(a, Tag):
                    continue
                title = (a.get_text() or "").strip()
                if not title:
                    continue
                if any(kw in title for kw in _NOTICE_TITLE_KWS):
                    href_raw = a.get("href")
                    href = str(href_raw or "").strip()
                    if not href:
                        continue
                    full = urljoin(page_url, href)
                    if full in seen:
                        continue
                    seen.add(full)

                    # Try to read the publication date from the listing row to
                    # stop pagination early.
                    pub_hint = None
                    try:
                        li_text = a.parent.get_text(" ", strip=True) if a.parent else ""
                        m = _LISTING_DATE_RE.search(li_text)
                        if m:
                            pub_hint = date(
                                int(m.group(1)), int(m.group(2)), int(m.group(3))
                            )
                    except Exception:
                        pub_hint = None

                    if pub_hint is not None and pub_hint <= cutoff:
                        page_hit_cutoff = True
                        continue
                    candidates.append((pub_hint, full))
        except Exception:
            break
        if page_hit_cutoff:
            break
        time.sleep(0.2)

    # Prefer the listing hint for ordering; fall back to URL ordering.
    candidates = sorted(
        candidates,
        key=lambda t: (t[0] is not None, t[0] or date.min, t[1]),
        reverse=True,
    )
    candidate_links = [u for _, u in candidates]
    print(f"  [cn_ndrc] Found {len(candidate_links)} candidate notice links")
    rows: list[dict] = []

    for article_url in candidate_links:
        try:
            resp = session.get(article_url, timeout=40)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.content, "lxml")
            text = soup.get_text("\n")
            pub = _parse_pub_date(text)
            if pub is None or pub <= cutoff:
                continue

            img_url = _find_table_image_url(article_url, soup)
            if not img_url:
                continue

            img_bytes = session.get(img_url, timeout=60).content
            img_path = _TMP_DIR / f"ndrc_{pub.isoformat()}.png"
            img_path.write_bytes(img_bytes)

            # Preprocess and OCR.
            img = Image.open(img_path)
            processed = _preprocess_numeric_region(img)
            proc_path = _TMP_DIR / f"ndrc_{pub.isoformat()}_num.png"
            processed.save(proc_path)

            pairs = _ocr_table_values(proc_path)
            if not pairs:
                print(f"  [cn_ndrc] {pub}: OCR produced no usable pairs")
                continue

            gas_mean = sum(g for g, _ in pairs) / len(pairs)
            die_mean = sum(d for _, d in pairs) / len(pairs)

            note = (
                f"Unweighted mean across {len(pairs)} listed regions in NDRC attachment; "
                "unit is CNY/ton (standard gasoline/diesel)."
            )

            for fam, prod, val in (
                ("gasoline", "Gasoline (standard)", gas_mean),
                ("diesel", "Diesel (standard)", die_mean),
            ):
                r_row = _TMPL_CN.copy()
                r_row.update(
                    {
                        "fuel_family": fam,
                        "fuel_product": prod,
                        "quality_group": "regular",
                        "price_local": round(float(val), 3),
                        "observation_date": str(pub),
                        "effective_from": str(pub),
                        "source_url": article_url,
                        "notes": note,
                    }
                )
                r_row["observation_hash"] = make_hash(r_row)
                rows.append(r_row)

            print(
                f"  [cn_ndrc] {pub}: pairs={len(pairs)} gas={gas_mean:.1f} diesel={die_mean:.1f}"
            )
        except Exception as exc:
            print(f"  [cn_ndrc] Error {article_url}: {exc}")
        time.sleep(0.25)

    if not rows:
        print("  [cn_ndrc] No new rows")
        return pd.DataFrame()
    print(f"  [cn_ndrc] {len(rows)} new rows")
    return pd.DataFrame(rows)
