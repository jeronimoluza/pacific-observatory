"""Philippines DOE fuel price fetchers — national and Visayas regional."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_philippines_doe",
        "country": "Philippines",
        "source_name": "DOE National Retail Pump Prices",
        "url": "https://doe.gov.ph/site/vfo/articles/group/liquid-fuels",
        "description": "Official government source (Philippines Department of Energy). Publishes weekly national retail pump price reports as web articles and PDF attachments. Prices are officially monitored pump prices.",
        "extraction_method": "Web scraping + PDF parsing (pdfplumber)",
        "products": [
            "Gasoline RON 91 (Regular)",
            "Gasoline RON 95 (Premium)",
            "Diesel Plus",
            "Diesel",
        ],
        "frequency": "Weekly",
        "output": "Primary CSV",
        "notes": "Handles both HTML articles and PDF attachments; pdfplumber used for PDF content. CRITICAL: Requires pdfplumber installed. Processes up to 20 article links. Price range PHP 30–120/L.",
    },
    {
        "fetcher_fn": "fetch_philippines_doe",
        "country": "Philippines",
        "source_name": "DOE National Retail Pump Prices",
        "url": "https://doe.gov.ph/site/vfo/articles/group/liquid-fuels",
        "description": "Official government (Philippines DOE). Weekly national retail pump prices as web articles and PDF attachments.",
        "extraction_method": ["Web scraping", "PDF parsing"],
        "products": [
            "Gasoline RON 91 (Regular)",
            "Gasoline RON 95 (Premium)",
            "Diesel Plus",
            "Diesel",
        ],
        "source_keys": ["ph_doe_retail_pump_prices"],
        "publishes_on": "Tuesday",
        "notes": "Handles HTML articles and PDF attachments; pdfplumber used for PDFs. CRITICAL: Requires pdfplumber installed. Processes up to 20 article links. Price range PHP 30–120/L.",
    },
    {
        "fetcher_fn": "fetch_ph_doe_visayas",
        "country": "Philippines",
        "source_name": "DOE Visayas Regional Weekly Prices",
        "url": "https://doe.gov.ph/site/vfo/articles/group/liquid-fuels?maincat=Retail%20Pump%20Prices&subcategory=Visayas%20Pump%20Prices",
        "description": "Official government (Philippines DOE, Visayas). Weekly per-city pump price PDFs. More granular than national report.",
        "extraction_method": ["Web scraping", "PDF parsing"],
        "products": ["Gasoline RON 91/95/97/100", "Diesel Plus", "Diesel", "Kerosene"],
        "source_keys": ["ph_doe_visayas_weekly"],
        "publishes_on": "Tuesday",
        "notes": "Extracts article metadata from __NUXT__ JS payload; downloads PDFs; pdfplumber parses per-city tables. CRITICAL: Requires pdfplumber installed.",
    },
]

import io
import re
import time
from datetime import date, timedelta

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import MONTH_MAP_EN, get_session, make_hash, make_template

# ── National DOE ─────────────────────────────────────────────────────────────

_TMPL_PH_DOE = make_template(
    country="Philippines",
    wb_iso3="PHL",
    source_key="ph_doe_retail_pump_prices",
    source_name="Philippines DOE Retail Pump Prices",
    source_url="https://doe.gov.ph/site/vfo/articles/group/liquid-fuels",
    currency="PHP",
    unit="L",
    subnational_area="National",
    publication_frequency="weekly",
    observation_method="survey",
)

_PH_DOE_PRODUCTS = [
    ("RON 91", "gasoline", "regular", 91, r"(?i)ron.{0,5}91\b|91\b"),
    ("RON95", "gasoline", "premium", 95, r"(?i)ron.{0,5}95\b|95\b"),
    ("DIESEL PLUS", "diesel", "regular", None, r"(?i)diesel\s?plus|diesel\+"),
    ("Diesel", "diesel", "regular", None, r"(?i)\bdiesel\b"),
]


def fetch_philippines_doe(cutoff: date) -> pd.DataFrame:
    """Fetch Philippines DOE national retail pump prices."""
    print("  [ph_doe] Fetching Philippines DOE data...")
    print(f"  [ph_doe] Cutoff: {cutoff}")

    session = get_session()
    today = date.today()
    listing_url = (
        "https://doe.gov.ph/site/vfo/articles/group/liquid-fuels"
        "?category=Retail+Pump+Prices&display_type=Card"
    )

    try:
        resp = session.get(listing_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [ph_doe] Could not fetch listing: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")
    article_links: list[str] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(kw in href.lower() for kw in ["retail", "pump", "price"]):
            full = href if href.startswith("http") else "https://doe.gov.ph" + href
            if full not in seen:
                seen.add(full)
                article_links.append(full)

    print(f"  [ph_doe] Found {len(article_links)} article links")
    all_rows = []

    for art_url in article_links[:20]:
        try:
            r = session.get(art_url, timeout=30)
            if r.status_code != 200:
                continue

            content_type = r.headers.get("content-type", "")
            if "pdf" in content_type or art_url.lower().endswith(".pdf"):
                try:
                    import pdfplumber

                    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
                except ImportError:
                    try:
                        text = r.content.decode("latin-1", errors="replace")
                        lines = [
                            ln
                            for ln in text.splitlines()
                            if ln.isprintable() and len(ln.strip()) > 3
                        ]
                        text = "\n".join(lines)
                    except Exception:
                        continue
                except Exception as e:
                    print(f"  [ph_doe] PDF parse error {art_url}: {e}")
                    continue
            else:
                text = BeautifulSoup(r.content, "lxml").get_text(separator="\n")

            if not any(
                kw in text.lower() for kw in ["petrol", "diesel", "ron", "fuel"]
            ):
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

            if obs_date is None or obs_date <= cutoff or obs_date > today:
                continue

            rows_added = 0
            for prod_name, family, qg, ron, prod_pat in _PH_DOE_PRODUCTS:
                m = re.search(
                    rf"{prod_pat}[^\d]{{0,150}}(\d{{2,3}}(?:\.\d{{1,2}})?)",
                    text,
                    re.IGNORECASE | re.DOTALL,
                )
                if not m:
                    continue
                try:
                    price = float(m.group(1))
                    if not (30 <= price <= 120):
                        continue
                except ValueError:
                    continue

                r_row = _TMPL_PH_DOE.copy()
                r_row.update(
                    {
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": price,
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date + timedelta(days=6)),
                        "observation_date": str(obs_date),
                        "source_url": art_url,
                    }
                )
                r_row["observation_hash"] = make_hash(r_row)
                all_rows.append(r_row)
                rows_added += 1

            if rows_added:
                print(f"  [ph_doe] {obs_date}: {rows_added} products")
        except Exception as e:
            print(f"  [ph_doe] Error {art_url}: {e}")
        time.sleep(0.4)

    if all_rows:
        print(f"  [ph_doe] {len(all_rows)} new rows")
    else:
        print("  [ph_doe] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ── DOE Visayas (regional) ────────────────────────────────────────────────────

_TMPL_PH = make_template(
    country="Philippines",
    wb_iso3="PHL",
    source_key="ph_doe_visayas_weekly",
    source_name="Philippines DOE Visayas Weekly Price Monitoring",
    source_url="https://doe.gov.ph/articles/",
    currency="PHP",
    unit="L",
    subnational_area="Visayas",
    publication_frequency="weekly",
    observation_method="survey",
)

_PH_PRODUCT_PATTERNS = [
    (
        r"(?i)ron\s*91|mogas\s*91|regular\s*gasoline",
        "RON 91",
        "gasoline",
        "regular",
        91,
    ),
    (
        r"(?i)ron\s*95|mogas\s*95|premium\s*gasoline",
        "RON 95",
        "gasoline",
        "premium",
        95,
    ),
    (r"(?i)ron\s*97", "RON 97", "gasoline", "premium", 97),
    (r"(?i)ron\s*100", "RON 100", "gasoline", "premium", 100),
    (r"(?i)diesel\s*plus", "Diesel Plus", "diesel", "premium", None),
    (r"(?i)\bdiesel\b", "Diesel", "diesel", "regular", None),
    (r"(?i)\bkerosene\b|\bkero\b", "Kerosene", "kerosene", "regular", None),
]


def _walk_nuxt(obj, _depth=0, _seen=None):
    """Recursively search NUXT JSON for article dicts."""
    if _seen is None:
        _seen = set()
    obj_id = id(obj)
    if obj_id in _seen or _depth > 30:
        return [], 1
    _seen.add(obj_id)

    articles = []
    total_pages = 1

    if isinstance(obj, dict):
        if "totalPages" in obj:
            try:
                tp = int(obj["totalPages"])
                if tp > 1:
                    total_pages = tp
            except (ValueError, TypeError):
                pass
        if "id" in obj and "title" in obj:
            articles.append(obj)
        else:
            for v in obj.values():
                sub_arts, sub_pages = _walk_nuxt(v, _depth + 1, _seen)
                articles.extend(sub_arts)
                if sub_pages > total_pages:
                    total_pages = sub_pages
    elif isinstance(obj, list):
        for item in obj:
            sub_arts, sub_pages = _walk_nuxt(item, _depth + 1, _seen)
            articles.extend(sub_arts)
            if sub_pages > total_pages:
                total_pages = sub_pages

    return articles, total_pages


def _parse_week_start(title: str, date_published: str = "") -> date | None:
    """Parse week-start date from DOE article title.

    Handles: '... for the week: February 24 to March 2, 2026'
    """
    m = re.search(
        r"(?i)week[:\s]+(\w+)\s+(\d{1,2})\s+to\s+\w+\s+\d{1,2}[,\s]+(\d{4})",
        title,
    )
    if m:
        month = MONTH_MAP_EN.get(m.group(1).lower()[:3])
        if month:
            try:
                return date(int(m.group(3)), month, int(m.group(2)))
            except ValueError:
                pass

    m = re.search(r"(?i)week[:\s]+(\w+)\s+(\d{1,2}).*?(\d{4})", title)
    if m:
        month = MONTH_MAP_EN.get(m.group(1).lower()[:3])
        if month:
            try:
                return date(int(m.group(3)), month, int(m.group(2)))
            except ValueError:
                pass

    if date_published:
        try:
            return pd.to_datetime(date_published).date()
        except Exception:
            pass

    return None


def _parse_nuxt_articles(html: str) -> list[dict]:
    """Parse __NUXT__ payload from listing page HTML to extract article metadata."""
    m = re.search(r"__NUXT__=(.*?)</script>", html, re.DOTALL)
    if not m:
        return []

    block = m.group(1)
    try:
        block = block.encode("utf-8").decode("unicode_escape", errors="replace")
    except Exception:
        pass

    article_chunks = re.split(r'(?=\{id:\d+,title:")', block)

    articles = []
    for chunk in article_chunks:
        id_m = re.match(r'\{id:(\d+),title:"([^"]*)"', chunk)
        if not id_m:
            continue

        article_id = int(id_m.group(1))
        title = id_m.group(2)

        dp_m = re.search(r'datePublished:"([^"]+)"', chunk)
        date_published = dp_m.group(1) if dp_m else ""

        pdf_url = None
        for cu_m in re.finditer(r'contentUrl:"([^"]+)"', chunk):
            path = cu_m.group(1)
            if re.search(r"\.pdf$|[-_]pdf$", path, re.IGNORECASE):
                pdf_url = (
                    path
                    if path.startswith("http")
                    else f"https://prod-cms.doe.gov.ph{path}"
                )
                break

        obs_date = _parse_week_start(title, date_published)
        if obs_date is None:
            continue

        articles.append(
            {
                "id": article_id,
                "title": title,
                "obs_date": obs_date,
                "pdf_url": pdf_url,
            }
        )

    return articles


def _parse_visayas_pdf(content: bytes) -> list[dict]:
    """Extract per-city price rows from a DOE Visayas PDF using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        print("  [ph_doe_vis] pdfplumber not installed")
        return []

    records = []
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    if not table:
                        continue

                    header_idx = None
                    col_province = col_city = col_product = col_price = None

                    for i, row in enumerate(table):
                        cells = [str(c).upper().strip() if c else "" for c in row]
                        if "PRODUCT" in cells and any("COMMON" in c for c in cells):
                            header_idx = i
                            for j, c in enumerate(cells):
                                if "PROVINCE" in c:
                                    col_province = j
                                elif "CITY" in c or "MUNICIPALITY" in c:
                                    col_city = j
                                elif c == "PRODUCT":
                                    col_product = j
                                elif "COMMON" in c:
                                    col_price = j
                            break

                    if header_idx is None or col_product is None or col_price is None:
                        continue

                    last_province = ""
                    last_city = ""

                    for row in table[header_idx + 1 :]:
                        if not row or len(row) <= col_price:
                            continue

                        def cell(idx, row=row):
                            if idx is None or idx >= len(row):
                                return ""
                            return str(row[idx] or "").strip()

                        prov = cell(col_province) if col_province is not None else ""
                        city_val = cell(col_city) if col_city is not None else ""
                        if prov:
                            last_province = prov
                        if city_val:
                            last_city = city_val

                        product = cell(col_product)
                        if not product or product.upper() == "PRODUCT":
                            continue

                        price_raw = cell(col_price)
                        if not price_raw or price_raw in ("-", "N/A", "n/a", ""):
                            continue

                        price = None
                        range_m = re.match(r"([\d.]+)\s*[-–]\s*([\d.]+)", price_raw)
                        if range_m:
                            try:
                                lo = float(range_m.group(1))
                                hi = float(range_m.group(2))
                                price = (lo + hi) / 2
                            except ValueError:
                                pass
                        else:
                            try:
                                price = float(re.sub(r"[^\d.]", "", price_raw))
                            except ValueError:
                                pass

                        if price is None or not (30 <= price <= 200):
                            continue

                        records.append(
                            {
                                "province": last_province,
                                "city": last_city,
                                "product": product,
                                "price": round(price, 2),
                            }
                        )
    except Exception as e:
        print(f"  [ph_doe_vis] PDF parse error: {e}")

    return records


def fetch_ph_doe_visayas(cutoff: date) -> pd.DataFrame:
    """Fetch Philippines DOE Visayas weekly price monitoring PDFs."""
    print("  [ph_doe_vis] Fetching Philippines DOE Visayas data...")
    print(f"  [ph_doe_vis] Cutoff: {cutoff}")

    session = get_session()
    listing_base = "https://doe.gov.ph/site/vfo/articles/group/liquid-fuels"
    listing_params = (
        "maincat=Retail%20Pump%20Prices"
        "&subcategory=Visayas%20Pump%20Prices"
        "&display_type=Card"
    )
    all_articles = []
    page = 1

    while True:
        url = f"{listing_base}?{listing_params}&page={page}"
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"  [ph_doe_vis] Listing page {page} error: {e}")
            break

        articles = _parse_nuxt_articles(resp.text)
        print(f"  [ph_doe_vis] Page {page}: {len(articles)} articles")

        if not articles:
            break

        all_articles.extend(articles)

        newest_on_page = max(a["obs_date"] for a in articles)
        if newest_on_page < cutoff:
            break

        page += 1
        time.sleep(0.5)

    new_articles = [a for a in all_articles if a["obs_date"] >= cutoff]
    print(
        f"  [ph_doe_vis] {len(all_articles)} total articles, {len(new_articles)} past cutoff"
    )

    if not new_articles:
        print("  [ph_doe_vis] No new articles")
        return pd.DataFrame()

    all_rows = []
    for article in new_articles:
        pdf_url = article.get("pdf_url")
        if not pdf_url:
            print(f"  [ph_doe_vis] No PDF URL for '{article['title'][:60]}'")
            continue

        try:
            pr = session.get(pdf_url, timeout=30)
            pr.raise_for_status()
        except Exception as e:
            print(f"  [ph_doe_vis] PDF download error {pdf_url}: {e}")
            time.sleep(0.3)
            continue

        records = _parse_visayas_pdf(pr.content)
        if not records:
            print(f"  [ph_doe_vis] {article['obs_date']}: 0 records from PDF")
            time.sleep(0.3)
            continue

        obs_date = article["obs_date"]
        if obs_date <= cutoff:
            time.sleep(0.3)
            continue

        article_url = (
            f"https://doe.gov.ph/articles/{article['id']}"
            if article.get("id")
            else pdf_url
        )

        for rec in records:
            matched = None
            for pat, prod_name, fam, qg, ron in _PH_PRODUCT_PATTERNS:
                if re.search(pat, rec["product"]):
                    matched = (prod_name, fam, qg, ron)
                    break

            if matched is None:
                continue

            prod_name, family, qg, ron = matched
            r = _TMPL_PH.copy()
            r.update(
                {
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "subnational_area": rec["province"] or "Visayas",
                    "city": rec["city"],
                    "price_local": rec["price"],
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date + timedelta(days=6)),
                    "observation_date": str(obs_date),
                    "source_url": article_url,
                }
            )
            r["observation_hash"] = make_hash(r)
            all_rows.append(r)

        print(f"  [ph_doe_vis] {obs_date}: {len(records)} per-city records")
        time.sleep(0.3)

    if all_rows:
        print(f"  [ph_doe_vis] Total: {len(all_rows)} new rows")
    else:
        print("  [ph_doe_vis] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
