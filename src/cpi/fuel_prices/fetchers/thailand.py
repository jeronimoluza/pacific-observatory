"""Thailand fuel price fetchers — OR/PTTOR daily and Bangchak historical."""

# ruff: noqa: E402
SOURCE_META = [
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

import html
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime

import pandas as pd

from ..utils import get_session, make_hash, make_template

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
