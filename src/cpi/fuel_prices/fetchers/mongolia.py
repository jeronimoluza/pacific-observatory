"""Mongolia fuel price fetchers — NSO 1212.mn API and data.mn HTML."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_mn_nso_weekly_aimag",
        "country": "Mongolia",
        "source_name": "NSO 1212.mn Aimag Weekly Prices",
        "url": "https://data.1212.mn:443/api/v1/en/NSO/Economy, environment/Consumer Price Index/DT_NSO_0300_010V5.px",
        "description": "Official government statistics (Mongolia National Statistics Office). Open data portal (1212.mn) providing weekly fuel prices by aimag via a JSON-stat2 API. Subnational coverage across 21 provinces.",
        "extraction_method": "REST API (JSON-stat2)",
        "products": [
            "Petrol A-80 (Gasoline Regular)",
            "Petrol A-92 (Gasoline Regular)",
            "Diesel",
        ],
        "frequency": "Weekly",
        "output": "Secondary CSV",
        "notes": "POST request with JSON-stat2 payload; navigates dimensional structure to resolve (product × region × time) flat index. Price range MNT 1,000–10,000/L.",
    },
    {
        "fetcher_fn": "fetch_mn_nso_weekly_aimag",
        "country": "Mongolia",
        "source_name": "NSO 1212.mn Aimag Weekly Prices",
        "url": "https://data.1212.mn:443/api/v1/en/NSO/Economy, environment/Consumer Price Index/DT_NSO_0300_010V5.px",
        "description": "Official (Mongolia National Statistics Office). Open data portal (1212.mn) with weekly fuel prices by aimag via JSON-stat2 API. 21 provinces.",
        "extraction_method": ["REST API"],
        "products": [
            "Petrol A-80 (Gasoline Regular)",
            "Petrol A-92 (Gasoline Regular)",
            "Diesel",
        ],
        "source_keys": ["mn_nso_aimag_weekly_fuel"],
        "publishes_on": "Weekly",
        "notes": "POST request with JSON-stat2 payload; navigates dimensional (product × region × time) index. Price range MNT 1,000–10,000/L.",
    },
    {
        "fetcher_fn": "fetch_mongolia_data_mn",
        "country": "Mongolia",
        "source_name": "data.mn Weekly Prices",
        "url": "https://data.mn/en/data/weekly-gasoline-prices-aimags",
        "description": "Independent Mongolian open data platform (data.mn). Republishes NSO fuel prices as HTML tables. Aimag-level + Ulaanbaatar city.",
        "extraction_method": ["Web scraping"],
        "products": ["Petrol A-92 (Gasoline)", "Diesel", "Petrol A-80 (Gasoline)"],
        "source_keys": [
            "mn_data_mn_a92_aimags",
            "mn_data_mn_diesel_aimags",
            "mn_data_mn_fuel_ulaanbaatar",
        ],
        "publishes_on": "Weekly",
        "notes": "Scrapes three datasets: aimag gasoline, aimag diesel, and Ulaanbaatar fuel prices. Price range MNT 500–10,000/L.",
    },
]

import re
from datetime import date, timedelta

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import get_session, make_hash, make_template

# ── NSO 1212.mn Weekly Aimag Prices ───────────────────────────────────────────

_TMPL_MN_NSO = make_template(
    country="Mongolia",
    wb_iso3="MNG",
    source_key="mn_nso_aimag_weekly_fuel",
    source_name="NSC Mongolia Weekly Prices — 1212.mn",
    source_url="https://data.1212.mn/api/v1/en/NSO/Economy, environment/Consumer Price Index/DT_NSO_0300_010V5.px",
    currency="MNT",
    unit="L",
    publication_frequency="weekly",
    observation_method="survey",
)

_MN_NSO_PRODUCTS = {
    "1": ("Petrol A-80", "gasoline", "regular", None),
    "2": ("Petrol A-92", "gasoline", "regular", None),
    "4": ("Diesel", "diesel", "regular", None),
}

_MN_NSO_AIMAGS = {
    "183": "Bayan-Ulgii",
    "182": "Govi-Altai",
    "181": "Zavkhan",
    "185": "Uvs",
    "184": "Khovd",
    "265": "Arkhangai",
    "264": "Bayankhongor",
    "263": "Bulgan",
    "261": "Orkhon",
    "262": "Uvurkhangai",
    "267": "Khuvsgul",
    "342": "Govisumber",
    "345": "Darkhan-Uul",
    "344": "Dornogovi",
    "348": "Dundgovi",
    "346": "Umnugovi",
    "343": "Selenge",
    "341": "Tuv",
    "421": "Dornod",
    "422": "Sukhbaatar",
    "423": "Khentii",
}

_MN_NSO_API_URL = "https://data.1212.mn:443/api/v1/en/NSO/Economy, environment/Consumer Price Index/DT_NSO_0300_010V5.px"


def fetch_mn_nso_weekly_aimag(cutoff: date) -> pd.DataFrame:
    """Fetch Mongolia NSO weekly aimag-level fuel prices from 1212.mn API."""
    print("  [mn_nso] Fetching Mongolia NSO 1212.mn aimag weekly fuel data...")
    print(f"  [mn_nso] Cutoff: {cutoff}")

    session = get_session()
    payload = {
        "query": [
            {
                "code": "Бүтээгдэхүүн",
                "selection": {"filter": "item", "values": ["1", "2", "4"]},
            }
        ],
        "response": {"format": "json-stat2"},
    }

    try:
        resp = session.post(_MN_NSO_API_URL, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [mn_nso] API error: {e}")
        return pd.DataFrame()

    try:
        ids = data["id"]
        sizes = data["size"]
        dims = data["dimension"]
        values = data["value"]
    except KeyError as e:
        print(f"  [mn_nso] Unexpected response structure — missing key {e}")
        return pd.DataFrame()

    prod_dim = dims[ids[0]]
    reg_dim = dims[ids[1]]
    time_dim = dims[ids[2]]

    prod_cats = prod_dim["category"]
    reg_cats = reg_dim["category"]
    time_cats = time_dim["category"]

    prod_index = prod_cats["index"]
    reg_index = reg_cats["index"]
    time_index = time_cats["index"]
    time_label = time_cats.get("label", {})

    n_reg = sizes[1]
    n_time = sizes[2]

    all_rows = []
    for prod_code, (prod_name, family, qg, ron) in _MN_NSO_PRODUCTS.items():
        if prod_code not in prod_index:
            continue
        pi = prod_index[prod_code]

        for reg_code, aimag_name in _MN_NSO_AIMAGS.items():
            if reg_code not in reg_index:
                continue
            ri = reg_index[reg_code]

            for time_code, ti in time_index.items():
                flat_idx = pi * n_reg * n_time + ri * n_time + ti
                if flat_idx >= len(values):
                    continue
                price = values[flat_idx]
                if price is None:
                    continue

                date_str = time_label.get(time_code, time_code)
                try:
                    obs_date = date.fromisoformat(date_str)
                except ValueError:
                    continue

                if obs_date <= cutoff:
                    continue

                if not (1000 <= price <= 10000):
                    continue

                r = _TMPL_MN_NSO.copy()
                r.update(
                    {
                        "subnational_area": aimag_name,
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": float(price),
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date + timedelta(days=6)),
                        "observation_date": str(obs_date),
                    }
                )
                r["observation_hash"] = make_hash(r)
                all_rows.append(r)

    if all_rows:
        print(f"  [mn_nso] {len(all_rows)} new rows")
    else:
        print("  [mn_nso] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ── data.mn Weekly Prices ──────────────────────────────────────────────────────

_TMPL_MN_A92 = make_template(
    country="Mongolia",
    wb_iso3="MNG",
    source_key="mn_data_mn_a92_aimags",
    source_name="data.mn Mongolia Weekly Gasoline A-92 Prices by Aimag",
    source_url="https://data.mn/en/data/weekly-gasoline-prices-aimags",
    currency="MNT",
    unit="L",
    fuel_product="Petrol A-92",
    fuel_family="gasoline",
    quality_group="regular",
    publication_frequency="weekly",
    observation_method="survey",
)

_TMPL_MN_DIESEL = make_template(
    country="Mongolia",
    wb_iso3="MNG",
    source_key="mn_data_mn_diesel_aimags",
    source_name="data.mn Mongolia Weekly Diesel Prices by Aimag",
    source_url="https://data.mn/en/data/weekly-diesel-prices-aimags",
    currency="MNT",
    unit="L",
    fuel_product="Diesel",
    fuel_family="diesel",
    quality_group="regular",
    publication_frequency="weekly",
    observation_method="survey",
)

_TMPL_MN_UB = make_template(
    country="Mongolia",
    wb_iso3="MNG",
    source_key="mn_data_mn_fuel_ulaanbaatar",
    source_name="data.mn Mongolia Weekly Fuel Prices in Ulaanbaatar",
    source_url="https://data.mn/en/data/weekly-fuel-prices-ulaanbaatar",
    currency="MNT",
    unit="L",
    subnational_area="Ulaanbaatar",
    publication_frequency="weekly",
    observation_method="survey",
)

_UB_PRODUCTS = {
    "a-80": ("Petrol A-80", "gasoline", "regular", None),
    "a80": ("Petrol A-80", "gasoline", "regular", None),
    "a-92": ("Petrol A-92", "gasoline", "regular", None),
    "a92": ("Petrol A-92", "gasoline", "regular", None),
    "diesel": ("Diesel", "diesel", "regular", None),
}

_MN_DATA_SOURCES = [
    (
        "mn_data_mn_a92_aimags",
        "https://data.mn/en/data/weekly-gasoline-prices-aimags",
        _TMPL_MN_A92,
        "Petrol A-92",
        "gasoline",
        "regular",
        None,
    ),
    (
        "mn_data_mn_diesel_aimags",
        "https://data.mn/en/data/weekly-diesel-prices-aimags",
        _TMPL_MN_DIESEL,
        "Diesel",
        "diesel",
        "regular",
        None,
    ),
    (
        "mn_data_mn_fuel_ulaanbaatar",
        "https://data.mn/en/data/weekly-fuel-prices-ulaanbaatar",
        _TMPL_MN_UB,
        None,
        None,
        None,
        None,
    ),
]


def _parse_mn_date(date_str: str) -> date | None:
    for pat in [
        r"(20\d{2})[/\-](\d{2})[/\-](\d{2})",
        r"(\d{2})[/\-](\d{2})[/\-](20\d{2})",
    ]:
        m = re.match(pat, date_str)
        if m:
            try:
                if pat.startswith(r"(20"):
                    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                else:
                    return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                pass
    return None


def fetch_mongolia_data_mn(cutoff: date) -> pd.DataFrame:
    """Fetch Mongolia data.mn weekly fuel prices (three datasets)."""
    print("  [mn_data] Fetching Mongolia data.mn data...")
    print(f"  [mn_data] Cutoff: {cutoff}")

    session = get_session()
    all_rows = []

    for (
        source_key,
        url,
        tmpl,
        default_prod,
        default_family,
        default_qg,
        default_ron,
    ) in _MN_DATA_SOURCES:
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"  [mn_data] Could not fetch {url}: {e}")
            continue

        soup = BeautifulSoup(resp.content, "lxml")
        rows_added = 0

        for table in soup.find_all("table"):
            rows_html = table.find_all("tr")
            if len(rows_html) < 3:
                continue
            headers = [
                c.get_text(strip=True).lower()
                for c in rows_html[0].find_all(["th", "td"])
            ]

            date_col = next(
                (i for i, h in enumerate(headers) if "date" in h or "огноо" in h), None
            )
            if date_col is None:
                continue

            if source_key != "mn_data_mn_fuel_ulaanbaatar":
                price_col = None
                for i, h in enumerate(headers):
                    if i == date_col:
                        continue
                    if any(
                        kw in h for kw in ["national", "average", "улсын", "дундаж"]
                    ):
                        price_col = i
                        break
                if price_col is None:
                    price_col = max(
                        (i for i in range(len(headers)) if i != date_col), default=None
                    )
                if price_col is None:
                    continue

                for row in rows_html[1:]:
                    cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                    if len(cells) <= max(date_col, price_col):
                        continue
                    obs_date = _parse_mn_date(cells[date_col])
                    if obs_date is None or obs_date <= cutoff:
                        continue
                    try:
                        price = float(re.sub(r"[^0-9.]", "", cells[price_col]))
                        if not (500 <= price <= 10000):
                            continue
                    except (ValueError, TypeError):
                        continue

                    r = tmpl.copy()
                    r.update(
                        {
                            "fuel_family": default_family,
                            "fuel_product": default_prod,
                            "quality_group": default_qg,
                            "octane_ron": default_ron,
                            "price_local": price,
                            "effective_from": str(obs_date),
                            "effective_to": str(obs_date + timedelta(days=6)),
                            "observation_date": str(obs_date),
                            "source_url": url,
                        }
                    )
                    r["observation_hash"] = make_hash(r)
                    all_rows.append(r)
                    rows_added += 1

            else:
                prod_cols: dict[int, tuple] = {}
                for i, h in enumerate(headers):
                    if i == date_col:
                        continue
                    for key, meta in _UB_PRODUCTS.items():
                        if key in h:
                            prod_cols[i] = meta
                            break

                if not prod_cols:
                    continue

                for row in rows_html[1:]:
                    cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                    if not cells:
                        continue
                    obs_date = _parse_mn_date(
                        cells[date_col] if date_col < len(cells) else ""
                    )
                    if obs_date is None or obs_date <= cutoff:
                        continue

                    for col_idx, (prod_name, family, qg, ron) in prod_cols.items():
                        if col_idx >= len(cells):
                            continue
                        try:
                            price = float(re.sub(r"[^0-9.]", "", cells[col_idx]))
                            if not (500 <= price <= 10000):
                                continue
                        except (ValueError, TypeError):
                            continue
                        r = tmpl.copy()
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
                                "source_url": url,
                            }
                        )
                        r["observation_hash"] = make_hash(r)
                        all_rows.append(r)
                        rows_added += 1

        print(f"  [mn_data] {source_key}: {rows_added} new rows")

    if all_rows:
        print(f"  [mn_data] {len(all_rows)} new rows total")
    else:
        print("  [mn_data] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
