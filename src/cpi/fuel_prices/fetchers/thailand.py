"""Thailand fuel price fetchers — EPPO P04 monthly retail and NGV retail."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_th_eppo_retail_daily",
        "country": "Thailand",
        "source_name": "EPPO Retail Fuel Prices (Daily)",
        "url": "http://www.eppo.go.th/petro/price/index.html",
        "description": "Official EPPO retail fuel prices page with current pump prices across major products.",
        "extraction_method": ["Web scraping"],
        "products": [
            "Benzine 95",
            "Gasohol 95",
            "Gasohol 91",
            "Gasohol E20",
            "Gasohol E85",
            "Diesel B7",
            "Diesel B10",
            "Diesel B20",
            "Premium Diesel",
        ],
        "source_keys": ["th_eppo_retail_daily"],
        "publishes_on": "Daily or irregular",
        "notes": "Retail prices published on EPPO oil price page; scrape table when available.",
    },
    {
        "fetcher_fn": "fetch_th_or_pttor_current_oil_price",
        "country": "Thailand",
        "source_name": "OR (PTT Oil & Retail) Current Oil Price (Daily)",
        "url": "https://orapiweb.pttor.com/oilservice/OilPrice.asmx",
        "description": "First-party retail price board for Thailand from OR/PTTOR, exposed as a SOAP web service (CurrentOilPrice). Returns Bangkok prices with explicit timestamp.",
        "extraction_method": ["SOAP API"],
        "products": [
            "Diesel",
            "Premium Diesel",
            "Gasoline 95",
            "Gasohol 95",
            "Gasohol 91",
            "Gasohol E20",
            "Gasohol E85",
            "Super Power GSH95",
        ],
        "source_keys": ["th_or_pttor_current_oil_price_daily"],
        "publishes_on": "Daily (typically 05:00 local)",
        "notes": "Uses SOAPAction CurrentOilPrice and parses embedded XML payload. Prices are for Bangkok and exclude local tax where applicable; recorded as THB/L.",
    },
    {
        "fetcher_fn": "fetch_th_eppo_p04",
        "country": "Thailand",
        "source_name": "EPPO P04 Monthly Retail Petroleum",
        "url": "https://www.eppo.go.th/epposite/images/Energy-Statistics/energyinformation/Energy_Statistics/Petroleum_Prices/P04.xls",
        "description": "Official government source (Energy Policy and Planning Office, Ministry of Energy). Publishes monthly retail petroleum price statistics as a public XLS file (P04 table). Includes biofuel blends.",
        "extraction_method": "Excel download (XLS)",
        "products": [
            "Gasoline 95 (ULG95)",
            "Gasoline 91 (UGR91)",
            "Kerosene",
            "Diesel HSD",
            "Diesel LSD",
            "Gasohol E10",
            "Gasohol E20",
            "Gasohol E85",
        ],
        "frequency": "Monthly",
        "output": "Secondary CSV",
        "notes": "Direct XLS download; uses xlrd engine. Locates header row by scanning for product keywords. Dates encoded as MON-DD with year from preceding year-marker rows. Price range THB 10–200/L.",
    },
    {
        "fetcher_fn": "fetch_th_eppo_p04",
        "country": "Thailand",
        "source_name": "EPPO P04 Monthly Retail Petroleum",
        "url": "https://www.eppo.go.th/epposite/images/Energy-Statistics/energyinformation/Energy_Statistics/Petroleum_Prices/P04.xls",
        "description": "Official government (EPPO/Ministry of Energy). Monthly retail petroleum stats as public XLS (P04 table). Includes biofuel blends.",
        "extraction_method": ["Excel download"],
        "products": [
            "Gasoline 95 (ULG95)",
            "Gasoline 91 (UGR91)",
            "Kerosene",
            "Diesel HSD",
            "Diesel LSD",
            "Gasohol E10",
            "Gasohol E20",
            "Gasohol E85",
        ],
        "source_keys": ["th_eppo_p04_monthly"],
        "publishes_on": "Monthly",
        "notes": "Direct XLS download; xlrd engine. Locates header row by scanning for product keywords. Dates encoded as MON-DD with year from preceding year-marker rows. Price range THB 10–200/L.",
    },
    {
        "fetcher_fn": "fetch_thailand_eppo_ngv",
        "country": "Thailand",
        "source_name": "EPPO NGV Bangkok Retail Prices",
        "url": "https://www.eppo.go.th/images/petroleum/price/retail-priceNGV/NGVPrice.xls",
        "description": "Official government (EPPO/Ministry of Energy). Monthly NGV retail prices in Bangkok as public XLS file.",
        "extraction_method": ["Excel download"],
        "products": ["Natural Gas for Vehicles (NGV)"],
        "source_keys": ["th_eppo_ngv_bangkok_2025"],
        "publishes_on": "Monthly",
        "notes": "Direct XLS download; auto-detects date and price columns. Bangkok only. Unit: kg. Price range THB 5–30/kg.",
    },
    {
        "fetcher_fn": "fetch_th_bangchak_retail_history",
        "country": "Thailand",
        "source_name": "Bangchak historical retail oil prices",
        "url": "https://www.bangchak.co.th/en/oilprice/historical",
        "description": "Bangchak retail oil price history with change-date rows by product.",
        "extraction_method": ["Playwright web scraping"],
        "products": [
            "Hi Premium Diesel S",
            "Hi Diesel S",
            "Hi Premium 97",
            "Gasohol 95",
            "Gasohol 91",
            "E20",
            "E85",
        ],
        "source_keys": ["th_bangchak_retail_history"],
        "publishes_on": "Irregular",
        "notes": "Uses historical price table with year dropdown; columns mapped by th.title attributes.",
    },
]

import io
import html
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from io import BytesIO

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import get_session, make_hash, make_template

# ── EPPO P04 Monthly Retail Petroleum ─────────────────────────────────────────

_TMPL_TH = make_template(
    country="Thailand",
    wb_iso3="THA",
    source_key="th_eppo_p04_monthly",
    source_name="Thailand EPPO Table P04 – Retail Prices of Petroleum Products",
    source_url="https://www.eppo.go.th/epposite/images/Energy-Statistics/energyinformation/Energy_Statistics/Petroleum_Prices/P04.xls",
    currency="THB",
    unit="L",
    subnational_area="National",
    publication_frequency="monthly",
    observation_method="reported",
)

_TH_EPPO_PRODUCTS = [
    ("ULG95", "Gasoline 95", "gasoline", "premium", 95),
    ("UGR91", "Gasoline 91", "gasoline", "regular", 91),
    ("KERO", "Kerosene", "kerosene", "regular", None),
    ("HSD", "Diesel (HSD)", "diesel", "regular", None),
    ("LSD", "Diesel (LSD)", "diesel", "premium", None),
    ("E10", "Gasohol E10", "gasoline", "regular", 91),
    ("E20", "Gasohol E20", "gasoline", "regular", 91),
    ("E85", "Gasohol E85", "gasoline", "biofuel", None),
]

_TH_PRICE_MIN, _TH_PRICE_MAX = 10.0, 200.0

_TH_MONTH_ABBR = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

_P04_URL = "https://www.eppo.go.th/epposite/images/Energy-Statistics/energyinformation/Energy_Statistics/Petroleum_Prices/P04.xls"

# ── EPPO Retail Fuel Prices (Daily) ───────────────────────────────────────────

_TH_RETAIL_URL = "http://www.eppo.go.th/petro/price/index.html"

_TMPL_TH_DAILY = make_template(
    country="Thailand",
    wb_iso3="THA",
    source_key="th_eppo_retail_daily",
    source_name="Thailand EPPO Retail Fuel Prices (Daily)",
    source_url=_TH_RETAIL_URL,
    currency="THB",
    unit="L",
    subnational_area="National",
    publication_frequency="daily",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_THAI_MONTHS = {
    "มกราคม": 1,
    "กุมภาพันธ์": 2,
    "มีนาคม": 3,
    "เมษายน": 4,
    "พฤษภาคม": 5,
    "มิถุนายน": 6,
    "กรกฎาคม": 7,
    "สิงหาคม": 8,
    "กันยายน": 9,
    "ตุลาคม": 10,
    "พฤศจิกายน": 11,
    "ธันวาคม": 12,
}

_TH_RETAIL_PRODUCTS = [
    {
        "patterns": [r"benzine\s*95", r"เบนซิน\s*95"],
        "fuel_product": "Benzine 95",
        "fuel_family": "gasoline",
        "quality_group": "premium",
        "octane_ron": 95,
        "ethanol_pct": 0,
    },
    {
        "patterns": [r"gasohol\s*95", r"แก๊สโซฮอล์\s*95"],
        "fuel_product": "Gasohol 95",
        "fuel_family": "gasoline",
        "quality_group": "regular",
        "octane_ron": 95,
        "ethanol_pct": 10,
    },
    {
        "patterns": [r"gasohol\s*91", r"แก๊สโซฮอล์\s*91"],
        "fuel_product": "Gasohol 91",
        "fuel_family": "gasoline",
        "quality_group": "regular",
        "octane_ron": 91,
        "ethanol_pct": 10,
    },
    {
        "patterns": [r"gasohol\s*e20", r"แก๊สโซฮอล์\s*e20"],
        "fuel_product": "Gasohol E20",
        "fuel_family": "gasoline",
        "quality_group": "regular",
        "octane_ron": 95,
        "ethanol_pct": 20,
    },
    {
        "patterns": [r"gasohol\s*e85", r"แก๊สโซฮอล์\s*e85"],
        "fuel_product": "Gasohol E85",
        "fuel_family": "gasoline",
        "quality_group": "biofuel",
        "octane_ron": None,
        "ethanol_pct": 85,
    },
    {
        "patterns": [r"diesel\s*b7", r"ดีเซล\s*b7"],
        "fuel_product": "Diesel B7",
        "fuel_family": "diesel",
        "quality_group": "regular",
    },
    {
        "patterns": [r"diesel\s*b10", r"ดีเซล\s*b10"],
        "fuel_product": "Diesel B10",
        "fuel_family": "diesel",
        "quality_group": "regular",
    },
    {
        "patterns": [r"diesel\s*b20", r"ดีเซล\s*b20"],
        "fuel_product": "Diesel B20",
        "fuel_family": "diesel",
        "quality_group": "regular",
    },
    {
        "patterns": [r"premium\s*diesel", r"ดีเซล\s*พรีเมียม", r"ดีเซลพรีเมียม"],
        "fuel_product": "Premium Diesel",
        "fuel_family": "diesel",
        "quality_group": "premium",
    },
]

_TH_NEWS_FEED_URL = (
    "https://www.eppo.go.th/index.php/th/petroleum/oil/status-oil-price"
    "?orders[publishUp]=publishUp&issearch=1&format=feed"
)


# ── Bangchak historical retail prices ────────────────────────────────────────

_TH_BANGCHAK_HISTORY_URL = (
    "https://www.bangchak.co.th/en/oilprice/historical?year={year}"
)

_TMPL_TH_BANGCHAK = make_template(
    country="Thailand",
    wb_iso3="THA",
    source_key="th_bangchak_retail_history",
    source_name="Bangchak historical retail oil prices",
    source_url="https://www.bangchak.co.th/en/oilprice/historical",
    currency="THB",
    unit="L",
    subnational_area="National",
    publication_frequency="irregular",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_TH_BANGCHAK_PRODUCT_MAP = {
    "hi premium diesel s": {
        "fuel_family": "diesel",
        "fuel_product": "Hi Premium Diesel S",
        "quality_group": "premium",
    },
    "hi diesel s": {
        "fuel_family": "diesel",
        "fuel_product": "Hi Diesel S",
        "quality_group": "regular",
    },
    "hi premium 97 gasohol 95": {
        "fuel_family": "gasoline",
        "fuel_product": "Hi Premium 97",
        "quality_group": "premium",
        "octane_ron": 97,
    },
    "gasohol e85 s evo": {
        "fuel_family": "gasoline",
        "fuel_product": "E85",
        "quality_group": "biofuel",
        "ethanol_pct": 85,
    },
    "gasohol e20 s evo": {
        "fuel_family": "gasoline",
        "fuel_product": "E20",
        "quality_group": "regular",
        "ethanol_pct": 20,
    },
    "gasohol 91 s evo": {
        "fuel_family": "gasoline",
        "fuel_product": "Gasohol 91",
        "quality_group": "regular",
        "octane_ron": 91,
    },
    "gasohol 95 s evo": {
        "fuel_family": "gasoline",
        "fuel_product": "Gasohol 95",
        "quality_group": "regular",
        "octane_ron": 95,
    },
}


# ── OR / PTTOR Current Oil Price (Daily) ──────────────────────────────────────

_TH_OR_OILPRICE_WSDL = "https://orapiweb.pttor.com/oilservice/OilPrice.asmx"

_TMPL_TH_OR = make_template(
    country="Thailand",
    wb_iso3="THA",
    source_key="th_or_pttor_current_oil_price_daily",
    source_name="Thailand OR/PTTOR Current Oil Price (Daily)",
    source_url=_TH_OR_OILPRICE_WSDL,
    source_type="compiled_api",
    currency="THB",
    unit="L",
    subnational_area="Bangkok",
    publication_frequency="daily",
    observation_method="reported",
    tax_status="tax_exclusive",
)

_TH_OR_PRODUCT_MAP: dict[str, dict] = {
    "diesel": {
        "fuel_family": "diesel",
        "fuel_product": "Diesel",
        "quality_group": "regular",
    },
    "premium diesel": {
        "fuel_family": "diesel",
        "fuel_product": "Premium Diesel",
        "quality_group": "premium",
    },
    "gasoline 95": {
        "fuel_family": "gasoline",
        "fuel_product": "Gasoline 95",
        "quality_group": "premium",
        "octane_ron": 95,
        "ethanol_pct": 0,
    },
    "gasohol 95": {
        "fuel_family": "gasoline",
        "fuel_product": "Gasohol 95",
        "quality_group": "regular",
        "octane_ron": 95,
        "ethanol_pct": 10,
    },
    "super power gsh95": {
        "fuel_family": "gasoline",
        "fuel_product": "Super Power GSH95",
        "quality_group": "premium",
        "octane_ron": 95,
        "ethanol_pct": 10,
    },
    "gasohol 91": {
        "fuel_family": "gasoline",
        "fuel_product": "Gasohol 91",
        "quality_group": "regular",
        "octane_ron": 91,
        "ethanol_pct": 10,
    },
    "gasohol e20": {
        "fuel_family": "gasoline",
        "fuel_product": "Gasohol E20",
        "quality_group": "regular",
        "octane_ron": 95,
        "ethanol_pct": 20,
    },
    "gasohol e85": {
        "fuel_family": "gasoline",
        "fuel_product": "Gasohol E85",
        "quality_group": "biofuel",
        "ethanol_pct": 85,
    },
}


def _th_or_current_oil_price_payload(language: str = "en") -> str:
    soap = f"""<?xml version=\"1.0\" encoding=\"utf-8\"?>
<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">
  <soap:Body>
    <CurrentOilPrice xmlns=\"http://www.pttor.com\">
      <Language>{language}</Language>
    </CurrentOilPrice>
  </soap:Body>
</soap:Envelope>"""

    session = get_session()
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "https://orapiweb.pttor.com/CurrentOilPrice",
    }
    resp = session.post(
        _TH_OR_OILPRICE_WSDL, data=soap.encode("utf-8"), headers=headers, timeout=30
    )
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    ns = {
        "soap": "http://www.w3.org/2003/05/soap-envelope",
        "m": "http://www.pttor.com",
    }
    result_el = root.find(".//m:CurrentOilPriceResult", ns)
    if result_el is None or not result_el.text:
        return ""
    return html.unescape(result_el.text).strip()


def fetch_th_or_pttor_current_oil_price(cutoff: date) -> pd.DataFrame:
    """Fetch Thailand daily retail fuel prices from OR/PTTOR SOAP API.

    This uses OR's `CurrentOilPrice` endpoint, which returns Bangkok prices
    and a `PRICE_DATE` timestamp. Rows are recorded as THB/L.
    """
    print("  [th_or] Fetching Thailand OR/PTTOR CurrentOilPrice (daily)...")
    print(f"  [th_or] Cutoff: {cutoff}")

    try:
        inner_xml = _th_or_current_oil_price_payload(language="en")
    except Exception as e:
        print(f"  [th_or] Request failed: {e}")
        return pd.DataFrame()

    if not inner_xml:
        print("  [th_or] Empty payload")
        return pd.DataFrame()

    try:
        inner_root = ET.fromstring(inner_xml)
    except ET.ParseError as e:
        print(f"  [th_or] Payload parse error: {e}")
        return pd.DataFrame()

    fuels = inner_root.findall(".//FUEL")
    if not fuels:
        print("  [th_or] No FUEL nodes in payload")
        return pd.DataFrame()

    rows = []
    obs_date: date | None = None
    for fuel in fuels:
        price_date = (fuel.findtext("PRICE_DATE") or "").strip()
        product = (fuel.findtext("PRODUCT") or "").strip()
        price_str = (fuel.findtext("PRICE") or "").strip()
        if not price_date or not product or not price_str:
            continue

        # PRICE_DATE like 2026-03-10T05:00
        try:
            d = date.fromisoformat(price_date.split("T")[0])
        except ValueError:
            continue
        if obs_date is None:
            obs_date = d
        if d != obs_date:
            # Keep first date only; mixed dates would be surprising
            continue
        if d <= cutoff:
            continue

        try:
            price = float(price_str)
        except ValueError:
            continue
        if not (5 <= price <= 200):
            continue

        spec = _TH_OR_PRODUCT_MAP.get(product.lower())
        if spec is None:
            continue

        row = _TMPL_TH_OR.copy()
        row.update(
            {
                "fuel_family": spec.get("fuel_family"),
                "fuel_product": spec.get("fuel_product"),
                "quality_group": spec.get("quality_group"),
                "octane_ron": spec.get("octane_ron"),
                "ethanol_pct": spec.get("ethanol_pct"),
                "price_local": round(price, 4),
                "effective_from": str(d),
                "effective_to": str(d),
                "observation_date": str(d),
                "notes": "Bangkok price board; excludes local tax where applicable.",
            }
        )
        row["observation_hash"] = make_hash(row)
        rows.append(row)

    if not rows:
        if obs_date is not None and obs_date <= cutoff:
            print(f"  [th_or] No new rows (obs_date={obs_date} <= cutoff)")
        else:
            print("  [th_or] No rows parsed")
        return pd.DataFrame()

    print(f"  [th_or] {len(rows)} rows fetched for {obs_date}")
    return pd.DataFrame(rows)


def _parse_thai_date_text(text: str) -> date | None:
    match = re.search(r"(\d{1,2})\s+([ก-ฮ]+)\s+(\d{4})", text)
    if match:
        day = int(match.group(1))
        mon = _THAI_MONTHS.get(match.group(2).strip())
        year = int(match.group(3))
        if mon:
            if year >= 2400:
                year -= 543
            try:
                return date(year, mon, day)
            except ValueError:
                return None
    match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
    if match:
        day = int(match.group(1))
        mon = int(match.group(2))
        year = int(match.group(3))
        if year < 100:
            year += 2000
        if year >= 2400:
            year -= 543
        try:
            return date(year, mon, day)
        except ValueError:
            return None
    return None


def _match_th_retail_product(text: str) -> dict | None:
    key = (text or "").lower()
    for spec in _TH_RETAIL_PRODUCTS:
        for pattern in spec["patterns"]:
            if re.search(pattern, key, re.IGNORECASE):
                return spec
    return None


def _parse_price_value(text: str) -> float | None:
    if not text:
        return None
    candidates = re.findall(r"\d+[\d,]*(?:\.\d+)?", text)
    if not candidates:
        return None
    raw = candidates[-1].replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_bangchak_date(text: str) -> date | None:
    value = (text or "").strip()
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_bangchak_title(title: str) -> str:
    return " ".join((title or "").strip().lower().split())


def fetch_th_eppo_retail_daily(cutoff: date) -> pd.DataFrame:
    """Fetch Thailand EPPO current retail fuel prices from the daily page."""
    print("  [th_eppo_daily] Fetching Thailand EPPO retail daily prices...")
    print(f"  [th_eppo_daily] Cutoff: {cutoff}")

    session = get_session()
    try:
        resp = session.get(_TH_RETAIL_URL, timeout=45)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [th_eppo_daily] Could not fetch page: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")
    page_text = soup.get_text(" ", strip=True)
    obs_date = _parse_thai_date_text(page_text) or date.today()

    if obs_date <= cutoff:
        print(f"  [th_eppo_daily] Date {obs_date} not newer than cutoff {cutoff}")
        return pd.DataFrame()

    rows = []
    seen_products = set()
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [
                cell.get_text(" ", strip=True) for cell in tr.find_all(["th", "td"])
            ]
            if len(cells) < 2:
                continue
            prod_text = cells[0]
            spec = _match_th_retail_product(prod_text)
            if not spec:
                continue

            price = None
            for cell_text in cells[1:]:
                val = _parse_price_value(cell_text)
                if val is not None:
                    price = val
            if price is None or not (5 <= price <= 120):
                continue

            product_key = spec["fuel_product"]
            if product_key in seen_products:
                continue
            seen_products.add(product_key)

            row = _TMPL_TH_DAILY.copy()
            row.update(
                {
                    "fuel_family": spec.get("fuel_family"),
                    "fuel_product": spec.get("fuel_product"),
                    "quality_group": spec.get("quality_group"),
                    "octane_ron": spec.get("octane_ron"),
                    "ethanol_pct": spec.get("ethanol_pct"),
                    "price_local": round(price, 4),
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date),
                    "observation_date": str(obs_date),
                    "source_url": _TH_RETAIL_URL,
                    "notes": prod_text.strip() or None,
                }
            )
            row["observation_hash"] = make_hash(row)
            rows.append(row)

    if not rows:
        print("  [th_eppo_daily] No rows parsed from page")
        return pd.DataFrame()

    print(f"  [th_eppo_daily] {len(rows)} rows fetched for {obs_date}")
    return pd.DataFrame(rows)


def fetch_th_bangchak_retail_history(cutoff: date) -> pd.DataFrame:
    """Fetch Thailand Bangchak historical retail prices by year."""
    print("  [th_bangchak] Fetching Bangchak historical retail prices...")
    print(f"  [th_bangchak] Cutoff: {cutoff}")

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"  [th_bangchak] Playwright not available: {e}")
        return pd.DataFrame()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # Discover available years from the dropdown (site tends to limit to a
        # fixed range like 2017..current).
        try:
            page.goto(
                "https://www.bangchak.co.th/en/oilprice/historical", timeout=60_000
            )
            page.wait_for_timeout(1_500)
            years = page.evaluate(
                """() => {
                    const sel = document.querySelector('select[name=year]');
                    if (!sel) return [];
                    return Array.from(sel.querySelectorAll('option'))
                      .map(o => (o.textContent || '').trim())
                      .map(t => parseInt(t, 10))
                      .filter(n => Number.isFinite(n) && n >= 1900 && n <= 2100);
                }"""
            )
        except Exception as e:
            print(f"  [th_bangchak] Could not discover year options: {e}")
            years = []

        if not years:
            years = list(range(cutoff.year, date.today().year + 1))

        years = sorted(set(int(y) for y in years if int(y) >= cutoff.year))

        rows: list[dict] = []
        for year in years:
            url = _TH_BANGCHAK_HISTORY_URL.format(year=year)
            try:
                page.goto(url, timeout=60_000)
                page.wait_for_timeout(2_000)
            except Exception as e:
                print(f"  [th_bangchak] Page load error ({year}): {e}")
                continue

            try:
                payload = page.evaluate(
                    """() => {
                        const tables = Array.from(document.querySelectorAll('table'));
                        const table = tables.find(t => t.querySelector('thead th[title]'));
                        if (!table) return { titles: [], rows: [] };
                        const titleThs = Array.from(table.querySelectorAll('thead tr:nth-child(2) th[title]'));
                        const titles = titleThs.map(th => (th.getAttribute('title') || '').trim()).filter(Boolean);
                        const rows = Array.from(table.querySelectorAll('tbody tr')).map(tr =>
                          Array.from(tr.querySelectorAll('th,td')).map(td => (td.textContent || '').trim())
                        );
                        return { titles, rows };
                    }"""
                )
            except Exception as e:
                print(f"  [th_bangchak] DOM extract error ({year}): {e}")
                continue

            titles = payload.get("titles") or []
            body_rows = payload.get("rows") or []
            if not titles or not body_rows:
                print(f"  [th_bangchak] No table rows for {year}")
                continue

            col_map: dict[int, str] = {}
            for i, title in enumerate(titles, start=1):
                col_map[i] = _normalize_bangchak_title(str(title))

            for cells in body_rows:
                if not cells or len(cells) < 2:
                    continue
                obs_date = _parse_bangchak_date(str(cells[0]))
                if obs_date is None or obs_date <= cutoff:
                    continue

                for col_idx, title_key in col_map.items():
                    if col_idx >= len(cells):
                        continue
                    price = _parse_price_value(str(cells[col_idx]))
                    if price is None or not (5 <= price <= 200):
                        continue
                    spec = _TH_BANGCHAK_PRODUCT_MAP.get(title_key)
                    if spec is None:
                        continue

                    row = _TMPL_TH_BANGCHAK.copy()
                    row.update(
                        {
                            "fuel_family": spec.get("fuel_family"),
                            "fuel_product": spec.get("fuel_product"),
                            "quality_group": spec.get("quality_group"),
                            "octane_ron": spec.get("octane_ron"),
                            "ethanol_pct": spec.get("ethanol_pct"),
                            "price_local": round(price, 4),
                            "effective_from": str(obs_date),
                            "effective_to": str(obs_date),
                            "observation_date": str(obs_date),
                            "source_url": url,
                        }
                    )
                    row["observation_hash"] = make_hash(row)
                    rows.append(row)

        browser.close()

    if not rows:
        print("  [th_bangchak] No new rows")
        return pd.DataFrame()

    print(f"  [th_bangchak] {len(rows)} rows fetched")
    return pd.DataFrame(rows)


def _parse_th_date(cell, current_year: int) -> date | tuple | None:
    """Parse 'MON-DD' or year integer from a P04 Excel cell."""
    s = str(cell).strip().upper()
    if s in ("AVERAGE", "NAN", "DATE", ""):
        return None
    try:
        yr = int(float(s))
        if 1990 <= yr <= 2100:
            return ("year", yr)
    except (ValueError, TypeError):
        pass
    m = re.match(r"([A-Z]{3})-(\d{1,2})$", s)
    if m and m.group(1) in _TH_MONTH_ABBR:
        mo = _TH_MONTH_ABBR[m.group(1)]
        day = int(m.group(2))
        try:
            return date(current_year, mo, day)
        except ValueError:
            return None
    return None


def fetch_th_eppo_p04(cutoff: date) -> pd.DataFrame:
    """Full-refresh fetch of Thailand EPPO P04 monthly retail petroleum prices."""
    print("  [th_eppo] Fetching Thailand EPPO P04 data (full refresh)...")
    print(f"  [th_eppo] Cutoff: {cutoff}")

    session = get_session()
    try:
        resp = session.get(_P04_URL, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [th_eppo] Download error: {e}")
        return pd.DataFrame()

    content = resp.content
    try:
        raw = pd.read_excel(io.BytesIO(content), engine="xlrd", header=None)
    except Exception:
        try:
            raw = pd.read_excel(io.BytesIO(content), header=None)
        except Exception as e:
            print(f"  [th_eppo] Excel parse error: {e}")
            return pd.DataFrame()

    header_row_idx = None
    col_map: dict[int, tuple] = {}
    for row_idx in range(min(20, len(raw))):
        row_vals = [str(v).upper() for v in raw.iloc[row_idx]]
        matches: dict[int, tuple] = {}
        for col_idx, cell in enumerate(row_vals):
            for kw, prod_name, family, qg, ron in _TH_EPPO_PRODUCTS:
                if kw in cell:
                    matches[col_idx] = (prod_name, family, qg, ron)
                    break
        if len(matches) >= 2:
            header_row_idx = row_idx
            col_map = matches
            break

    if header_row_idx is None:
        print("  [th_eppo] Could not locate header row with product keywords")
        return pd.DataFrame()

    date_col = 1
    all_rows = []
    current_year = None

    for row_idx in range(header_row_idx + 1, len(raw)):
        row = raw.iloc[row_idx]
        cell = row.iloc[date_col]
        parsed = _parse_th_date(cell, current_year or 2000)
        if parsed is None:
            continue
        if isinstance(parsed, tuple) and parsed[0] == "year":
            current_year = parsed[1]
            continue
        if current_year is None:
            continue
        obs_date = parsed
        if obs_date <= cutoff:
            continue

        if obs_date.month == 12:
            eff_to = date(obs_date.year, 12, 31)
        else:
            eff_to = date(obs_date.year, obs_date.month + 1, 1) - timedelta(days=1)

        for col_idx, (prod_name, family, qg, ron) in col_map.items():
            if col_idx >= len(row):
                continue
            try:
                price = float(row.iloc[col_idx])
            except (ValueError, TypeError):
                continue
            if not (_TH_PRICE_MIN <= price <= _TH_PRICE_MAX):
                continue

            r = _TMPL_TH.copy()
            r.update(
                {
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "price_local": price,
                    "effective_from": str(obs_date),
                    "effective_to": str(eff_to),
                    "observation_date": str(obs_date),
                    "source_url": _P04_URL,
                }
            )
            r["observation_hash"] = make_hash(r)
            all_rows.append(r)

    if all_rows:
        print(f"  [th_eppo] {len(all_rows)} new rows")
    else:
        print("  [th_eppo] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ── EPPO NGV Bangkok ──────────────────────────────────────────────────────────

_TMPL_TH_NGV = make_template(
    country="Thailand",
    wb_iso3="THA",
    source_key="th_eppo_ngv_bangkok_2025",
    source_name="Thailand EPPO NGV Retail Prices — Bangkok",
    source_url="https://www.eppo.go.th/images/petroleum/price/retail-priceNGV/NGVPrice.xls",
    currency="THB",
    unit="kg",
    subnational_area="Bangkok",
    publication_frequency="monthly",
    observation_method="reported",
    fuel_product="NGV retail price",
    fuel_family="natural_gas",
    quality_group="regular",
)

_NGV_URL = "https://www.eppo.go.th/images/petroleum/price/retail-priceNGV/NGVPrice.xls"


def fetch_thailand_eppo_ngv(cutoff: date) -> pd.DataFrame:
    """Fetch Thailand EPPO NGV retail prices from Bangkok (monthly XLS)."""
    print("  [th_eppo_ngv] Fetching Thailand EPPO NGV data...")
    print(f"  [th_eppo_ngv] Cutoff: {cutoff}")

    session = get_session()
    try:
        resp = session.get(_NGV_URL, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [th_eppo_ngv] Could not download XLS: {e}")
        return pd.DataFrame()

    try:
        import xlrd  # noqa: F401

        engine = "xlrd"
    except ImportError:
        engine = "openpyxl"

    all_rows = []
    try:
        xf = pd.ExcelFile(BytesIO(resp.content), engine=engine)
        for sheet in xf.sheet_names:
            try:
                raw = pd.read_excel(
                    BytesIO(resp.content), sheet_name=sheet, header=None, engine=engine
                )
            except Exception:
                continue

            date_col = None
            for col_idx in range(min(3, raw.shape[1])):
                parsed = pd.to_datetime(raw.iloc[:, col_idx], errors="coerce")
                if parsed.notna().sum() > 10:
                    date_col = col_idx
                    break

            if date_col is None:
                continue

            raw["_date"] = pd.to_datetime(raw.iloc[:, date_col], errors="coerce")
            raw_new = raw[raw["_date"].dt.date > cutoff].copy()

            if raw_new.empty:
                continue

            price_col = None
            for col_idx in range(raw.shape[1]):
                if col_idx == date_col:
                    continue
                vals = pd.to_numeric(raw.iloc[:, col_idx], errors="coerce").dropna()
                if vals.empty:
                    continue
                if vals.between(5, 30).sum() > 5:
                    price_col = col_idx
                    break

            if price_col is None:
                continue

            for _, row in raw_new.iterrows():
                obs_date = row["_date"].date()
                try:
                    price = float(row.iloc[price_col])
                    if pd.isna(price) or not (5 <= price <= 30):
                        continue
                except (ValueError, TypeError):
                    continue

                r = _TMPL_TH_NGV.copy()
                r.update(
                    {
                        "price_local": round(price, 4),
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date),
                        "observation_date": str(obs_date),
                        "source_url": _NGV_URL,
                    }
                )
                r["observation_hash"] = make_hash(r)
                all_rows.append(r)

            if all_rows:
                print(f"  [th_eppo_ngv] Sheet '{sheet}': {len(all_rows)} new rows")
                break

    except Exception as e:
        if "zip" in str(e).lower() or "xlrd" in str(e).lower():
            print("  [th_eppo_ngv] Legacy .xls requires xlrd: pip install xlrd>=2.0.1")
        else:
            print(f"  [th_eppo_ngv] Error parsing XLS: {e}")

    if not all_rows:
        print("  [th_eppo_ngv] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


def fetch_thailand_news_evidence(max_items: int = 50) -> list[dict]:
    """Fetch Thailand EPPO oil price news RSS metadata for Track A evidence."""
    session = get_session()
    try:
        resp = session.get(_TH_NEWS_FEED_URL, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [th_news] Could not fetch RSS feed: {e}")
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"  [th_news] RSS parse error: {e}")
        return []

    items = root.findall(".//item")
    records = []
    fetched_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    for item in items[:max_items]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        pub_raw = (item.findtext("pubDate") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub_date = None
        if pub_raw:
            try:
                pub_date = parsedate_to_datetime(pub_raw).date().isoformat()
            except Exception:
                pub_date = None

        records.append(
            {
                "country": "Thailand",
                "source_key": "th_eppo_oil_price_status_news",
                "source_name": "EPPO Oil Price Status News",
                "source_url": _TH_NEWS_FEED_URL,
                "article_url": link or guid,
                "title": title,
                "published_date": pub_date,
                "summary": desc or None,
                "fetched_at": fetched_at,
                "evidence_type": "news_article",
            }
        )

    return records
