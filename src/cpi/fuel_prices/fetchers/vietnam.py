"""Vietnam Petrolimex retail price fetcher — OCR of price-table images."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_vn_petrolimex",
        "country": "Vietnam",
        "source_name": "Petrolimex Retail Price Announcements",
        "url": "https://www.petrolimex.com.vn/ndi/thong-cao-bao-chi.html",
        "description": "Semi-official (Petrolimex, Vietnam National Petroleum Group — state enterprise). Biweekly price adjustment press releases with price tables as JPG images, not text.",
        "extraction_method": ["Web scraping", "OCR"],
        "products": [
            "Gasoline RON 95-V (Premium)",
            "Gasoline RON 95-III (Premium)",
            "E5 RON 92-II (Biofuel)",
            "E10 RON 95-III (Biofuel)",
            "Diesel 0.001S-V (Premium)",
            "Diesel 0.05S-II (Regular)",
            "Kerosene 2-K",
            "Mazut 180cst (Fuel Oil)",
        ],
        "source_keys": ["vn_petrolimex_retail"],
        "publishes_on": "Biweekly (1st and 15th of month)",
        "notes": "CRITICAL: Requires Tesseract OCR installed (/opt/homebrew/bin/tesseract or system PATH). Scrapes paginated listing; OCRs embedded JPGs. Two price zones + national average. Temp files written to _vn_plx_tmp/. Price range VND 10,000–50,000/L.",
    },
]

import re
import shutil
import subprocess
import time
from datetime import date
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import get_session, make_hash, make_template

_TMPL_VN = make_template(
    country="Vietnam",
    wb_iso3="VNM",
    source_key="vn_petrolimex_retail",
    source_name="Petrolimex (Vietnam National Petroleum Group) Retail Price Announcements",
    source_url="https://www.petrolimex.com.vn/ndi/thong-cao-bao-chi.html",
    currency="VND",
    unit="L",
    tax_status="tax_inclusive",
    publication_frequency="biweekly",
    observation_method="reported",
)

# More-specific keys MUST come before less-specific ones.
_VN_PLX_PRODUCTS = [
    ("180cst", "Mazut 180cst-0.5S", "fuel_oil", "premium", None, "kg"),
    ("mazut", "Mazut N02B (3.5S)", "fuel_oil", "regular", None, "kg"),
    ("0,001", "Diesel 0.001S-V", "diesel", "premium", None, "L"),
    ("0,05", "Diesel 0.05S-II", "diesel", "regular", None, "L"),
    ("e10", "E10 RON 95-III", "gasoline", "biofuel", 95, "L"),
    ("e5", "E5 RON 92-II", "gasoline", "biofuel", 92, "L"),
    ("95-v", "RON 95-V", "gasoline", "premium", 95, "L"),
    ("95-iil", "RON 95-III", "gasoline", "premium", 95, "L"),
    ("95-ill", "RON 95-III", "gasoline", "premium", 95, "L"),
    ("95-ii|", "RON 95-III", "gasoline", "premium", 95, "L"),
    ("95-iii", "RON 95-III", "gasoline", "premium", 95, "L"),
    ("95-ii", "RON 95-III", "gasoline", "premium", 95, "L"),
    ("d\u1ea7u h\u1ecfa", "Kerosene 2-K", "kerosene", "regular", None, "L"),
    ("d\u1ea7u h", "Kerosene 2-K", "kerosene", "regular", None, "L"),
    ("dau hoa", "Kerosene 2-K", "kerosene", "regular", None, "L"),
    ("dau h\xe9a", "Kerosene 2-K", "kerosene", "regular", None, "L"),
    ("dau h6a", "Kerosene 2-K", "kerosene", "regular", None, "L"),
    ("dau hda", "Kerosene 2-K", "kerosene", "regular", None, "L"),
    ("kerosene", "Kerosene 2-K", "kerosene", "regular", None, "L"),
]

_VN_PLX_LISTING = "https://www.petrolimex.com.vn/ndi/thong-cao-bao-chi.html"
_VN_PLX_BASE = "https://www.petrolimex.com.vn"
_VN_PLX_SLUG_RE = re.compile(r"ngay-(\d{2})-(\d{2})-(\d{4})")
_VN_PLX_PRICE_RE = re.compile(r"\b(\d{2,3}[.,]\d{3})\b")

_TESSERACT_BIN = "/opt/homebrew/bin/tesseract"
if not Path(_TESSERACT_BIN).exists():
    _TESSERACT_BIN = shutil.which("tesseract") or _TESSERACT_BIN


def _parse_vn_date_from_slug(url: str) -> date | None:
    m = _VN_PLX_SLUG_RE.search(url)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _get_vn_plx_article_urls(
    session, cutoff: date | None = None
) -> list[tuple[str, date]]:
    """Collect all price-adjustment article URLs + effective dates from listing page(s)."""
    results: list[tuple[str, date]] = []
    seen: set[str] = set()

    total_pages = 1
    try:
        resp0 = session.get(_VN_PLX_LISTING, timeout=20)
        if resp0.status_code == 200:
            soup0 = BeautifulSoup(resp0.content, "lxml")
            pag_div = soup0.find("div", class_="pagination")
            if pag_div:
                page_nums = [
                    int(a.get_text(strip=True))
                    for a in pag_div.find_all("a", href=True)
                    if a.get_text(strip=True).isdigit()
                ]
                if page_nums:
                    total_pages = max(page_nums)
    except Exception as e:
        print(f"  [vn_plx] Could not determine total pages: {e}")

    print(f"  [vn_plx] Listing pages to crawl: {total_pages}")

    for page in range(1, total_pages + 1):
        url = (
            _VN_PLX_LISTING
            if page == 1
            else f"{_VN_PLX_BASE}/ndi/thong-cao-bao-chi/{page}.html"
        )
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                print(f"  [vn_plx] Listing page {page}: HTTP {resp.status_code}")
                break
        except Exception as e:
            print(f"  [vn_plx] Listing page {page} error: {e}")
            break

        soup = BeautifulSoup(resp.content, "lxml")
        found_this_page = 0
        oldest_on_page = None

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "petrolimex-dieu-chinh-gia-xang-dau" not in href:
                continue
            full = href if href.startswith("http") else _VN_PLX_BASE + href
            if full in seen:
                continue
            eff_date = _parse_vn_date_from_slug(href)
            if eff_date is None:
                continue
            seen.add(full)
            results.append((full, eff_date))
            found_this_page += 1
            if oldest_on_page is None or eff_date < oldest_on_page:
                oldest_on_page = eff_date

        if found_this_page == 0:
            break

        if (
            cutoff is not None
            and oldest_on_page is not None
            and oldest_on_page <= cutoff
        ):
            break

        time.sleep(0.3)

    return results


def _get_price_image_url(session, article_url: str) -> str | None:
    """Fetch article HTML and return the URL of the price-table JPG image."""
    try:
        resp = session.get(article_url, timeout=20)
        if resp.status_code != 200:
            return None
    except Exception as e:
        print(f"  [vn_plx] Article fetch error {article_url}: {e}")
        return None

    soup = BeautifulSoup(resp.content, "lxml")
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if "/jpgs/" in src and "thumbnails" not in src:
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = _VN_PLX_BASE + src
            return src
    return None


def _parse_price_table_from_image(
    img_bytes: bytes, tmp_dir: Path
) -> list[tuple[str, float, float]]:
    """OCR the price-table image; returns list of (line_lower, vung1, vung2)."""
    img_path = tmp_dir / "plx_price_img.jpg"
    ocr_out = tmp_dir / "plx_price_ocr"
    ocr_txt = tmp_dir / "plx_price_ocr.txt"

    try:
        img_path.write_bytes(img_bytes)
    except Exception as e:
        print(f"  [vn_plx] Cannot write image: {e}")
        return []

    try:
        result = subprocess.run(
            [_TESSERACT_BIN, str(img_path), str(ocr_out), "-l", "eng", "--psm", "4"],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(
                f"  [vn_plx] Tesseract error: {result.stderr.decode('utf-8', errors='replace')[:200]}"
            )
            return []
    except FileNotFoundError:
        print(f"  [vn_plx] Tesseract not found at {_TESSERACT_BIN}")
        return []
    except Exception as e:
        print(f"  [vn_plx] Tesseract subprocess error: {e}")
        return []

    if not ocr_txt.exists():
        return []

    ocr_text = ocr_txt.read_text(encoding="utf-8", errors="replace")

    rows: list[tuple[str, float, float]] = []
    for line in ocr_text.splitlines():
        line_lower = line.lower()
        prices = _VN_PLX_PRICE_RE.findall(line)
        if len(prices) < 2:
            continue
        try:
            p1 = float(prices[0].replace(".", "").replace(",", ""))
            p2 = float(prices[1].replace(".", "").replace(",", ""))
        except ValueError:
            continue
        if not (10_000 <= p1 <= 50_000) or not (10_000 <= p2 <= 50_000):
            continue
        rows.append((line_lower, p1, p2))

    try:
        img_path.unlink(missing_ok=True)
        ocr_txt.unlink(missing_ok=True)
    except Exception:
        pass

    return rows


def _match_product(line_lower: str) -> tuple | None:
    for key, prod_name, family, qg, ron, unit in _VN_PLX_PRODUCTS:
        if key in line_lower:
            return (prod_name, family, qg, ron, unit)
    return None


def _remove_tmp_dir(tmp_dir: Path) -> None:
    try:
        if tmp_dir.exists() and not any(tmp_dir.iterdir()):
            tmp_dir.rmdir()
    except Exception:
        pass


def fetch_vn_petrolimex(cutoff: date) -> pd.DataFrame:
    """Fetch Vietnam Petrolimex retail price announcements via OCR of embedded price images."""
    print("  [vn_plx] Fetching Vietnam Petrolimex price announcements...")
    print(f"  [vn_plx] Cutoff: {cutoff}")

    session = get_session()
    tmp_dir = Path(__file__).resolve().parent / "_vn_plx_tmp"
    tmp_dir.mkdir(exist_ok=True)

    all_articles = _get_vn_plx_article_urls(session, cutoff=cutoff)
    print(f"  [vn_plx] Found {len(all_articles)} price-adjustment articles total")

    new_articles = [(url, d) for url, d in all_articles if d > cutoff]
    print(f"  [vn_plx] {len(new_articles)} articles newer than cutoff")

    if not new_articles:
        print("  [vn_plx] No new articles")
        _remove_tmp_dir(tmp_dir)
        return pd.DataFrame()

    all_rows = []
    for article_url, eff_date in sorted(new_articles):
        img_url = _get_price_image_url(session, article_url)
        if img_url is None:
            print(f"  [vn_plx] {eff_date}: no price image found in {article_url}")
            time.sleep(0.3)
            continue

        try:
            img_resp = session.get(img_url, timeout=30)
            img_resp.raise_for_status()
            img_bytes = img_resp.content
        except Exception as e:
            print(f"  [vn_plx] {eff_date}: image download error: {e}")
            time.sleep(0.3)
            continue

        parsed_rows = _parse_price_table_from_image(img_bytes, tmp_dir)
        if not parsed_rows:
            print(f"  [vn_plx] {eff_date}: OCR returned no rows")
            time.sleep(0.3)
            continue

        article_row_count = 0
        for line_lower, vung1, vung2 in parsed_rows:
            matched = _match_product(line_lower)
            if matched is None:
                continue
            prod_name, family, qg, ron, unit = matched
            national_avg = round((vung1 + vung2) / 2, 2)

            for zone_label, price in [
                ("Zone 1", vung1),
                ("Zone 2", vung2),
                ("National", national_avg),
            ]:
                r = _TMPL_VN.copy()
                r.update(
                    {
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "unit": unit,
                        "subnational_area": zone_label,
                        "price_local": price,
                        "effective_from": str(eff_date),
                        "effective_to": None,
                        "observation_date": str(eff_date),
                        "source_url": article_url,
                        "notes": (
                            "Zone 1: near main supply sources (ports/refineries/depots)"
                            if zone_label == "Zone 1"
                            else "Zone 2: remote/mountainous/island areas far from supply sources"
                            if zone_label == "Zone 2"
                            else "National average: (Zone 1 + Zone 2) / 2"
                        ),
                    }
                )
                r["observation_hash"] = make_hash(r)
                all_rows.append(r)
                article_row_count += 1

        print(
            f"  [vn_plx] {eff_date}: {article_row_count} rows ({article_row_count // 3} products)"
        )
        time.sleep(0.5)

    _remove_tmp_dir(tmp_dir)

    if all_rows:
        print(f"  [vn_plx] Total: {len(all_rows)} new rows")
    else:
        print("  [vn_plx] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
