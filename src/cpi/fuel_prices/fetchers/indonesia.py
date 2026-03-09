"""Indonesia OTO.com monthly fuel price fetcher."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_id_oto",
        "country": "Indonesia",
        "source_name": "OTO.com Monthly Fuel Prices",
        "url": "https://www.oto.com/ajax/get-fuel-price-trends",
        "description": "Commercial portal (OTO.com) aggregating Pertamina official prices. Public JSON AJAX endpoint; reflects Pertamina state-enterprise retail rates.",
        "extraction_method": ["REST API"],
        "products": [
            "Pertalite (Gasoline Regular)",
            "Pertamax (Gasoline Premium)",
            "Pertamax Turbo (Gasoline Super Premium)",
            "Dexlite (Diesel Premium)",
            "Pertamina Dex (Diesel Super Premium)",
        ],
        "source_keys": ["id_oto_monthly_prices"],
        "publishes_on": "Monthly (1st of month)",
        "notes": "Public JSON API; no auth required. Fetches rolling 12-month + yearly data for 5 Pertamina fuel IDs. Price range IDR 3,000–30,000/L.",
    },
]

from datetime import date, datetime, timedelta

import pandas as pd

from ..utils import get_session, make_hash, make_template

_TMPL_ID = make_template(
    country="Indonesia",
    wb_iso3="IDN",
    source_key="id_oto_monthly_prices",
    source_name="OTO.com Indonesia Fuel Prices",
    source_url="https://www.oto.com/en/harga-bbm",
    currency="IDR",
    unit="L",
    subnational_area="National",
    publication_frequency="monthly",
    observation_method="survey",
)

_ID_OTO_PRODUCTS = [
    (1, "Pertalite", "gasoline", "regular", None),
    (2, "Pertamax Turbo", "gasoline", "super_premium", None),
    (3, "Pertamax", "gasoline", "premium", None),
    (4, "Dexlite", "diesel", "premium", None),
    (5, "Pertamina Dex", "diesel", "super_premium", None),
]

_ID_OTO_BASE_URL = "https://www.oto.com/ajax/get-fuel-price-trends"


def fetch_id_oto(cutoff: date) -> pd.DataFrame:
    """Fetch Indonesia fuel prices from OTO.com public JSON API (full refresh)."""
    print("  [id_oto] Fetching Indonesia OTO.com data (full refresh)...")

    session = get_session()
    all_rows = []

    for fuel_id, prod_name, family, qg, ron in _ID_OTO_PRODUCTS:
        rows_for_product: dict[date, tuple[float, date]] = {}
        monthly_years: set[int] = set()

        # Monthly data (rolling 12-month window)
        try:
            resp = session.get(
                _ID_OTO_BASE_URL,
                params={"fuelId": fuel_id, "input": "month", "categorySlug": "mobil"},
                timeout=15,
            )
        except Exception as e:
            print(f"  [id_oto] Request error (fuelId={fuel_id}, month): {e}")
            resp = None

        if resp is not None and resp.status_code == 200:
            try:
                items = resp.json()
            except Exception:
                items = []
            for item in items:
                text, value = item.get("text", ""), item.get("value", 0)
                try:
                    obs_date = datetime.strptime(text, "%b %y").date()
                    next_m = obs_date.replace(day=28) + timedelta(days=4)
                    eff_to = next_m - timedelta(days=next_m.day)
                except Exception:
                    continue
                if not (3000 <= value <= 30000):
                    continue
                rows_for_product[obs_date] = (float(value), eff_to)
                monthly_years.add(obs_date.year)

        # Yearly data — skip any year already covered by monthly entries
        try:
            resp = session.get(
                _ID_OTO_BASE_URL,
                params={"fuelId": fuel_id, "input": "year", "categorySlug": "mobil"},
                timeout=15,
            )
        except Exception as e:
            print(f"  [id_oto] Request error (fuelId={fuel_id}, year): {e}")
            resp = None

        if resp is not None and resp.status_code == 200:
            try:
                items = resp.json()
            except Exception:
                items = []
            for item in items:
                text, value = item.get("text", ""), item.get("value", 0)
                try:
                    year = int(text)
                    obs_date = date(year, 1, 1)
                    eff_to = date(year, 12, 31)
                except Exception:
                    continue
                if year in monthly_years:
                    continue
                if not (3000 <= value <= 30000):
                    continue
                rows_for_product[obs_date] = (float(value), eff_to)

        for obs_date, (price, eff_to) in sorted(rows_for_product.items()):
            if obs_date <= cutoff:
                continue
            r = _TMPL_ID.copy()
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
                    "source_url": _ID_OTO_BASE_URL,
                }
            )
            r["observation_hash"] = make_hash(r)
            all_rows.append(r)

    print(f"  [id_oto] {len(all_rows)} rows fetched (cutoff {cutoff})")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
