"""Samoa Ministry of Finance monthly fuel prices (OCR of price-table images).

Split out unchanged from legacy pacific-observatory
``src/cpi/fuel_prices/fetchers/pacific_islands.py::fetch_samoa_mof`` (dev 2d60a353).
"""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_samoa_mof",
        "country": "Samoa",
        "source_name": "Ministry of Finance Monthly Fuel Prices",
        "url": "https://www.mof.gov.ws/press-releases/march-2026-fuel-prices",
        "description": "Official government (Samoa Ministry of Finance). Monthly fuel price announcements as press releases. Prices in a small retail price table published as a JPG image on each article page.",
        "extraction_method": ["Web scraping", "OCR"],
        "products": ["Gasoline (Regular Petrol)", "Diesel", "Kerosene"],
        "source_keys": ["ws_mof_monthly_fuel_prices"],
        "publishes_on": "Monthly",
        "notes": "CRITICAL: Requires Tesseract OCR (/opt/homebrew/bin/tesseract or system PATH). Crawls 'Latest Press Releases' sidebar on the entry URL; filters links whose title matches 'MONTH YYYY Fuel Prices'. OCRs embedded JPG price table from each article. Price range WST 1.0–15.0/L. Temp files written to _ws_mof_tmp/.",
    },
]

import re
import shutil
import subprocess
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from fuel.fetchers._shared.eap.legacy import MONTH_MAP_EN, get_session, make_hash, make_template

# ── Samoa MOF ─────────────────────────────────────────────────────────────────

_TMPL_WS = make_template(
    country="Samoa",
    wb_iso3="WSM",
    source_key="ws_mof_monthly_fuel_prices",
    source_name="Samoa Ministry of Finance — Monthly Fuel Prices",
    source_url="https://www.mof.gov.ws/press-releases/march-2026-fuel-prices",
    currency="WST",
    unit="L",
    subnational_area="National",
    publication_frequency="monthly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

# (key_id, product_name, fuel_family, quality_group, octane_ron, match_pattern)
# match_pattern is a compiled regex used against the lowercased OCR line.
# Extra patterns handle common OCR misreads (e.g. "Petol" for "Petrol").
_WS_PRODUCTS = [
    # Fuzzy patterns handle common Tesseract misreads:
    #   "Petol" (missing r), "Petol" -> pet[ro]{0,2}l
    #   "Pewol" (w instead of tr), "Petal" -> pe[wt][ro]{0,2}l
    ("petrol", "Petrol", "gasoline", "regular", None, re.compile(r"pe[wt][ro]{0,2}l")),
    ("diesel", "Diesel", "diesel", "regular", None, re.compile(r"dies?el")),
    ("kerosene", "Kerosene", "kerosene", "regular", None, re.compile(r"keros[ei]ne")),
]

# Matches titles like "March 2026 Fuel Prices", "January 2025 Retail Fuel Prices"
_WS_FUEL_TITLE_RE = re.compile(
    r"(?i)\b(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+(20\d{2})\b.{0,30}\bfuel\s+prices\b"
)

# Price on a product line: "$2.99", "$2.9", or "§2.70" (OCR misreads "$" as "§").
# Must be preceded by "$" or "§" so we don't pick up narrative bare numbers.
_WS_PRICE_RE = re.compile(r"[\$§]\s*(\d+\.\d{1,2})\b")
# Fallback for OCR that merges the decimal point: "$266 per litre" means $2.66.
# Only used in table sections; match 3-digit integers 100-999 followed by \s+per.
_WS_NODECIMAL_PRICE_RE = re.compile(r"[\$§]\s*([1-9]\d{2})\s+per", re.IGNORECASE)

_WS_BASE_URL = "https://www.mof.gov.ws"
_WS_ENTRY_URL = "https://www.mof.gov.ws/press-releases/march-2026-fuel-prices"

# Tesseract binary (same detection pattern as vietnam.py)
_WS_TESSERACT_BIN = "/opt/homebrew/bin/tesseract"
if not Path(_WS_TESSERACT_BIN).exists():
    _WS_TESSERACT_BIN = shutil.which("tesseract") or _WS_TESSERACT_BIN


def _get_ws_article_urls(session) -> list[tuple[str, date]]:
    """Fetch the entry URL and return (full_url, obs_date) for all fuel-price articles found."""
    results: list[tuple[str, date]] = []
    seen: set[str] = set()

    try:
        resp = session.get(_WS_ENTRY_URL, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [ws_mof] Could not fetch entry URL: {e}")
        return results

    soup = BeautifulSoup(resp.content, "lxml")

    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        title = a.get_text(separator=" ", strip=True)
        m = _WS_FUEL_TITLE_RE.search(title)
        if not m:
            continue
        full = href if href.startswith("http") else _WS_BASE_URL + href
        if full in seen:
            continue
        seen.add(full)
        month_num = MONTH_MAP_EN[m.group(1).lower()]
        year = int(m.group(2))
        try:
            obs_date = date(year, month_num, 1)
        except ValueError:
            continue
        results.append((full, obs_date))

    return results


def _get_ws_price_image_url(session, article_url: str) -> str | None:
    """Fetch an article page and return the URL of the price-table image (JPG or PNG)."""
    try:
        resp = session.get(article_url, timeout=20)
        if resp.status_code != 200:
            return None
    except Exception as e:
        print(f"  [ws_mof] Article fetch error {article_url}: {e}")
        return None

    soup = BeautifulSoup(resp.content, "lxml")
    for img in soup.find_all("img", src=True):
        src = str(img["src"])
        # The price table images are hosted on cdn.prod.website-files.com
        # and may end in .jpg, .jpeg, or .png
        src_lower = src.lower()
        if "cdn.prod.website-files.com" in src and any(
            src_lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png")
        ):
            # Skip logos — they're in a different asset folder (67a155f272e2c5aeb2caf86f)
            # Price images are in the per-article folder (67a155f272e2c5aeb2caf892)
            if "67a155f272e2c5aeb2caf892" in src:
                if src.startswith("//"):
                    src = "https:" + src
                return src
    return None


def _parse_ws_price_image(
    img_bytes: bytes, tmp_dir: Path, img_ext: str = ".jpg"
) -> dict[str, float]:
    """OCR the price-table image (JPG or PNG); return {product_key: price}."""
    img_filename = f"ws_mof_price{img_ext}"
    ocr_stem = "ws_mof_price_ocr"
    img_path = tmp_dir / img_filename
    ocr_txt = tmp_dir / f"{ocr_stem}.txt"

    try:
        img_path.write_bytes(img_bytes)
    except Exception as e:
        print(f"  [ws_mof] Cannot write image: {e}")
        return {}

    try:
        # Use cwd=tmp_dir + relative filenames to avoid Leptonica absolute-path
        # issues on some Tesseract 5.x / macOS setups.
        result = subprocess.run(
            [_WS_TESSERACT_BIN, img_filename, ocr_stem, "-l", "eng", "--psm", "6"],
            capture_output=True,
            timeout=30,
            cwd=str(tmp_dir),
        )
        if result.returncode != 0:
            print(
                f"  [ws_mof] Tesseract error: "
                f"{result.stderr.decode('utf-8', errors='replace')[:200]}"
            )
            return {}
    except FileNotFoundError:
        print(f"  [ws_mof] Tesseract not found at {_WS_TESSERACT_BIN}")
        return {}
    except Exception as e:
        print(f"  [ws_mof] Tesseract subprocess error: {e}")
        return {}

    if not ocr_txt.exists():
        return {}

    ocr_text = ocr_txt.read_text(encoding="utf-8", errors="replace")

    # Find the price table section header — a line near the end that says
    # "Retail Prices from" / "Total Price from" / "Recall Prices from" (OCR variants).
    # Only parse lines after this header to avoid picking up narrative text.
    _WS_TABLE_START_RE = re.compile(
        r"(?i)(re[ct]a[il]{1,2}\s+prices?\s+from"
        r"|toul?\s+price\s+from"
        r"|rec[ae]ll?\s+prices?\s+from"
        r"|r[ei][lt]ail\s+prices?\s+from"
        r"|sil\s+prices?\s+from)"  # "sil" = OCR misread of "Retail"
    )
    lines = ocr_text.splitlines()
    table_start = 0
    for i, ln in enumerate(lines):
        if _WS_TABLE_START_RE.search(ln):
            table_start = i
            break
    parse_lines = lines[table_start:]

    prices: dict[str, float] = {}
    for line in parse_lines:
        line_lower = line.lower()
        # Identify which product this line belongs to (fuzzy regex for OCR misreads)
        product_key: str | None = None
        for key, _prod_name, _family, _qg, _ron, match_re in _WS_PRODUCTS:
            if match_re.search(line_lower):
                product_key = key
                break
        if product_key is None:
            continue
        # Extract the first $-prefixed price on this line.
        # Primary: "Petrol $X.XX per litre" / "Petrol $X.X per litre"
        # Fallback: "Kerosene $266 per litre" — OCR dropped the decimal; divide by 100.
        all_prices = _WS_PRICE_RE.findall(line)
        if all_prices:
            raw_price = all_prices[0]
            try:
                price = float(raw_price)
            except ValueError:
                continue
        else:
            nd = _WS_NODECIMAL_PRICE_RE.search(line)
            if not nd:
                continue
            try:
                price = int(nd.group(1)) / 100.0
            except (ValueError, IndexError):
                continue
        if not (1.0 <= price <= 15.0):
            continue
        if product_key not in prices:
            prices[product_key] = price

    try:
        img_path.unlink(missing_ok=True)
        ocr_txt.unlink(missing_ok=True)
    except Exception:
        pass

    return prices


def _ws_remove_tmp_dir(tmp_dir: Path) -> None:
    try:
        if tmp_dir.exists() and not any(tmp_dir.iterdir()):
            tmp_dir.rmdir()
    except Exception:
        pass


def fetch_samoa_mof(cutoff: date) -> pd.DataFrame:
    """Fetch Samoa Ministry of Finance monthly fuel prices via OCR of price-table images."""
    print("  [ws_mof] Fetching Samoa MOF data (OCR)...")
    print(f"  [ws_mof] Cutoff: {cutoff}")

    session = get_session()
    tmp_dir = Path(__file__).resolve().parent / "_ws_mof_tmp"
    tmp_dir.mkdir(exist_ok=True)

    all_articles = _get_ws_article_urls(session)
    print(f"  [ws_mof] Found {len(all_articles)} fuel-price articles total")

    today = date.today()

    # Samoa prices are published monthly and are state-controlled for the period.
    # Forward-fill each month's price across daily observation dates.
    # Include any month whose end date is newer than cutoff (not just obs_date).
    def month_end(d: date) -> date:
        return (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(
            days=1
        )

    new_articles = [(url, d) for url, d in all_articles if month_end(d) > cutoff]
    print(f"  [ws_mof] {len(new_articles)} articles with coverage after cutoff")

    if not new_articles:
        print("  [ws_mof] No new articles")
        _ws_remove_tmp_dir(tmp_dir)
        return pd.DataFrame()

    all_rows: list[dict] = []

    for art_url, obs_date in sorted(new_articles, key=lambda x: x[1]):
        img_url = _get_ws_price_image_url(session, art_url)
        if img_url is None:
            print(f"  [ws_mof] {obs_date}: no price image found in {art_url}")
            time.sleep(0.3)
            continue

        try:
            img_resp = session.get(img_url, timeout=30)
            img_resp.raise_for_status()
            img_bytes = img_resp.content
        except Exception as e:
            print(f"  [ws_mof] {obs_date}: image download error: {e}")
            time.sleep(0.3)
            continue

        img_ext = Path(img_url.split("?")[0]).suffix.lower() or ".jpg"
        prices = _parse_ws_price_image(img_bytes, tmp_dir, img_ext=img_ext)
        if not prices:
            print(f"  [ws_mof] {obs_date}: OCR returned no prices")
            time.sleep(0.3)
            continue

        month_end_date = month_end(obs_date)

        rows_added = 0
        for key, prod_name, family, qg, ron, _match_re in _WS_PRODUCTS:
            if key not in prices:
                continue
            price = prices[key]
            fill_start = max(obs_date, cutoff + timedelta(days=1))
            fill_end = min(month_end_date, today)
            if fill_end < fill_start:
                continue

            d = fill_start
            while d <= fill_end:
                r_row = _TMPL_WS.copy()
                r_row.update(
                    {
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": price,
                        "effective_from": str(obs_date),
                        "effective_to": str(month_end_date),
                        "observation_date": str(d),
                        "source_url": art_url,
                    }
                )
                r_row["observation_hash"] = make_hash(r_row)
                all_rows.append(r_row)
                rows_added += 1
                d += timedelta(days=1)

        print(f"  [ws_mof] {obs_date}: {rows_added} daily rows — {prices}")
        time.sleep(0.5)

    _ws_remove_tmp_dir(tmp_dir)

    if all_rows:
        print(f"  [ws_mof] Total: {len(all_rows)} new rows")
    else:
        print("  [ws_mof] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
