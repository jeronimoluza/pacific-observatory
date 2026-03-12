"""Korea Opinet weekly national average fuel price fetcher."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_kr_opinet_weekly",
        "country": "Korea, Rep.",
        "source_name": "Opinet Weekly National Average",
        "url": "https://www.opinet.co.kr/user/doop/doopOilHistory.do",
        "description": "Official (Opinet, Korea National Oil Corporation). Weekly national average retail prices. Korean-language web form interface.",
        "extraction_method": ["Web scraping"],
        "products": ["Gasoline (Regular, RON 91)", "Diesel", "Kerosene"],
        "source_keys": ["kr_opinet_history_weekly"],
        "publishes_on": "Monday",
        "notes": "GET to establish session, then POST with form data; parses Korean-script HTML table headers. Date encoded as Korean week notation (e.g. 2014년03월1주). Price range KRW 500–5,000/L.",
    },
    {
        "fetcher_fn": "fetch_kr_opinet_daily",
        "country": "Korea, Rep.",
        "source_name": "Opinet Daily Chart Averages",
        "url": "https://www.opinet.co.kr/user/main/mainView.do",
        "description": "Official (Opinet, Korea National Oil Corporation). Daily national plus regional averages extracted from the homepage time-series chart JSON endpoint.",
        "extraction_method": ["Web scraping", "JSON endpoint"],
        "products": ["Gasoline (Regular, RON 91)", "Diesel", "LPG"],
        "source_keys": ["kr_opinet_daily_avg"],
        "publishes_on": "Daily",
        "notes": "Bootstraps a homepage session using the hidden opinet_key and calls /user/main/mainLineChartNewAjax.do with DIV_CD=D for each region. Captures National and regional daily averages.",
    },
    {
        "fetcher_fn": "fetch_kr_fuel_news_evidence",
        "country": "Korea, Rep.",
        "source_name": "Korea Fuel Price News (RSS)",
        "url": "https://www.opinet.co.kr",
        "description": "Track A news/article evidence for Korea fuel prices. RSS/Atom feed captured as raw evidence only.",
        "extraction_method": ["RSS/Atom"],
        "products": [],
        "source_keys": ["kr_fuel_price_news"],
        "publishes_on": "Daily or irregular",
        "notes": "Requires KOREA_FUEL_NEWS_RSS_URL env var pointing to a news feed. Records are stored as evidence only; not mixed into price observations.",
    },
]

import os
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import get_session, make_hash, make_template

_TMPL_KR = make_template(
    country="Korea, Rep.",
    wb_iso3="KOR",
    source_key="kr_opinet_history_weekly",
    source_name="Korea Opinet Oil Price History (Weekly National Average)",
    source_url="https://www.opinet.co.kr/user/doop/doopOilHistory.do",
    currency="KRW",
    unit="L",
    subnational_area="National",
    publication_frequency="weekly",
    observation_method="survey",
)

_TMPL_KR_DAILY = make_template(
    country="Korea, Rep.",
    wb_iso3="KOR",
    source_key="kr_opinet_daily_avg",
    source_name="Korea Opinet Daily Chart Averages",
    source_url="https://www.opinet.co.kr/user/main/mainView.do",
    currency="KRW",
    unit="L",
    subnational_area="National",
    publication_frequency="daily",
    observation_method="reported",
)

_KR_PRODUCT_COLS = [
    ("보통휘발유", "Regular Gasoline", "gasoline", "regular", 91),
    ("자동차용경유", "Diesel", "diesel", "regular", None),
    ("실내등유", "Kerosene", "kerosene", "regular", None),
]

_KR_OPINET_API_URL = "https://www.opinet.co.kr/api/avgRecentPrice.do"
_KR_OPINET_API_KEY_ENV = "OPINET_API_KEY"
_KR_OPINET_MAIN_URL = "https://www.opinet.co.kr/user/main/mainView.do"
_KR_OPINET_MAIN_CHART_URL = "https://www.opinet.co.kr/user/main/mainLineChartNewAjax.do"

_KR_OPINET_PRODUCT_CODES = {
    "B027": ("Regular Gasoline", "gasoline", "regular", 91),
    "D047": ("Diesel", "diesel", "regular", None),
    "K015": ("LPG", "lpg", "regular", None),
}

_KR_OPINET_PRODUCT_NAMES = {
    "휘발유": "B027",
    "보통휘발유": "B027",
    "경유": "D047",
    "자동차용경유": "D047",
    "LPG": "K015",
}

_KR_NEWS_RSS_ENV = "KOREA_FUEL_NEWS_RSS_URL"


def _parse_kr_week_date(period_str: str) -> date | None:
    """Parse '2014년03월1주' -> first day of that week-period within the month."""
    m = re.match(r"(\d{4})년\s*0?(\d{1,2})월\s*(\d)주", period_str.strip())
    if not m:
        return None
    year, month, week_num = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(year, month, (week_num - 1) * 7 + 1)
    except ValueError:
        return None


def _parse_kr_api_date(value: str | None) -> date | None:
    if not value:
        return None
    s = str(value).strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_kr_price(value) -> float | None:
    if value is None:
        return None
    text = str(value)
    match = re.findall(r"\d+[\d,]*(?:\.\d+)?", text)
    if not match:
        return None
    raw = match[-1].replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _bootstrap_kr_main_page(session) -> str | None:
    """Return Opinet main-page HTML after posting the hidden opinet_key."""
    try:
        landing = session.get(_KR_OPINET_MAIN_URL, timeout=30)
        landing.raise_for_status()
    except Exception as e:
        print(f"  [kr_opinet_daily] Landing page request failed: {e}")
        return None

    m = re.search(r"opinet_key\.value\s*=\s*'([^']+)'", landing.text)
    if not m:
        m = re.search(
            r'name=["\']opinet_key["\'][^>]*value=["\']([^"\']+)["\']',
            landing.text,
        )
    if not m:
        print("  [kr_opinet_daily] Could not find opinet_key on landing page")
        return None

    try:
        resp = session.post(
            _KR_OPINET_MAIN_URL, data={"opinet_key": m.group(1)}, timeout=30
        )
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"  [kr_opinet_daily] Main page bootstrap failed: {e}")
        return None


def _parse_kr_sido_codes(main_html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(main_html, "lxml")
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for div in soup.select("#all_img_map div[id^='m_']"):
        code_el = div.select_one(".accesskey")
        name_el = div.select_one(".title")
        if code_el is None or name_el is None:
            continue
        code = code_el.get_text(strip=True)
        name = name_el.get_text(strip=True)
        if not code or code in seen:
            continue
        seen.add(code)
        out.append((code, name))
    return out


def fetch_kr_opinet_weekly(cutoff: date) -> pd.DataFrame:
    """Fetch Korea Opinet weekly national average fuel prices from history page."""
    print("  [kr_opinet] Fetching Korea Opinet weekly data...")
    print(f"  [kr_opinet] Cutoff: {cutoff}")

    session = get_session()
    today = date.today()

    url = "https://www.opinet.co.kr/user/doop/doopOilHistory.do"
    try:
        session.get(url, headers={"Accept-Language": "ko-KR,ko;q=0.9"}, timeout=15)
    except Exception:
        pass

    start = cutoff + timedelta(days=1)
    post_data = [
        ("TERM", "W"),
        ("STA_Y", str(start.year)),
        ("STA_M", f"{start.month:02d}"),
        ("STA_W", str((start.day - 1) // 7 + 1)),
        ("END_Y", str(today.year)),
        ("END_M", f"{today.month:02d}"),
        ("END_W", str((today.day - 1) // 7 + 1)),
        ("OIL_CD_B027_P", "Y"),
        ("OIL_CD_D047_P", "Y"),
        ("OIL_CD_C004_P", "Y"),
    ]

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": url,
        "Origin": "https://www.opinet.co.kr",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }

    try:
        resp = session.post(url, data=post_data, headers=headers, timeout=60)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
    except Exception as e:
        print(f"  [kr_opinet] Request failed: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.text, "lxml")

    table = None
    for tbl in soup.find_all("table"):
        header_text = tbl.find("tr").get_text() if tbl.find("tr") else ""
        if "기간" in header_text:
            table = tbl
            break

    if table is None:
        print("  [kr_opinet] No price table found in response (check POST params)")
        return pd.DataFrame()

    rows = table.find_all("tr")

    col_map: dict[int, tuple] = {}
    for row in rows[:3]:
        cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
        for i, cell in enumerate(cells):
            for kr_name, prod_name, family, qg, ron in _KR_PRODUCT_COLS:
                if kr_name in cell:
                    col_map[i] = (prod_name, family, qg, ron)
        if col_map:
            break

    if not col_map:
        for i, (_, prod_name, family, qg, ron) in enumerate(_KR_PRODUCT_COLS):
            col_map[i + 1] = (prod_name, family, qg, ron)

    all_rows = []
    for row in rows:
        cells = [c.get_text(strip=True) for c in row.find_all("td")]
        if not cells or len(cells) < 2:
            continue

        obs_date = _parse_kr_week_date(cells[0])
        if obs_date is None or obs_date <= cutoff:
            continue

        for col_idx, (prod_name, family, qg, ron) in col_map.items():
            if col_idx >= len(cells):
                continue
            price_str = cells[col_idx].replace(",", "").strip()
            try:
                price = float(price_str)
            except ValueError:
                continue
            if not (500 <= price <= 5000):
                continue

            r = _TMPL_KR.copy()
            r.update(
                {
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "price_local": price,
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date + timedelta(days=6)),
                    "observation_date": str(obs_date),
                }
            )
            r["observation_hash"] = make_hash(r)
            all_rows.append(r)

    if all_rows:
        print(f"  [kr_opinet] {len(all_rows)} new rows")
    else:
        print("  [kr_opinet] No new rows (check POST parameters or page response)")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


def fetch_kr_opinet_daily(cutoff: date) -> pd.DataFrame:
    """Fetch Korea Opinet daily national + regional averages from chart JSON."""
    print("  [kr_opinet_daily] Fetching Korea Opinet daily chart averages...")
    print(f"  [kr_opinet_daily] Cutoff: {cutoff}")

    session = get_session()
    main_html = _bootstrap_kr_main_page(session)
    if not main_html:
        return pd.DataFrame()

    sidos = _parse_kr_sido_codes(main_html)
    if not sidos:
        print("  [kr_opinet_daily] No SIDO codes found on main page")
        return pd.DataFrame()

    rows = []
    seen_national: set[tuple[str, date]] = set()
    for sido_code, sido_name in sidos:
        for prod_code in ("B027", "D047", "K015"):
            spec = _KR_OPINET_PRODUCT_CODES.get(prod_code)
            if spec is None:
                continue
            try:
                resp = session.post(
                    _KR_OPINET_MAIN_CHART_URL,
                    data={"DIV_CD": "D", "SIDO_CD": sido_code, "KNOC_PD_CD": prod_code},
                    headers={
                        "X-Requested-With": "XMLHttpRequest",
                        "Referer": _KR_OPINET_MAIN_URL,
                        "Origin": "https://www.opinet.co.kr",
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                payload = resp.json()
            except Exception as e:
                print(
                    f"  [kr_opinet_daily] Chart request failed for {sido_name} {prod_code}: {e}"
                )
                continue

            items = payload.get("result", {}).get("chartData", [])
            if not isinstance(items, list):
                continue

            prod_label, family, qg, ron = spec
            for item in items:
                if not isinstance(item, dict):
                    continue
                obs_date = _parse_kr_api_date(
                    item.get("STD_DT_FULL") or item.get("STD_DT")
                )
                if obs_date is None or obs_date <= cutoff:
                    continue

                nat_price = _parse_kr_price(item.get("PRICE"))
                if nat_price is not None and 500 <= nat_price <= 5000:
                    nat_key = (prod_code, obs_date)
                    if nat_key not in seen_national:
                        row = _TMPL_KR_DAILY.copy()
                        row.update(
                            {
                                "fuel_family": family,
                                "fuel_product": prod_label,
                                "quality_group": qg,
                                "octane_ron": ron,
                                "subnational_area": "National",
                                "price_local": round(nat_price, 4),
                                "effective_from": str(obs_date),
                                "effective_to": str(obs_date),
                                "observation_date": str(obs_date),
                                "source_url": _KR_OPINET_MAIN_URL,
                                "notes": f"Opinet chart national average; SIDO query {sido_code}",
                            }
                        )
                        row["observation_hash"] = make_hash(row)
                        rows.append(row)
                        seen_national.add(nat_key)

                sido_price = _parse_kr_price(item.get("PRICE_SIDO"))
                if sido_price is None or not (500 <= sido_price <= 5000):
                    continue
                row = _TMPL_KR_DAILY.copy()
                row.update(
                    {
                        "fuel_family": family,
                        "fuel_product": prod_label,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "subnational_area": sido_name,
                        "price_local": round(sido_price, 4),
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date),
                        "observation_date": str(obs_date),
                        "source_url": _KR_OPINET_MAIN_URL,
                        "notes": f"Opinet chart regional average; SIDO_CD={sido_code}",
                    }
                )
                row["observation_hash"] = make_hash(row)
                rows.append(row)

    if rows:
        print(f"  [kr_opinet_daily] {len(rows)} new rows")
    else:
        print("  [kr_opinet_daily] No new rows")
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def fetch_kr_fuel_news_evidence(max_items: int = 50) -> list[dict]:
    """Fetch Korea fuel price news RSS/Atom metadata for Track A evidence."""
    feed_url = os.environ.get(_KR_NEWS_RSS_ENV)
    if not feed_url:
        print("  [kr_news] Missing KOREA_FUEL_NEWS_RSS_URL; skipping news evidence.")
        return []

    session = get_session()
    try:
        resp = session.get(feed_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [kr_news] Could not fetch RSS feed: {e}")
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"  [kr_news] RSS parse error: {e}")
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
                "country": "Korea, Rep.",
                "source_key": "kr_fuel_price_news",
                "source_name": "Korea Fuel Price News",
                "source_url": feed_url,
                "article_url": link or guid,
                "title": title,
                "published_date": pub_date,
                "summary": desc or None,
                "fetched_at": fetched_at,
                "evidence_type": "news_article",
            }
        )

    return records
