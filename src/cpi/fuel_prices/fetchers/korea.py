"""Korea Opinet weekly national average fuel price fetcher."""

import re
from datetime import date, timedelta

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

_KR_PRODUCT_COLS = [
    ("보통휘발유", "Regular Gasoline", "gasoline", "regular", 91),
    ("자동차용경유", "Diesel", "diesel", "regular", None),
    ("실내등유", "Kerosene", "kerosene", "regular", None),
]


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
