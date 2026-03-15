"""Pacific Islands fuel price fetchers — PNG, Samoa, Vanuatu, Solomon Islands."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_png_iccc",
        "country": "Papua New Guinea",
        "source_name": "ICCC Monthly Indicative Retail Prices",
        "url": "https://iccc.gov.pg/prices-regulation/#fuel-prices",
        "description": "Official government regulator (ICCC). Monthly indicative retail prices for Port Moresby published as WordPress posts with HTML tables.",
        "extraction_method": ["REST API", "HTML table parsing"],
        "products": ["Gasoline (Regular Petrol)", "Diesel", "Kerosene"],
        "source_keys": ["pg_iccc_monthly_irp"],
        "publishes_on": "Monthly",
        "notes": "Uses WP REST API to list and fetch posts. Parses HTML tables for current and previous month prices (toea converted to PGK). Port Moresby only. Price range PGK 1.0–20.0/L.",
    },
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
    {
        "fetcher_fn": "fetch_vanuatu_doe",
        "country": "Vanuatu",
        "source_name": "Department of Energy Retail Fuel Prices",
        "url": "https://doe.gov.vu/index.php/news-events/news",
        "description": "Official government (Vanuatu Dept. of Energy). Monthly retail fuel price announcements as news articles. Prices in unstructured text.",
        "extraction_method": ["Web scraping"],
        "products": ["Gasoline Unleaded 95RON (Premium)", "Diesel Low Sulphur 10PPM"],
        "source_keys": ["vu_doe_retail_petrol_diesel_2025"],
        "publishes_on": "Monthly (irregular notice)",
        "notes": "WARNING: SSL verification disabled (verify=False). Processes up to 25 candidate links. Price range VUV 100–500/L.",
    },
    {
        "fetcher_fn": "fetch_solomon_islands",
        "country": "Solomon Islands",
        "source_name": "Government Price Control Gazette",
        "url": "https://solomons.gov.sb/",
        "description": "Official government (Solomon Islands). Legally regulated price control gazette notices for petroleum and LPG as press/media releases.",
        "extraction_method": ["Web scraping"],
        "products": ["Gasoline (Petrol PMS)", "Diesel ADO", "Propane LPG"],
        "source_keys": ["sb_price_control_petroleum_2025", "sb_price_control_lpg_2025"],
        "publishes_on": "Monthly (irregular amendment)",
        "notes": "Scans government website for fuel/price keywords. Processes up to 30 candidate links. Price range SBD 5–30/L (petroleum), SBD 10–200/kg (LPG).",
    },
]

import re
import shutil
import subprocess
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from ..utils import MONTH_MAP_EN, get_session, make_hash, make_template

# ── Papua New Guinea ICCC ──────────────────────────────────────────────────────

_TMPL_PNG = make_template(
    country="Papua New Guinea",
    wb_iso3="PNG",
    source_key="pg_iccc_monthly_irp",
    source_name="Papua New Guinea ICCC Indicative Retail Fuel Prices",
    source_url="https://iccc.gov.pg/prices-regulation/#fuel-prices",
    currency="PGK",
    unit="L",
    subnational_area="Port Moresby",
    publication_frequency="monthly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_PNG_PRODUCTS = [
    ("Petrol", "gasoline", "regular", None),
    ("Diesel", "diesel", "regular", None),
    ("Kerosene", "kerosene", "regular", None),
]

_PNG_DATE_RE = re.compile(
    r"(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(20\d{2})",
    re.IGNORECASE,
)

_WP_LIST_URL = (
    "https://iccc.gov.pg/wp-json/wp/v2/posts"
    "?categories=763309980&per_page=100&orderby=date&order=desc"
    "&_fields=id,date,slug,title,link"
)


def _parse_png_table(html: str, article_link: str) -> list[dict]:
    """Parse an ICCC article HTML table and return observation rows.

    Each table has header row (product columns) then current-month and
    previous-month price rows.  Prices are in toea (÷100 → PGK).
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        return []

    tbody = table.find("tbody")
    trs = (tbody if tbody else table).find_all("tr")
    if len(trs) < 2:
        return []

    # --- header row: identify column indices for each product ---
    header_cells = trs[0].find_all(["th", "td"])
    col_map: dict[int, tuple] = {}  # col_idx → (prod_name, family, qg, ron)
    for i, cell in enumerate(header_cells):
        text = cell.get_text(separator=" ", strip=True).lower()
        for prod_name, family, qg, ron in _PNG_PRODUCTS:
            if prod_name.lower() in text:
                col_map[i] = (prod_name, family, qg, ron)
                break

    if not col_map:
        return []

    rows: list[dict] = []

    # --- data rows (row 1 = current month, row 2 = previous month) ---
    for tr in trs[1:3]:
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue

        # Parse date from the first cell text
        first_text = cells[0].get_text(separator=" ", strip=True)
        dm = _PNG_DATE_RE.search(first_text)
        if not dm:
            continue
        day = int(dm.group(1))
        month_num = MONTH_MAP_EN[dm.group(2).lower()]
        year = int(dm.group(3))
        try:
            obs_date = date(year, month_num, day)
        except ValueError:
            continue

        month_end = (obs_date.replace(day=28) + timedelta(days=4)).replace(
            day=1
        ) - timedelta(days=1)

        for col_idx, (prod_name, family, qg, ron) in col_map.items():
            if col_idx >= len(cells):
                continue
            price_text = cells[col_idx].get_text(separator=" ", strip=True)
            # Extract numeric value (may be inside <strong> tags already flattened)
            pm = re.search(r"([\d,]+(?:\.\d+)?)", price_text.replace(",", ""))
            if not pm:
                continue
            try:
                toea = float(pm.group(1))
                price = toea / 100.0  # toea → PGK
                if not (1.0 <= price <= 20.0):
                    continue
            except ValueError:
                continue

            r_row = _TMPL_PNG.copy()
            r_row.update(
                {
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "price_local": round(price, 4),
                    "effective_from": str(obs_date),
                    "effective_to": str(month_end),
                    "observation_date": str(obs_date),
                    "source_url": article_link,
                }
            )
            r_row["observation_hash"] = make_hash(r_row)
            rows.append(r_row)

    return rows


def _wp_get(session, url: str, max_retries: int = 3) -> requests.Response | None:
    """GET with retry on 429."""
    for attempt in range(max_retries):
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 3 * (attempt + 1)))
                print(f"  [png_iccc] Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            return resp
        except Exception as e:
            print(f"  [png_iccc] Request error (attempt {attempt + 1}): {e}")
            time.sleep(2)
    return None


def _wp_session() -> requests.Session:
    """Session for ICCC WP REST API — minimal headers to avoid WAF blocks."""
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        }
    )
    return s


def fetch_png_iccc(cutoff: date) -> pd.DataFrame:
    """Fetch PNG ICCC monthly indicative retail fuel prices via WP REST API."""
    print("  [png_iccc] Fetching PNG ICCC data (WP REST API)...")
    print(f"  [png_iccc] Cutoff: {cutoff}")

    session = _wp_session()

    # --- listing phase: paginate through WP posts ---
    posts: list[dict] = []
    page_num = 1
    while True:
        url = f"{_WP_LIST_URL}&page={page_num}"
        resp = _wp_get(session, url)
        if resp is None:
            print(f"  [png_iccc] Listing page {page_num} failed after retries")
            break
        if resp.status_code == 400:
            break  # past last page
        try:
            resp.raise_for_status()
        except Exception as e:
            print(f"  [png_iccc] Listing page {page_num} error: {e}")
            break

        batch = resp.json()
        if not batch:
            break
        posts.extend(batch)

        total = int(resp.headers.get("X-WP-Total", len(posts)))
        if len(posts) >= total:
            break
        page_num += 1
        time.sleep(0.5)

    print(f"  [png_iccc] Found {len(posts)} posts via WP API")
    all_rows: list[dict] = []

    # --- content phase: fetch each post and parse table ---
    for post in posts:
        post_id = post["id"]
        article_link = post.get("link", "")
        content_url = (
            f"https://iccc.gov.pg/wp-json/wp/v2/posts/{post_id}"
            f"?_fields=id,date,title,content"
        )
        r = _wp_get(session, content_url)
        if r is None or r.status_code != 200:
            time.sleep(0.5)
            continue
        try:
            data = r.json()
            html = data.get("content", {}).get("rendered", "")
            if not html:
                continue
        except Exception as e:
            print(f"  [png_iccc] Content parse error (id={post_id}): {e}")
            continue

        rows = _parse_png_table(html, article_link)
        new_rows = [
            r for r in rows if date.fromisoformat(r["observation_date"]) > cutoff
        ]
        if new_rows:
            all_rows.extend(new_rows)
            dates = {r["observation_date"] for r in new_rows}
            print(
                f"  [png_iccc] Post {post_id}: {len(new_rows)} rows ({', '.join(sorted(dates))})"
            )

        time.sleep(0.3)

    if all_rows:
        print(f"  [png_iccc] {len(all_rows)} total new rows")
    else:
        print("  [png_iccc] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


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

    new_articles = [(url, d) for url, d in all_articles if d > cutoff]
    print(f"  [ws_mof] {len(new_articles)} articles newer than cutoff")

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

        month_end = (obs_date.replace(day=28) + timedelta(days=4)).replace(
            day=1
        ) - timedelta(days=1)

        rows_added = 0
        for key, prod_name, family, qg, ron, _match_re in _WS_PRODUCTS:
            if key not in prices:
                continue
            price = prices[key]
            r_row = _TMPL_WS.copy()
            r_row.update(
                {
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "price_local": price,
                    "effective_from": str(obs_date),
                    "effective_to": str(month_end),
                    "observation_date": str(obs_date),
                    "source_url": art_url,
                }
            )
            r_row["observation_hash"] = make_hash(r_row)
            all_rows.append(r_row)
            rows_added += 1

        print(f"  [ws_mof] {obs_date}: {rows_added} products — {prices}")
        time.sleep(0.5)

    _ws_remove_tmp_dir(tmp_dir)

    if all_rows:
        print(f"  [ws_mof] Total: {len(all_rows)} new rows")
    else:
        print("  [ws_mof] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ── Vanuatu DOE ───────────────────────────────────────────────────────────────

_TMPL_VU = make_template(
    country="Vanuatu",
    wb_iso3="VUT",
    source_key="vu_doe_retail_petrol_diesel_2025",
    source_name="Vanuatu Department of Energy — Retail Fuel Prices",
    source_url="https://doe.gov.vu/index.php/news-events/news",
    currency="VUV",
    unit="L",
    subnational_area="National",
    publication_frequency="monthly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_VU_PRODUCTS = [
    (
        "Unleaded Petrol 95RON",
        "gasoline",
        "premium",
        95,
        r"(?i)(unleaded|petrol|gasoline|essence)",
    ),
    ("Low Sulphur Diesel 10PPM", "diesel", "regular", None, r"(?i)diesel|gasoil"),
]


def fetch_vanuatu_doe(cutoff: date) -> pd.DataFrame:
    """Fetch Vanuatu Department of Energy retail fuel prices."""
    print("  [vu_doe] Fetching Vanuatu DOE data...")
    print(f"  [vu_doe] Cutoff: {cutoff}")

    session = get_session()
    listing_url = "https://doe.gov.vu/index.php/news-events/news"

    try:
        resp = session.get(listing_url, timeout=30, verify=False)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [vu_doe] Could not fetch listing: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")
    article_links: list[str] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        link_text = a.get_text(strip=True).lower()
        if any(
            kw in link_text or kw in href.lower()
            for kw in ["fuel", "petrol", "diesel", "price"]
        ):
            full = href if href.startswith("http") else "https://doe.gov.vu" + href
            if full not in seen:
                seen.add(full)
                article_links.append(full)

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "doe.gov.vu" in href and "/news" in href and href not in seen:
            seen.add(href)
            article_links.append(href)
        elif href.startswith("/") and "/news" in href:
            full = "https://doe.gov.vu" + href
            if full not in seen:
                seen.add(full)
                article_links.append(full)

    print(f"  [vu_doe] Found {len(article_links)} candidate links")
    all_rows = []

    for art_url in article_links[:25]:
        try:
            r = session.get(art_url, timeout=20, verify=False)
            if r.status_code != 200:
                continue
            text = BeautifulSoup(r.content, "lxml").get_text(separator="\n")

            if not any(kw in text.lower() for kw in ["fuel", "petrol", "diesel"]):
                continue

            obs_date = None
            for month_name, month_num in MONTH_MAP_EN.items():
                if len(month_name) < 4:
                    continue
                if month_name in text.lower():
                    year_m = re.search(r"\b(20\d{2})\b", text)
                    if year_m:
                        try:
                            obs_date = date(int(year_m.group(1)), month_num, 1)
                            break
                        except ValueError:
                            pass
            if obs_date is None:
                iso_m = re.search(r"(20\d{2})[/\-](\d{2})[/\-](\d{2})", text)
                if iso_m:
                    try:
                        obs_date = date(
                            int(iso_m.group(1)),
                            int(iso_m.group(2)),
                            int(iso_m.group(3)),
                        )
                    except ValueError:
                        pass

            if obs_date is None or obs_date <= cutoff:
                continue

            rows_added = 0
            for prod_name, family, qg, ron, prod_pat in _VU_PRODUCTS:
                m = re.search(
                    rf"{prod_pat}[^\d]{{0,150}}(\d{{3,4}}(?:\.\d{{1,2}})?)",
                    text,
                    re.IGNORECASE | re.DOTALL,
                )
                if not m:
                    continue
                try:
                    price = float(m.group(1))
                    if not (100 <= price <= 500):
                        continue
                except ValueError:
                    continue

                r_row = _TMPL_VU.copy()
                r_row.update(
                    {
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": price,
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date),
                        "observation_date": str(obs_date),
                        "source_url": art_url,
                    }
                )
                r_row["observation_hash"] = make_hash(r_row)
                all_rows.append(r_row)
                rows_added += 1

            if rows_added:
                print(f"  [vu_doe] {obs_date}: {rows_added} products")
        except Exception as e:
            print(f"  [vu_doe] Error {art_url}: {e}")
        time.sleep(0.3)

    if all_rows:
        print(f"  [vu_doe] {len(all_rows)} new rows")
    else:
        print("  [vu_doe] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ── Solomon Islands ───────────────────────────────────────────────────────────

_TMPL_SB_PETROL = make_template(
    country="Solomon Islands",
    wb_iso3="SLB",
    source_key="sb_price_control_petroleum_2025",
    source_name="Solomon Islands Petroleum Price Control",
    source_url="https://solomons.gov.sb/",
    currency="SBD",
    unit="L",
    subnational_area="National",
    publication_frequency="monthly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_TMPL_SB_LPG = make_template(
    country="Solomon Islands",
    wb_iso3="SLB",
    source_key="sb_price_control_lpg_2025",
    source_name="Solomon Islands LPG Price Control",
    source_url="https://solomons.gov.sb/",
    currency="SBD",
    unit="kg",
    subnational_area="National",
    publication_frequency="monthly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_SB_SOURCES = {
    "sb_price_control_petroleum_2025": {
        "tmpl": _TMPL_SB_PETROL,
        "products": [
            ("Diesel (ADO)", "diesel", None, None, r"(?i)diesel|ado|automotive"),
            (
                "Petrol (PMS)",
                "gasoline",
                "regular",
                None,
                r"(?i)petrol|pms|motor spirit",
            ),
        ],
        "price_range": (5, 30),
    },
    "sb_price_control_lpg_2025": {
        "tmpl": _TMPL_SB_LPG,
        "products": [
            ("Propane LPG", "lpg", "regular", None, r"(?i)lpg|propane"),
        ],
        "price_range": (10, 200),
    },
}

_SB_SCAN_URLS = [
    "https://solomons.gov.sb/",
    "https://solomons.gov.sb/category/media-releases/",
    "https://solomons.gov.sb/category/press-releases/",
    "https://solomons.gov.sb/search/?q=fuel+price",
    "https://solomons.gov.sb/search/?q=price+control+petroleum",
    "https://solomons.gov.sb/search/?q=lpg+price",
]


def fetch_solomon_islands(cutoff: date) -> pd.DataFrame:
    """Fetch Solomon Islands petroleum and LPG price-control gazette notices."""
    print("  [sb] Fetching Solomon Islands data...")
    print(f"  [sb] Cutoff: {cutoff}")

    session = get_session()
    article_links: set[str] = set()

    for scan_url in _SB_SCAN_URLS:
        try:
            r = session.get(scan_url, timeout=20)
            if r.status_code != 200:
                continue
            s = BeautifulSoup(r.content, "lxml")
            for a in s.find_all("a", href=True):
                href = a["href"]
                link_text = a.get_text(strip=True).lower()
                if any(
                    kw in link_text or kw in href.lower()
                    for kw in ["fuel", "petrol", "diesel", "lpg", "price control"]
                ):
                    full = (
                        href
                        if href.startswith("http")
                        else "https://solomons.gov.sb/" + href.lstrip("/")
                    )
                    article_links.add(full)
        except Exception:
            pass
        time.sleep(0.3)

    print(f"  [sb] Found {len(article_links)} candidate links")
    all_rows: list[dict] = []

    for art_url in list(article_links)[:30]:
        try:
            r = session.get(art_url, timeout=20)
            if r.status_code != 200:
                continue
            text = BeautifulSoup(r.content, "lxml").get_text(separator="\n")

            if not any(
                kw in text.lower() for kw in ["fuel", "petrol", "diesel", "lpg"]
            ):
                continue

            is_lpg = bool(re.search(r"(?i)\blpg\b|\bpropane\b", text))
            is_petrol = bool(
                re.search(r"(?i)\bpetrol\b|\bdiesel\b|\bpms\b|\bado\b", text)
            )

            obs_date = None
            for month_name, month_num in MONTH_MAP_EN.items():
                if len(month_name) < 4:
                    continue
                if month_name in text.lower():
                    year_m = re.search(r"\b(20\d{2})\b", text)
                    if year_m:
                        try:
                            obs_date = date(int(year_m.group(1)), month_num, 1)
                            break
                        except ValueError:
                            pass
            if obs_date is None:
                iso_m = re.search(r"(20\d{2})[/\-](\d{2})[/\-](\d{2})", text)
                if iso_m:
                    try:
                        obs_date = date(
                            int(iso_m.group(1)),
                            int(iso_m.group(2)),
                            int(iso_m.group(3)),
                        )
                    except ValueError:
                        pass

            if obs_date is None or obs_date <= cutoff:
                continue

            for source_key, spec in _SB_SOURCES.items():
                if source_key == "sb_price_control_lpg_2025" and not is_lpg:
                    continue
                if source_key == "sb_price_control_petroleum_2025" and not is_petrol:
                    continue

                tmpl = spec["tmpl"]
                min_p, max_p = spec["price_range"]
                for prod_name, family, qg, ron, prod_pat in spec["products"]:
                    m = re.search(
                        rf"{prod_pat}[^\d]{{0,150}}(\d+(?:\.\d{{1,2}})?)",
                        text,
                        re.IGNORECASE | re.DOTALL,
                    )
                    if not m:
                        continue
                    try:
                        price = float(m.group(1))
                        if not (min_p <= price <= max_p):
                            continue
                    except ValueError:
                        continue

                    r_row = tmpl.copy()
                    r_row.update(
                        {
                            "fuel_family": family,
                            "fuel_product": prod_name,
                            "quality_group": qg,
                            "octane_ron": ron,
                            "price_local": price,
                            "effective_from": str(obs_date),
                            "effective_to": str(obs_date),
                            "observation_date": str(obs_date),
                            "source_url": art_url,
                        }
                    )
                    r_row["observation_hash"] = make_hash(r_row)
                    all_rows.append(r_row)

        except Exception as e:
            print(f"  [sb] Error {art_url}: {e}")
        time.sleep(0.2)

    for source_key in _SB_SOURCES:
        count = sum(1 for r in all_rows if r.get("source_key") == source_key)
        print(f"  [sb] {source_key}: {count} new rows")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
