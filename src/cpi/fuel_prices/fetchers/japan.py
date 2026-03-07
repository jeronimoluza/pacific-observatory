"""Japan ANRE weekly petroleum price fetcher (local *s5.xlsx files)."""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from ..constants import JAPAN_DIR
from ..utils import make_hash, make_template

_TMPL_JP = make_template(
    country="Japan",
    wb_iso3="JPN",
    source_key="jp_anre_weekly_petroleum_2026",
    source_name="ANRE (Agency for Natural Resources and Energy) Weekly Petroleum Survey",
    source_url="https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/",
    currency="JPY",
    unit="L",
    subnational_area="National",
    publication_frequency="weekly",
    observation_method="survey",
)

# Sheet name -> (product label, fuel_family, quality_group, octane_ron, price_divisor)
# price_divisor=18 for kerosene sheets whose prices are per 18-litre can
_JP_S5_SHEETS = {
    "ハイオク": ("High-octane Gasoline", "gasoline", "premium", None, 1.0),
    "レギュラー": ("Regular Gasoline", "gasoline", "regular", None, 1.0),
    "軽油": ("Diesel", "diesel", "regular", None, 1.0),
    "灯油店頭": ("Kerosene (retail)", "kerosene", "regular", None, 18.0),
}


def _parse_anre_s5_xlsx(path: Path, cutoff: date) -> list[dict]:
    """Parse a local *s5.xlsx file.  Row 0 = header; col 1 = date; col 2 = national avg."""
    results = []
    try:
        xf = pd.ExcelFile(path)
    except Exception as e:
        print(f"  [jp_anre] Cannot open {path.name}: {e}")
        return results

    source_url = str(path)
    for sheet_name, (prod_name, family, qg, ron, divisor) in _JP_S5_SHEETS.items():
        if sheet_name not in xf.sheet_names:
            continue
        try:
            raw = pd.read_excel(path, sheet_name=sheet_name, header=None)
        except Exception as e:
            print(f"  [jp_anre] {path.name} sheet '{sheet_name}' error: {e}")
            continue

        # Row 0 is the header; data starts at row 1
        for _, row in raw.iloc[1:].iterrows():
            raw_date = row.iloc[1]
            raw_price = row.iloc[2]

            if pd.isna(raw_date):
                continue
            try:
                obs_date = pd.to_datetime(raw_date).date()
            except Exception:
                continue

            if obs_date <= cutoff:
                continue

            if pd.isna(raw_price):
                continue
            try:
                price = float(raw_price) / divisor
            except Exception:
                continue

            if family == "kerosene":
                if not (50 <= price <= 300):
                    continue
            else:
                if not (80 <= price <= 500):
                    continue

            r = _TMPL_JP.copy()
            r.update(
                {
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "price_local": round(price, 2),
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date + timedelta(days=6)),
                    "observation_date": str(obs_date),
                    "source_url": source_url,
                }
            )
            results.append(r)

    return results


def fetch_jp_anre_excel(cutoff: date) -> pd.DataFrame:
    """Read Japan ANRE weekly data from local *s5.xlsx files in japan_prices/."""
    print("  [jp_anre] Reading Japan ANRE data from local files...")
    print(f"  [jp_anre] Cutoff: {cutoff}")

    japan_dir = JAPAN_DIR
    if not japan_dir.exists():
        print(f"  [jp_anre] Directory not found: {japan_dir}")
        return pd.DataFrame()

    s5_files = sorted(japan_dir.glob("*s5.xlsx"))
    if not s5_files:
        print("  [jp_anre] No *s5.xlsx files found in japan_prices/")
        return pd.DataFrame()

    all_rows = []
    for f in s5_files:
        parsed = _parse_anre_s5_xlsx(f, cutoff)
        if parsed:
            all_rows.extend(parsed)
            print(f"  [jp_anre] {f.name}: {len(parsed)} new rows")
        else:
            print(f"  [jp_anre] {f.name}: no new rows past cutoff")

    if all_rows:
        for r in all_rows:
            r["observation_hash"] = make_hash(r)
        print(f"  [jp_anre] Total: {len(all_rows)} new rows")
    else:
        print("  [jp_anre] No new rows")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
