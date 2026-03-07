"""Fiji FCCC Price Control Orders fetcher (PDF-based)."""

import io
import re
import time
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import MONTH_MAP_EN, get_session, make_hash, make_template

_TMPL_FJ = make_template(
    country="Fiji",
    wb_iso3="FJI",
    source_key="fj_fccc_order_prices",
    source_name="Fiji Commerce Commission (FCCC) Petroleum Price Control Orders",
    source_url="https://fccc.gov.fj/petroleum/",
    currency="FJD",
    unit="L",
    publication_frequency="quarterly",
)

_FJ_PRODUCT_PATTERNS = [
    (
        r"(?i)motor.?spirit|mogas|unleaded.?petrol",
        "Motor Spirit",
        "gasoline",
        "regular",
    ),
    (r"(?i)\bgasoil\b|\bdiesoline\b|\bdiesel\b", "Diesel", "diesel", "regular"),
    (r"(?i)pre.?mix|premix", "Premix", "gasoline", "premix"),
    (r"(?i)\bkerosene\b", "Kerosene", "kerosene", "regular"),
    (r"(?i)\bautogas\b|\blpg\b", "Autogas", "lpg", "regular"),
]


def _parse_fccc_pdf(content: bytes, pdf_url: str) -> list[dict]:
    """Parse an FCCC price control order PDF; return row dicts (no hashes)."""
    try:
        import pdfplumber
    except ImportError:
        print("  [fj_fccc] pdfplumber not installed — pip install pdfplumber")
        return []

    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as e:
        print(f"  [fj_fccc] pdfplumber error: {e}")
        return []

    eff_date = None
    for pat in [
        r"effective\s+(?:from\s+)?(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})",
        r"(\d{1,2})(?:st|nd|rd|th)?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})",
    ]:
        m = re.search(pat, full_text, re.IGNORECASE)
        if m:
            try:
                eff_date = date(
                    int(m.group(3)),
                    MONTH_MAP_EN[m.group(2).lower()[:3]],
                    int(m.group(1)),
                )
                break
            except (ValueError, KeyError):
                pass

    if eff_date is None:
        print(f"  [fj_fccc] Could not parse effective date from {pdf_url}")
        return []

    rows = []
    lines = full_text.split("\n")
    for prod_pat, prod_name, family, qg in _FJ_PRODUCT_PATTERNS:
        for i, line in enumerate(lines):
            if not re.search(prod_pat, line):
                continue
            window = " ".join(lines[i : i + 5])
            price_m = re.search(r"\b(\d+\.\d{1,3})\b", window)
            if not price_m:
                continue
            p = float(price_m.group(1))
            lo, hi = (1.0, 4.0) if family == "lpg" else (1.0, 5.0)
            if not (lo <= p <= hi):
                continue

            r = _TMPL_FJ.copy()
            r.update(
                {
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "price_local": p,
                    "effective_from": str(eff_date),
                    "effective_to": str(eff_date),
                    "observation_date": str(eff_date),
                    "source_url": pdf_url,
                }
            )
            rows.append(r)
            break  # one price per product

    return rows


def fetch_fj_fccc_orders(cutoff: date) -> pd.DataFrame:
    """Fetch Fiji FCCC Price Control Order PDFs from fccc.gov.fj."""
    print("  [fj_fccc] Fetching Fiji FCCC order PDFs...")
    print(f"  [fj_fccc] Cutoff: {cutoff}")

    session = get_session()
    try:
        resp = session.get("https://fccc.gov.fj/petroleum/", timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [fj_fccc] Could not fetch petroleum page: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")
    pdf_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if not href.lower().endswith(".pdf"):
            continue
        combined = (text + " " + href).lower()
        if re.search(r"petroleum.prices", combined):
            full = href if href.startswith("http") else "https://fccc.gov.fj" + href
            pdf_links.append((full, text))

    print(f"  [fj_fccc] Found {len(pdf_links)} petroleum PDF links")

    all_rows = []
    consecutive_old = 0
    for pdf_url, link_text in pdf_links:
        try:
            r = session.get(pdf_url, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f"  [fj_fccc] PDF fetch error {pdf_url}: {e}")
            continue

        parsed = _parse_fccc_pdf(r.content, pdf_url)
        new_from_this = 0
        for row in parsed:
            try:
                obs_date = date.fromisoformat(row["observation_date"])
            except (ValueError, KeyError):
                continue
            if obs_date <= cutoff:
                consecutive_old += 1
                continue
            consecutive_old = 0
            row["observation_hash"] = make_hash(row)
            all_rows.append(row)
            new_from_this += 1

        if parsed:
            obs = parsed[0]["observation_date"] if parsed else "?"
            print(f"  [fj_fccc] {obs}: {len(parsed)} products — {link_text[:60]}")

        if consecutive_old >= 6:
            print("  [fj_fccc] Stopping early — past cutoff")
            break

        time.sleep(0.5)

    if all_rows:
        print(f"  [fj_fccc] {len(all_rows)} new rows")
    else:
        print("  [fj_fccc] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
