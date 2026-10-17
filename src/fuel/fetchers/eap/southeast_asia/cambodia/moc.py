"""Cambodia Ministry of Commerce fuel price notices.

Ported unchanged from legacy pacific-observatory
``src/cpi/fuel_prices/fetchers/cambodia.py::fetch_cambodia_moc`` (dev 2d60a353).
Legacy cadence is manual: the GraphQL endpoint answers 403 without a token.
"""

import re
import time
from datetime import date, timedelta

import pandas as pd
from bs4 import BeautifulSoup

from fuel.fetchers._shared.eap.legacy import get_session, make_hash, make_template

# ── Cambodia MOC fuel price notices (sequential news ID scan) ─────────────────

_TMPL_KH_MOC = make_template(
    country="Cambodia",
    wb_iso3="KHM",
    source_key="kh_moc_fuel_notices",
    source_name="Cambodia Ministry of Commerce Fuel Price Notices",
    source_url="https://moc.gov.kh/en-US/news/",
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
    news_langs = ["en-US", "kh"]
    consecutive_non_fuel = 0
    for notice_id in range(last_id + 1, last_id + 2000):
        if consecutive_non_fuel > 50:
            print(
                f"  [kh_moc] Stopping after 50 consecutive non-fuel pages at ID {notice_id}"
            )
            break

        page_url = None
        soup = None
        for lang in news_langs:
            url = f"https://moc.gov.kh/{lang}/news/{notice_id}"
            try:
                resp = session.get(url, timeout=15)
            except Exception:
                continue
            if resp.status_code == 200:
                page_url = url
                soup = BeautifulSoup(resp.content, "lxml")
                break
            if resp.status_code not in (404, 302):
                time.sleep(0.1)

        if soup is None:
            consecutive_non_fuel += 1
            time.sleep(0.05)
            continue

        try:
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
                                "source_url": page_url or url,
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
