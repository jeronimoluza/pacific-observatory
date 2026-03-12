"""Japan ANRE weekly petroleum price fetcher (Playwright downloads *s5.xlsx)."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_jp_anre_excel",
        "country": "Japan",
        "source_name": "ANRE/METI Weekly Petroleum Survey",
        "url": "https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/",
        "description": "Official government (ANRE/METI). Weekly national average retail prices published as Excel files. Fetcher downloads latest *s5.xlsx via Playwright.",
        "extraction_method": ["Playwright", "Excel download"],
        "products": [
            "Gasoline (High-Octane/Premium)",
            "Gasoline (Regular)",
            "Diesel",
            "Kerosene",
        ],
        "source_keys": ["jp_anre_weekly_petroleum_2026"],
        "publishes_on": "Wednesday 14:00 (JST)",
        "notes": "Excel files (*s5.xlsx) are downloaded automatically into data/cpi/fuel_prices/japan_prices/. Kerosene price is per 18L can, divided by 18. Encuestas los lunes, publicacion los miercoles 14:00 (JST).",
    },
]

from datetime import date, timedelta
from pathlib import Path
import re
from urllib.parse import urljoin

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


def _parse_anre_s5_xlsx(path: Path, cutoff: date, source_url: str | None) -> list[dict]:
    """Parse a local *s5.xlsx file.  Row 0 = header; col 1 = date; col 2 = national avg."""
    results = []
    try:
        xf = pd.ExcelFile(path)
    except Exception as e:
        print(f"  [jp_anre] Cannot open {path.name}: {e}")
        return results

    source_ref = source_url or str(path)
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
                    "source_url": source_ref,
                }
            )
            results.append(r)

    return results


def _parse_s5_filename_date(name: str) -> date | None:
    stem = Path(name).stem
    if len(stem) < 6:
        return None
    try:
        yy = int(stem[:2])
        mm = int(stem[2:4])
        dd = int(stem[4:6])
        year = 2000 + yy
        return date(year, mm, dd)
    except Exception:
        return None


def _download_latest_s5_files(cutoff: date) -> dict[str, str]:
    """Download recent *s5.xlsx files via Playwright; return filename->url map."""
    print("  [jp_anre] Checking ANRE site via Playwright...")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"  [jp_anre] Playwright not available: {e}")
        return {}

    japan_dir = JAPAN_DIR
    japan_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        request = p.request.new_context()
        links: list[tuple[str, str]] = []
        direct_base = (
            "https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/xlsx/"
        )
        today = date.today()
        probe_start = max(cutoff + timedelta(days=1), today - timedelta(days=45))
        probe_dates = [
            probe_start + timedelta(days=i)
            for i in range((today - probe_start).days + 1)
        ]
        for d in probe_dates:
            fname = f"{d:%y%m%d}s5.xlsx"
            url = f"{direct_base}{fname}"
            try:
                resp = request.get(url, timeout=30_000)
            except Exception:
                continue
            if resp.ok:
                links.append((fname, url))

        if not links:
            try:
                resp = request.get(
                    "https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/",
                    timeout=120_000,
                )
                if resp.ok:
                    html = resp.text()
                    hrefs = re.findall(r'href=["\']([^"\']*s5\.xlsx[^"\']*)', html)
                    for href in hrefs:
                        url = urljoin(
                            "https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/",
                            href,
                        )
                        filename = Path(url).name
                        links.append((filename, url))
            except Exception as e:
                print(f"  [jp_anre] Request error: {e}")

        browser = None
        if not links:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(
                    "https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/",
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )
                page.wait_for_timeout(3_000)
                hrefs = page.eval_on_selector_all(
                    "a[href]",
                    "els => els.map(e => e.getAttribute('href')).filter(Boolean)",
                )
                for href in hrefs:
                    if "s5.xlsx" not in href:
                        continue
                    url = urljoin(
                        "https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/",
                        href,
                    )
                    filename = Path(url).name
                    links.append((filename, url))
            except Exception as e:
                print(f"  [jp_anre] Page load error: {e}")
            if browser is not None:
                browser.close()

        if not links:
            print("  [jp_anre] No *s5.xlsx links found")
            return {}

        target_links = []
        for filename, url in links:
            fdate = _parse_s5_filename_date(filename)
            if fdate and fdate > cutoff:
                target_links.append((filename, url))

        if not target_links:
            latest = None
            for filename, url in links:
                fdate = _parse_s5_filename_date(filename)
                if not fdate:
                    continue
                if latest is None or fdate > latest[0]:
                    latest = (fdate, filename, url)
            if latest:
                target_links = [(latest[1], latest[2])]

        if not target_links:
            print("  [jp_anre] No dated *s5.xlsx links to download")
            return {}

        download_map: dict[str, str] = {}
        for filename, url in target_links:
            out_path = JAPAN_DIR / filename
            if out_path.exists():
                download_map[filename] = url
                continue
            try:
                resp = request.get(url, timeout=60_000)
            except Exception as e:
                print(f"  [jp_anre] Download error {url}: {e}")
                continue
            if not resp.ok:
                print(f"  [jp_anre] Download failed {url}: {resp.status}")
                continue
            try:
                out_path.write_bytes(resp.body())
                download_map[filename] = url
                print(f"  [jp_anre] Downloaded {filename}")
            except Exception as e:
                print(f"  [jp_anre] Write error {filename}: {e}")

        return download_map


def fetch_jp_anre_excel(cutoff: date) -> pd.DataFrame:
    """Fetch Japan ANRE weekly data via Playwright and local *s5.xlsx files."""
    print("  [jp_anre] Fetching Japan ANRE data (Playwright)...")
    print(f"  [jp_anre] Cutoff: {cutoff}")

    download_map = _download_latest_s5_files(cutoff)

    japan_dir = JAPAN_DIR
    japan_dir.mkdir(parents=True, exist_ok=True)

    s5_files = sorted(japan_dir.glob("*s5.xlsx"))
    if not s5_files:
        print("  [jp_anre] No *s5.xlsx files found in japan_prices/")
        return pd.DataFrame()

    all_rows = []
    for f in s5_files:
        source_url = download_map.get(f.name)
        parsed = _parse_anre_s5_xlsx(f, cutoff, source_url)
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
