"""Parallel-market FX in publish: two Excel sheets and a dashboard section.

USD prices on the dashboard stay on the official rate. Where the World Bank
RTFX panel has a parallel (unofficial) rate for a country, this adds:

- ``usd_parallel`` sheet: iso3, fuel_family, units + one column per date, USD/L
  at the parallel rate;
- ``fx_parallel`` sheet: monthly official vs parallel rate and the premium;
- a table on the dashboard with the latest official vs parallel USD/L.
"""

from __future__ import annotations

import html
from datetime import date, timedelta

import pandas as pd

_SECTION_ID = "parallel-fx"


def _family_frames(countries: list[dict], history_years: int) -> pd.DataFrame:
    cutoff = (date.today() - timedelta(days=365 * history_years)).isoformat()
    frames = []
    for c in countries:
        path = c["output_dir"] / "fuel_family_usd_prices.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path, low_memory=False)
        if "price_usd_parallel" not in df.columns:
            continue
        df = df[df["price_usd_parallel"].notna() & (df["observation_date"] >= cutoff)]
        if not df.empty:
            frames.append(df.assign(iso3=df["iso3"].fillna(c.get("iso3", ""))))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def parallel_sheets(
    countries: list[dict], history_years: int
) -> dict[str, pd.DataFrame]:
    fam = _family_frames(countries, history_years)
    if fam.empty:
        return {}
    wide = (
        fam.assign(units="USD/L (parallel rate)")
        .pivot_table(
            index=["iso3", "fuel_family", "units"],
            columns="observation_date",
            values="price_usd_parallel",
        )
        .reset_index()
        .sort_values(["iso3", "fuel_family"])
    )
    fam["month"] = fam["observation_date"].str[:7]
    rates = (
        fam.groupby(["iso3", "currency", "month"], as_index=False)
        .agg(
            official_rate=("fx_rate", "mean"),
            parallel_rate=("fx_rate_parallel", "first"),
        )
        .sort_values(["iso3", "month"])
    )
    rates["parallel_premium_pct"] = (
        (rates["parallel_rate"] / rates["official_rate"] - 1) * 100
    ).round(1)
    return {"usd_parallel": wide, "fx_parallel": rates}


def station_stats_sheet(countries: list[dict], history_years: int) -> pd.DataFrame:
    """Long table of the station-aggregated series: mean and median side by side."""
    cutoff = (date.today() - timedelta(days=365 * history_years)).isoformat()
    frames = []
    for c in countries:
        path = c["output_dir"] / "station_stats.csv"
        if path.exists():
            st = pd.read_csv(path)
            frames.append(
                st[st["observation_date"] >= cutoff].assign(iso3=c.get("iso3", ""))
            )
    if not frames:
        return pd.DataFrame()
    cols = [
        "iso3",
        "source_key",
        "series_key",
        "observation_date",
        "price_mean",
        "price_median",
        "price_trimmed_mean",
        "n_stations",
        "n_dropped",
        "dispersion",
        "flagged",
    ]
    return pd.concat(frames, ignore_index=True)[cols].sort_values(cols[:4])


def _latest_rows(countries: list[dict]) -> list[dict]:
    fam = _family_frames(countries, history_years=1)
    if fam.empty:
        return []
    latest = (
        fam.sort_values("observation_date").groupby(["country", "fuel_family"]).tail(1)
    )
    return latest.sort_values(["country", "fuel_family"]).to_dict("records")


def parallel_section_html(countries: list[dict]) -> str:
    rows = _latest_rows(countries)
    if not rows:
        return ""
    body = "".join(
        "<tr>"
        f"<td>{html.escape(str(r['country']))}</td><td>{html.escape(str(r['fuel_family']))}</td>"
        f"<td>{r['observation_date']}</td><td>{html.escape(str(r['currency']))}</td>"
        f"<td>{r['fx_rate']:,.2f}</td><td>{r['fx_rate_parallel']:,.2f}</td>"
        f"<td>{r['price_usd']:,.3f}</td><td>{r['price_usd_parallel']:,.3f}</td>"
        "</tr>"
        for r in rows
    )
    return (
        f'<section id="{_SECTION_ID}" style="max-width:1100px;margin:24px auto;padding:0 16px;'
        'font-size:0.9em;overflow-x:auto">'
        "<h3>Official vs parallel-market exchange rate</h3>"
        "<p>USD prices elsewhere on this page use the official rate. Where the World Bank "
        "Real-Time Exchange Rates panel (RTFX) reports a parallel (unofficial) rate, the "
        "latest USD/L at both rates is shown here.</p>"
        '<table style="border-collapse:collapse;width:100%">'
        "<thead><tr><th>Country</th><th>Fuel</th><th>Date</th><th>Currency</th>"
        "<th>Official rate</th><th>Parallel rate</th><th>USD/L official</th>"
        "<th>USD/L parallel</th></tr></thead>"
        f"<tbody>{body}</tbody></table></section>"
    )


def inject_parallel_section(html_path, countries: list[dict]) -> bool:
    """Insert the section before ``</body>``; False when no country has a parallel rate."""
    section = parallel_section_html(countries)
    if not section:
        return False
    text = html_path.read_text(encoding="utf-8")
    idx = text.rfind("</body>")
    if idx < 0:
        return False
    html_path.write_text(text[:idx] + section + "\n" + text[idx:], encoding="utf-8")
    return True
