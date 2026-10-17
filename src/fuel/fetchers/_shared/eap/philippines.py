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

from fuel.fetchers._shared.eap.legacy import MONTH_MAP_EN, get_session, make_hash, make_template

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

