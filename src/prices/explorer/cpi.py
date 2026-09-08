"""Official CPI from the IMF, as a standalone benchmark artifact.

What this is for: a reader looking at a scraped, matched-item food price change
wants to know whether it is anywhere near the number the national statistical
office publishes. That comparison is the whole point of putting the two on one
chart, and it is only honest if both sides are stated in the same currency --
see `_app.js`, which converts our US$ series into local terms before the
official line is drawn beside it.

Deliberately standalone. It does NOT go through `enrich/stages/concatenate.py`
or the `cpi_benchmark` fetcher fleet: it fetches, writes one tidy table, and the
explorer build reads that table. Nothing upstream of the explorer changes, so
this can land while the enrich pipeline is blocked on something unrelated.

Granularity is whatever the IMF dataset carries, which is division level:
CP01..CP12 plus `_T` for all items. A country publishes some subset -- Fiji and
Korea publish all twelve, the Philippines and Japan publish the headline only --
and one wildcard request returns everything a country has. The dashboard itself
is scoped to COICOP divisions 01 and 02, so those are the divisions it can draw
a comparison against; the table keeps all of them so the next thing built on it
does not have to refetch.

The dataset:  https://data.imf.org/en/datasets/IMF.STA:CPI
"""

from __future__ import annotations

import logging

import pandas as pd

from prices.explorer.sources import REPO_ROOT

logger = logging.getLogger(__name__)

__all__ = ["OFFICIAL_CSV", "SERIES_LABEL", "HEADLINE", "refresh", "load_official"]

OFFICIAL_CSV = REPO_ROOT / "data" / "cpi" / "official_cpi_monthly.csv"

HEADLINE = "_T"
SERIES_LABEL = {
    "_T": "All items",
    "CP01": "Food and non-alcoholic beverages",
    "CP02": "Alcoholic beverages and tobacco",
    "CP03": "Clothing and footwear",
    "CP04": "Housing, water, electricity, gas and other fuels",
    "CP05": "Furnishings, household equipment and routine maintenance",
    "CP06": "Health",
    "CP07": "Transport",
    "CP08": "Communication",
    "CP09": "Recreation and culture",
    "CP10": "Education",
    "CP11": "Restaurants and hotels",
    "CP12": "Miscellaneous goods and services",
}
# The COICOP division each IMF series stands for, so the client can line the
# official series up with whatever category is on screen.
DIVISION_OF = {code: code[2:] for code in SERIES_LABEL if code != HEADLINE}


def refresh(iso3s: list[str], start_period: int = 2012) -> pd.DataFrame:
    """Fetch every division each country publishes and write the tidy table.

    One request per country: an empty COICOP key is the SDMX wildcard, so a
    country's twelve divisions and its headline arrive together rather than in
    thirteen round trips. Countries that return nothing are skipped, not
    invented -- a missing official CPI has to read as missing.
    """
    # imported here so the explorer build does not need `sdmx` installed
    from cpi.imf_data.cpi import _load_or_fetch

    rows = []
    for iso3 in iso3s:
        try:
            got = _load_or_fetch(iso3, "M", start_period, "")
        except Exception as exc:  # noqa: BLE001 - one bad country must not stop the rest
            logger.warning("CPI fetch failed for %s: %s", iso3, exc)
            continue
        if got is None or got.empty:
            continue
        rows.append(got.assign(COUNTRY=iso3))
    if not rows:
        raise SystemExit("no official CPI could be fetched for any country")

    df = pd.concat(rows, ignore_index=True)
    out = pd.DataFrame(
        {
            "iso3": df.COUNTRY.astype(str),
            # SDMX writes "2026-M06"; the explorer keys every series on "2026-06"
            "period": df.TIME_PERIOD.astype(str).str.replace(
                r"^(\d{4})-M(\d{1,2})$",
                lambda m: f"{m.group(1)}-{int(m.group(2)):02d}",
                regex=True,
            ),
            "series": df.COICOP_1999.astype(str),
            "index_value": pd.to_numeric(df.value, errors="coerce"),
        }
    ).dropna(subset=["index_value"])
    # Every field is a key the explorer joins on, so a row that is not exactly
    # well formed is dropped rather than written and puzzled over later: at
    # least one upstream record carries a newline inside a field, which turns
    # into a broken row on the way through CSV.
    out = out[
        out.series.isin(SERIES_LABEL)
        & out.iso3.str.fullmatch(r"[A-Z]{3}")
        & out.period.str.fullmatch(r"\d{4}-\d{2}")
    ].drop_duplicates(["iso3", "period", "series"])
    out = out.sort_values(["iso3", "series", "period"])
    OFFICIAL_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OFFICIAL_CSV, index=False)

    # An artifact that does not read back as it was written is not an artifact.
    back = pd.read_csv(OFFICIAL_CSV, dtype={"iso3": str, "period": str, "series": str})
    if len(back) != len(out) or set(back.series) != set(out.series):
        raise SystemExit(
            f"{OFFICIAL_CSV} did not round-trip: wrote {len(out)} rows, read {len(back)}"
        )
    logger.info(
        "official CPI written: %s — %s countries, %s series, %s rows",
        OFFICIAL_CSV,
        out.iso3.nunique(),
        out.series.nunique(),
        len(out),
    )
    return out


def load_official(iso3_by_slug: dict[str, str]) -> dict[str, dict]:
    """The tidy table, re-keyed on the explorer's country slugs.

    Returns {} when the artifact has not been built. The overlay is an optional
    benchmark, not a dependency: a build with no CPI table on disk must still
    produce a dashboard, minus the extra line.
    """
    if not OFFICIAL_CSV.exists():
        logger.info("no official CPI table at %s — overlay omitted", OFFICIAL_CSV)
        return {}
    df = pd.read_csv(OFFICIAL_CSV, dtype={"iso3": str, "period": str, "series": str})
    by_iso3 = {v: k for k, v in iso3_by_slug.items() if v}
    df = df[df.iso3.isin(by_iso3)]

    out: dict[str, dict] = {}
    for (iso3, series), g in df.sort_values("period").groupby(["iso3", "series"]):
        entry = out.setdefault(by_iso3[iso3], {})
        entry[series] = {
            "p": g.period.tolist(),
            "v": [round(float(v), 4) for v in g.index_value],
        }
    return out
