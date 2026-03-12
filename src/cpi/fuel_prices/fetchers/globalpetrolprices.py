"""GlobalPetrolPrices (GPP) daily snapshot fetcher.

This module intentionally writes a separate daily snapshot CSV (not the canonical
fuel_prices schema) so we can use GPP as a lightweight benchmark series without
mixing it into the reconstructed EAP fuel tables.

Run:
    poetry run python -m src.cpi.fuel_prices.fetchers.globalpetrolprices

If Playwright browsers are missing:
    poetry run playwright install chromium
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import html as _html
import re

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class Country:
    slug: str
    name: str
    iso2: str
    iso3: str


def _read_countries(path: Path) -> list[Country]:
    df = pd.read_csv(path)
    out: list[Country] = []
    for _, r in df.iterrows():
        out.append(
            Country(
                slug=str(r["slug"]).strip(),
                name=str(r["name"]).strip(),
                iso2=str(r["iso2"]).strip(),
                iso3=str(r["iso3"]).strip(),
            )
        )
    return out


def _slugify_gpp(name: str) -> str:
    # GPP uses title-case English names with spaces replaced by hyphens.
    # Some countries use a different common name (handled in _GPP_SLUG_OVERRIDES).
    s = name.strip()
    s = s.replace(",", "")
    s = s.replace("  ", " ")
    s = s.replace(" ", "-")
    return s


_GPP_SLUG_OVERRIDES: dict[str, list[str]] = {
    # Our name -> candidate slugs (tried in order)
    "Korea, Rep.": ["South-Korea"],
    "South Korea": ["South-Korea"],
    "Viet Nam": ["Vietnam"],
    "Papua New Guinea": ["Papua-New-Guinea"],
    "New Zealand": ["New-Zealand"],
    "Myanmar": ["Burma-Myanmar"],
}


def _candidate_slugs(country_name: str) -> list[str]:
    cands: list[str] = []
    cands.extend(_GPP_SLUG_OVERRIDES.get(country_name, []))
    cands.append(_slugify_gpp(country_name))
    # Deduplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for c in cands:
        if c and c not in seen:
            out.append(c)
            seen.add(c)
    return out


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(s: str) -> str:
    return _html.unescape(_TAG_RE.sub("", s or "")).strip()


def _to_float(v: str | None) -> float | None:
    if v is None:
        return None
    s = _strip_tags(str(v)).replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _parse_gpp_fuels_table(html: str) -> list[dict]:
    """Parse the first 'Fuels, price per liter' table using regex.

    We avoid pandas.read_html() to keep this fetcher dependency-light.
    """
    # The fuel table is a <table> containing a header cell:
    #   <td class="tableTitleBar">Fuels, price per liter</td>
    m = re.search(
        r"<table[^>]*>\s*<thead>.*?"
        r"<td[^>]*tableTitleBar[^>]*>\s*Fuels,\s*price\s*per\s*liter\s*</td>"
        r".*?</table>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return []
    table_html = m.group(0)

    header_row_match = re.search(
        r"<thead>.*?<tr>(.*?)</tr>.*?</thead>",
        table_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not header_row_match:
        return []
    header_tds = re.findall(
        r"<td[^>]*>(.*?)</td>",
        header_row_match.group(1),
        flags=re.IGNORECASE | re.DOTALL,
    )
    header_tds = [_strip_tags(x) for x in header_tds]
    if len(header_tds) < 4:
        return []
    currency = header_tds[2].strip() or None
    if not currency:
        return []

    tbody_match = re.search(
        r"<tbody>(.*?)</tbody>", table_html, flags=re.IGNORECASE | re.DOTALL
    )
    if not tbody_match:
        return []
    tbody_html = tbody_match.group(1)

    out: list[dict] = []
    for tr in re.findall(
        r"<tr>(.*?)</tr>", tbody_html, flags=re.IGNORECASE | re.DOTALL
    ):
        fuel_a = re.search(
            r"<a[^>]*class=\"indicatorName\"[^>]*>(.*?)</a>",
            tr,
            flags=re.IGNORECASE | re.DOTALL,
        )
        fuel_label = _strip_tags(fuel_a.group(1)) if fuel_a else None
        if not fuel_label:
            continue

        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.IGNORECASE | re.DOTALL)
        if len(tds) < 3:
            continue

        date_raw = _strip_tags(tds[0])
        try:
            price_date = datetime.strptime(date_raw, "%d.%m.%Y").date().isoformat()
        except Exception:
            price_date = None

        price_local = _to_float(tds[1])
        price_usd = _to_float(tds[2])
        if price_local is None and price_usd is None:
            continue

        out.append(
            {
                "fuel_label": fuel_label,
                "price_date": price_date,
                "currency": currency,
                "price_local": price_local,
                "price_usd": price_usd,
            }
        )

    return out


def fetch_gpp_snapshot(
    countries: Iterable[Country],
    *,
    out_path: Path,
    headless: bool = True,
    timeout_ms: int = 60_000,
) -> pd.DataFrame:
    """Fetch a 'today' snapshot for all provided countries.

    'today' refers to scrape date; GPP's own weekly date is stored as price_date.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        raise RuntimeError(
            "Playwright is not available in this environment. "
            "Install deps and/or run: poetry run playwright install chromium"
        ) from e

    scrape_date = date.today().isoformat()
    scrape_ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    rows: list[dict] = []
    missing: list[str] = []

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        for c in countries:
            found = False
            for slug in _candidate_slugs(c.name):
                url = f"https://www.globalpetrolprices.com/{slug}/"
                try:
                    resp = page.goto(
                        url, wait_until="domcontentloaded", timeout=timeout_ms
                    )
                    status = resp.status if resp is not None else None
                    if status == 404:
                        continue
                    page.wait_for_timeout(250)
                    html = page.content()
                except Exception:
                    continue

                fuels = _parse_gpp_fuels_table(html)
                if not fuels:
                    continue

                for r in fuels:
                    fuel_label = r["fuel_label"].lower()
                    if "gasoline" in fuel_label:
                        fuel = "gasoline"
                    elif "diesel" in fuel_label:
                        fuel = "diesel"
                    else:
                        # keep others (lpg/kerosene) but label them explicitly
                        fuel = r["fuel_label"].strip()

                    rows.append(
                        {
                            "scrape_date": scrape_date,
                            "scrape_ts": scrape_ts,
                            "country": c.name,
                            "iso3": c.iso3,
                            "gpp_slug": slug,
                            "fuel": fuel,
                            "price_local": r["price_local"],
                            "currency": r["currency"],
                            "unit": "L",
                            "price_usd": r["price_usd"],
                            "price_date": r["price_date"],
                            "source_url": url,
                        }
                    )

                found = True
                break

            if not found:
                missing.append(f"{c.name} ({c.iso3})")

        browser.close()

    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)

    if missing:
        miss_path = out_path.with_suffix(".missing.txt")
        miss_path.write_text("\n".join(missing) + "\n", encoding="utf-8")

    return df


def _default_out_path(today: str) -> Path:
    return (
        PROJECT_ROOT
        / "data"
        / "cpi"
        / "fuel_prices"
        / "snapshots"
        / f"gpp_daily_snapshot_{today}.csv"
    )


def main() -> int:
    ap = argparse.ArgumentParser(prog="gpp-snapshot")
    ap.add_argument(
        "--countries",
        type=Path,
        default=PROJECT_ROOT / "data" / "cpi" / "_countries.csv",
        help="Path to data/cpi/_countries.csv",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output CSV path (default: data/cpi/fuel_prices/snapshots/gpp_daily_snapshot_<today>.csv)",
    )
    ap.add_argument("--headed", action="store_true", help="Run browser headed")
    args = ap.parse_args()

    today = date.today().isoformat()
    out_path = args.out or _default_out_path(today)
    countries = _read_countries(args.countries)

    df = fetch_gpp_snapshot(countries, out_path=out_path, headless=not args.headed)

    # Verification print: gasoline + diesel rows only, wide per country.
    if not df.empty:
        core = df[df["fuel"].isin(["gasoline", "diesel"])].copy()
        if not core.empty:
            core["value"] = core.apply(
                lambda r: (
                    f"{r['price_local']} {r['currency']}/L (gpp_date {r['price_date']})"
                ),
                axis=1,
            )
            wide = (
                core.pivot_table(
                    index=["country", "iso3"],
                    columns="fuel",
                    values="value",
                    aggfunc="first",
                )
                .reset_index()
                .sort_values(["country", "iso3"])
            )
            print(wide.to_markdown(index=False))

    print(f"\nSaved snapshot: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
