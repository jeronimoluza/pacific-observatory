"""Cambodia fuel price fetchers: PTT Cambodia (canonical) + MOC notices."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_kh_ptt",
        "country": "Cambodia",
        "source_name": "PTT Cambodia Monthly Prices",
        "url": "https://www.ptt.com.kh/products-and-services-oil-price",
        "description": "PTT Cambodia (subsidiary of Thailand's state-owned PTT Group). Monthly retail pump prices as HTML tables.",
        "extraction_method": ["Web scraping"],
        "products": ["Gasoline (Super/Premium)", "Gasoline (Regular)", "Diesel"],
        "source_keys": ["kh_ptt_monthly_prices"],
        "publishes_on": "Monthly (start of month)",
        "notes": "Iterates year-by-year; parses HTML price tables with multiple date-format fallbacks. Price range KHR 2,000–8,000/L.",
    },
    {
        "fetcher_fn": "fetch_cambodia_moc",
        "country": "Cambodia",
        "source_name": "Ministry of Commerce Fuel Notices",
        "url": "https://moc.gov.kh/kh/news/",
        "description": "Official government (Cambodia Ministry of Commerce). Biweekly fuel price notices as news articles in Khmer script.",
        "extraction_method": ["Web scraping"],
        "products": ["Gasoline (Regular)", "Diesel"],
        "source_keys": ["kh_moc_fuel_notices"],
        "publishes_on": "Biweekly",
        "notes": "Sequential scan of news article IDs from hardcoded ID 3035; detects fuel articles via Khmer-script keywords. Price range KHR 2,500–6,500/L.",
    },
]

import re
import time
from datetime import date, timedelta

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import MONTH_MAP_EN, get_session, make_hash, make_template

# ── PTT Cambodia monthly prices (canonical) ──────────────────────────────────

_TMPL_KH_PTT = make_template(
    country="Cambodia",
    wb_iso3="KHM",
    source_key="kh_ptt_monthly_prices",
    source_name="PTT Cambodia",
    source_url="https://www.ptt.com.kh/products-and-services-oil-price",
    currency="KHR",
    unit="L",
    publication_frequency="monthly",
)

_KH_PRODUCTS = [
    ("super", "Super", "gasoline", "premium", None),
    ("regular", "Regular", "gasoline", "regular", None),
    ("diesel", "Diesel", "diesel", "regular", None),
]


def fetch_kh_ptt(cutoff: date) -> pd.DataFrame:
    """Fetch Cambodia PTT monthly oil prices from ptt.com.kh."""
    print("  [kh_ptt] Fetching Cambodia PTT data...")
    print(f"  [kh_ptt] Cutoff: {cutoff}")

    session = get_session()
    today = date.today()
    all_rows = []

    for year in range(max(cutoff.year, 2019), today.year + 1):
        url = f"https://www.ptt.com.kh/products-and-services-oil-price?months=0&year={year}"
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code != 200:
                print(f"  [kh_ptt] HTTP {resp.status_code} for year {year}")
                continue
        except Exception as e:
            print(f"  [kh_ptt] Fetch error year {year}: {e}")
            continue

        soup = BeautifulSoup(resp.content, "lxml")
        for table in soup.find_all("table"):
            rows_html = table.find_all("tr")
            if len(rows_html) < 3:
                continue

            header_cells = rows_html[0].find_all(["th", "td"])
            headers = [c.get_text(strip=True).lower() for c in header_cells]

            date_col = next(
                (i for i, h in enumerate(headers) if "date" in h or "month" in h),
                0 if headers else None,
            )
            if date_col is None:
                continue

            prod_cols: dict[int, tuple] = {}
            for ci, h in enumerate(headers):
                if ci == date_col:
                    continue
                for key, prod_name, family, qg, ron in _KH_PRODUCTS:
                    if key in h:
                        prod_cols[ci] = (prod_name, family, qg, ron)
                        break

            if not prod_cols:
                non_date = [i for i in range(len(headers)) if i != date_col]
                for ci, (key, prod_name, family, qg, ron) in zip(
                    non_date, _KH_PRODUCTS
                ):
                    prod_cols[ci] = (prod_name, family, qg, ron)

            for row in rows_html[1:]:
                cells = row.find_all(["th", "td"])
                if len(cells) <= date_col:
                    continue
                texts = [c.get_text(strip=True) for c in cells]
                date_str = texts[date_col] if date_col < len(texts) else ""

                obs_date = None
                for pat, parse_fn in [
                    (
                        r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})",
                        lambda m: date(
                            int(m.group(1)), int(m.group(2)), int(m.group(3))
                        ),
                    ),
                    (
                        r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
                        lambda m: date(
                            int(m.group(3)), int(m.group(2)), int(m.group(1))
                        ),
                    ),
                ]:
                    m = re.search(pat, date_str)
                    if m:
                        try:
                            obs_date = parse_fn(m)
                            break
                        except ValueError:
                            pass

                if obs_date is None:
                    m = re.match(r"([A-Za-z]{3})-(\d{1,2})-(\d{4})", date_str)
                    if m:
                        try:
                            obs_date = date(
                                int(m.group(3)),
                                MONTH_MAP_EN[m.group(1).lower()],
                                int(m.group(2)),
                            )
                        except (ValueError, KeyError):
                            pass

                if obs_date is None:
                    for mo_name, mo_num in MONTH_MAP_EN.items():
                        if mo_name in date_str.lower():
                            y_m = re.search(r"\b(\d{4})\b", date_str)
                            if y_m:
                                try:
                                    obs_date = date(int(y_m.group(1)), mo_num, 1)
                                    break
                                except ValueError:
                                    pass

                if obs_date is None or obs_date <= cutoff:
                    continue

                for ci, (prod_name, family, qg, ron) in prod_cols.items():
                    if ci >= len(texts):
                        continue
                    try:
                        price = float(re.sub(r"[^0-9.]", "", texts[ci]))
                        if not (2000 <= price <= 8000):
                            continue
                    except (ValueError, TypeError):
                        continue

                    r = _TMPL_KH_PTT.copy()
                    r.update(
                        {
                            "fuel_family": family,
                            "fuel_product": prod_name,
                            "quality_group": qg,
                            "octane_ron": ron,
                            "price_local": price,
                            "effective_from": str(obs_date),
                            "effective_to": str(obs_date),
                            "observation_date": str(obs_date),
                            "source_url": url,
                        }
                    )
                    r["observation_hash"] = make_hash(r)
                    all_rows.append(r)

        time.sleep(0.5)

    if all_rows:
        print(f"  [kh_ptt] {len(all_rows)} new rows")
    else:
        print("  [kh_ptt] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ── Cambodia MOC fuel price notices (sequential news ID scan) ─────────────────

_TMPL_KH_MOC = make_template(
    country="Cambodia",
    wb_iso3="KHM",
    source_key="kh_moc_fuel_notices",
    source_name="Cambodia Ministry of Commerce Fuel Price Notices",
    source_url="https://moc.gov.kh/",
    currency="KHR",
    unit="L",
    publication_frequency="biweekly",
    observation_method="reported",
)


def fetch_cambodia_moc(cutoff: date) -> pd.DataFrame:
    """Fetch Cambodia MOC fuel prices via sequential news ID scan."""
    print("  [kh_moc] Fetching Cambodia MOC data...")
    print(f"  [kh_moc] Cutoff: {cutoff}")

    session = get_session()
    all_rows = []
    today = date.today()

    graphql_url = "https://graphql.moc.gov.kh/graphql"
    gql_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "apollo-require-preflight": "true",
        "Referer": "https://moc.gov.kh/commodity-values",
        "Origin": "https://moc.gov.kh",
    }
    try:
        introspect = {"query": "{ __schema { queryType { fields { name } } } }"}
        r = session.post(graphql_url, json=introspect, headers=gql_headers, timeout=10)
        if r.status_code == 200 and "data" in r.text:
            print("  [kh_moc] GraphQL accessible — introspection succeeded")
        else:
            print(
                f"  [kh_moc] GraphQL: HTTP {r.status_code} (requires auth or unavailable)"
            )
    except Exception as e:
        print(f"  [kh_moc] GraphQL error: {e}")

    last_id = 3035
    consecutive_non_fuel = 0
    for notice_id in range(last_id + 1, last_id + 2000):
        if consecutive_non_fuel > 50:
            print(
                f"  [kh_moc] Stopping after 50 consecutive non-fuel pages at ID {notice_id}"
            )
            break

        url = f"https://moc.gov.kh/kh/news/{notice_id}"
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code in (404, 302):
                consecutive_non_fuel += 1
                time.sleep(0.05)
                continue
            if resp.status_code != 200:
                consecutive_non_fuel += 1
                time.sleep(0.2)
                continue

            soup = BeautifulSoup(resp.content, "lxml")
            text = soup.get_text(separator="\n")

            is_fuel_notice = (
                ("ប្រេង" in text and "ថ្លៃ" in text)
                or "ឥន្ធនៈ" in text
                or ("diesel" in text.lower() and any(c.isdigit() for c in text))
            )

            if not is_fuel_notice:
                consecutive_non_fuel += 1
                time.sleep(0.05)
                continue

            consecutive_non_fuel = 0

            eff_from = None
            eff_to = None
            iso_matches = re.findall(r"(20\d{2})[/\-](\d{2})[/\-](\d{2})", text)
            dmy_matches = re.findall(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", text)

            if iso_matches:
                dates = []
                for y, mo, d in iso_matches:
                    try:
                        dates.append(date(int(y), int(mo), int(d)))
                    except ValueError:
                        pass
                if dates:
                    eff_from, eff_to = min(dates), max(dates)
            elif dmy_matches:
                dates = []
                for g1, g2, y in dmy_matches:
                    try:
                        dates.append(date(int(y), int(g2), int(g1)))
                    except ValueError:
                        try:
                            dates.append(date(int(y), int(g1), int(g2)))
                        except ValueError:
                            pass
                if dates:
                    eff_from, eff_to = min(dates), max(dates)

            if eff_from is None or eff_from <= cutoff:
                if eff_from is not None:
                    consecutive_non_fuel += 1
                continue

            if eff_to is None or eff_to < eff_from:
                eff_to = eff_from + timedelta(days=9)

            price_candidates = sorted(
                {
                    int(p)
                    for p in re.findall(r"\b(\d{4})\b", text)
                    if 2500 <= int(p) <= 6500
                }
            )

            if not price_candidates:
                consecutive_non_fuel += 1
                continue

            diesel_price = None
            gas_price = None

            diesel_m = re.search(r"ម៉ាស៊ូត[^\d]{0,50}(\d{4})", text)
            gas_m = re.search(r"សាំងធម្មតា[^\d]{0,50}(\d{4})", text)

            if diesel_m and 2500 <= int(diesel_m.group(1)) <= 6500:
                diesel_price = float(diesel_m.group(1))
            if gas_m and 2500 <= int(gas_m.group(1)) <= 6500:
                gas_price = float(gas_m.group(1))

            if diesel_price is None and price_candidates:
                diesel_price = float(price_candidates[0])
            if gas_price is None and len(price_candidates) >= 2:
                gas_price = float(price_candidates[1])

            products = []
            if diesel_price:
                products.append(("Diesel", "diesel", "regular", None, diesel_price))
            if gas_price and gas_price != diesel_price:
                products.append(
                    ("Regular Gasoline", "gasoline", "regular", None, gas_price)
                )

            if not products:
                continue

            rows_added = 0
            for prod_name, family, qg, ron, price in products:
                d = eff_from
                while d <= min(eff_to, today):
                    if d > cutoff:
                        r = _TMPL_KH_MOC.copy()
                        r.update(
                            {
                                "fuel_family": family,
                                "fuel_product": prod_name,
                                "quality_group": qg,
                                "octane_ron": ron,
                                "price_local": price,
                                "effective_from": str(eff_from),
                                "effective_to": str(eff_to),
                                "observation_date": str(d),
                                "source_url": url,
                            }
                        )
                        r["observation_hash"] = make_hash(r)
                        all_rows.append(r)
                        rows_added += 1
                    d += timedelta(days=1)

            if rows_added:
                print(
                    f"  [kh_moc] ID {notice_id}: {eff_from}–{eff_to}, {len(products)} products, {rows_added} rows"
                )

        except Exception as e:
            print(f"  [kh_moc] ID {notice_id}: error: {e}")
            consecutive_non_fuel += 1

        time.sleep(0.15)

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
