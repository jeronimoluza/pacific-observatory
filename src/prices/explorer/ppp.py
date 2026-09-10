"""An external price level to check our own price level against.

WHY THIS EXISTS. The basket ranking says Fiji is at 118 and India at 61 against
a world median of 100. Nothing inside this repository can tell you whether that
is right: the world median is our own corpus's median, so the whole scale is
self-referential. What settles it is somebody else's price level, built from
somebody else's prices, on the same countries. From the 2026-09-09 call:
"they go and they price 1000 products in each country, and then they compare
them directly... So we should find something very correlated with that. It's
not going to be exactly the same." And, asked whether it replaces our number:
"No, it's definitely not a replacement. It's like the benchmark in the same way
that you were benchmarking against the CPI."

So this is an OVERLAY. Nothing here is ever blended into our figure, corrects
our figure, or reweights it. It is drawn beside it and the reader judges.

WHAT WE FETCH, and why there are two of them.

  icp   World Bank ICP `PX.WL`, "price level index (World = 100)", at the same
        classification the expenditure weights already come from. Published at
        our exact food classes (1101110-1101190), at non-alcoholic beverages
        (1101200), alcohol (1102100) and tobacco (1102200), and at the two
        DIVISION aggregates 1101000 and 1102000 that are our divisions 01 and
        02 exactly. World = 100 is our base, food-and-tobacco is our scope,
        and an expenditure-weighted average over classes is our aggregation.
        This is the comparator; everything below is the check on it.

  wdi   `PA.NUS.GDP.PLI`, "price level index (GDP)", and `PA.NUS.PRVT.PLI`, the
        same for household final consumption. This is what William named in the
        call -- he called it `PA.NUS.PPPC.RF`, which the WDI has since retired;
        the API answers "The indicator was not found. It may have been deleted
        or archived", and `PA.NUS.GDP.PLI` is the series that replaced it.
        WHOLE-ECONOMY, so it prices rent, healthcare and haircuts alongside
        bread. Services are cheap in poor countries in a way food is not
        (Balassa-Samuelson), so this one is expected to sit BELOW the food
        benchmark at the bottom of the income scale and the gap is a real
        property of the two measures, not a defect in either. Its compensation
        is time: it is extrapolated annually, so 2024 and 2025 exist, where ICP
        stops at its 2021 round.

BASES DO NOT MATCH, and are made to. ICP publishes World = 100 and the WDI
publishes United States = 100. The conversion is one number -- the United
States' own price level on the world base -- which ICP publishes as PX.WL for
the USA. It is a scale constant, taken from the ICP round, and it is applied to
the WDI series so both benchmarks and our own figure land on one axis.

VINTAGE. Same policy as `weights.py`: the latest round each economy has, no
floor, and the round year travels with the value so a 2011 benchmark reads as a
2011 benchmark on screen. This matters far more here than it does for weights.
A weight is a share and ages slowly; a PRICE LEVEL is a real exchange rate and
moves several per cent a year, so a country benchmarked on ICP 2011 against a
corpus scraped in 2026 is being compared across fifteen years of real
appreciation. That is a caveat the chart has to carry, not one to bury here.

ICP 2011 (source 62) is listed in `weights.ICP_SOURCES` for the record and is
not queried: its data endpoint returns an XML error rather than JSON. Source 78
carries 2011 values for the economies that have nothing newer, which is the
same thing by another route.

The refresh needs the network. The render never does: `load_benchmark` reads
the cached CSV and returns an empty block when it is absent, exactly as the
official-CPI overlay does.
"""

from __future__ import annotations

import csv
import logging
import math
from collections import defaultdict
from pathlib import Path

from prices.explorer.sources import REPO_ROOT, _levels
from prices.explorer.weights import ICP_SOURCES, ICP_TO_NODE, _get

logger = logging.getLogger(__name__)

__all__ = ["PPP_CSV", "refresh", "load_benchmark"]

PPP_CSV = REPO_ROOT / "data" / "prices" / "ppp" / "price_level_benchmark.csv"

# ICP price-level classification. A sibling of the `CN` expenditure
# classification `weights.py` fetches, on the same endpoint, over the same
# series -- so the crosswalk in `weights.ICP_TO_NODE` is reused rather than
# copied, and any correction to it moves both.
ICP_CLASS = "PX.WL"

# The two ICP series that ARE our divisions, plus GDP. The division pair is
# what the unweighted reading of our own basket corresponds to (`_basket_levels`
# with no weights averages up to the divisions and takes their mean); GDP is
# what makes the WDI comparable, since the USA's PX.WL at GDP is the constant
# that turns a US = 100 index into a World = 100 one.
ICP_EXTRA = {
    "1101000": "01",     # FOOD AND NON-ALCOHOLIC BEVERAGES
    "1102000": "02",     # ALCOHOLIC BEVERAGES, TOBACCO AND NARCOTICS
    "1000000": "GDP",    # GROSS DOMESTIC PRODUCT -- whole economy
}
ICP_SERIES = {**ICP_TO_NODE, **ICP_EXTRA}

_PX_URL = (
    "https://api.worldbank.org/v2/sources/{src}/country/all/"
    "classification/" + ICP_CLASS + "/series/{ser}/time/all/data"
    "?format=json&per_page=20000"
)

# WDI indicator -> the code it is stored under. `PA.NUS.PPPC.RF`, the indicator
# named on the call, is retired; these two are what the WDI publishes now.
WDI_INDICATORS = {
    "PA.NUS.GDP.PLI": "GDP",
    "PA.NUS.PRVT.PLI": "HFCE",
}
_WDI_URL = (
    "https://api.worldbank.org/v2/country/all/indicator/{ind}"
    "?format=json&per_page=25000&date=2015:2030"
)

LABELS = {
    "icp": "World Bank ICP, price level index (World = 100), food, beverages, "
           "alcohol and tobacco",
    "icp_gdp": "World Bank ICP, price level index (World = 100), whole economy",
    "wdi": "World Bank WDI PA.NUS.GDP.PLI, price level index (GDP), rescaled "
           "from United States = 100 to World = 100",
    "wdi_hfce": "World Bank WDI PA.NUS.PRVT.PLI, price level index (household "
                "final consumption), rescaled to World = 100",
}


def refresh_icp_levels() -> list[dict]:
    """Latest available ICP price level per (economy, series).

    30 requests -- fifteen series over two rounds -- and the newest round an
    economy appears in wins. Sources are walked newest-first and the comparison
    is strict, so an economy present in both source 90 and source 78 at 2017
    keeps source 90's value: the same year re-benchmarked by the later round is
    the later round's number.
    """
    latest: dict[tuple[str, str], tuple[int, float]] = {}
    for src in ICP_SOURCES:
        for ser in ICP_SERIES:
            try:
                doc = _get(_PX_URL.format(src=src, ser=ser))
            except Exception as exc:                      # noqa: BLE001
                logger.warning("ICP %s source %s series %s: %s",
                               ICP_CLASS, src, ser, exc)
                continue
            # NOT a list. The v2 sources endpoint returns `source` as an object
            # here and as an array elsewhere; indexing it as an array is the
            # bug this comment exists to stop being written a third time.
            data = doc.get("source", {}).get("data", [])
            for rec in data:
                if rec.get("value") is None:
                    continue
                by = {v["concept"]: v for v in rec["variable"]}
                iso = by.get("Country", {}).get("id", "")
                yr = by.get("Time", {}).get("id", "")
                # id is "YR2021", not "2021"
                if len(iso) != 3 or not yr.startswith("YR"):
                    continue
                year = int(yr[2:])
                try:
                    val = float(rec["value"])
                except (TypeError, ValueError):
                    continue
                if val <= 0:
                    continue
                key = (iso, ser)
                if key not in latest or year > latest[key][0]:
                    latest[key] = (year, val)
    rows = [
        {"iso3": iso, "code": ICP_SERIES[ser], "value": val,
         "round": year, "source": "icp"}
        for (iso, ser), (year, val) in latest.items()
    ]
    logger.info("ICP %s: %d values over %d economies",
                ICP_CLASS, len(rows), len({r["iso3"] for r in rows}))
    return rows


def refresh_wdi_levels() -> list[dict]:
    """The WDI price level indices, latest year with a value per economy.

    United States = 100 as published; `load_benchmark` does the rescaling.

    The WDI country list carries regional and income aggregates alongside
    economies, and some of them DO have three-letter codes ("EUU", "LIC"), so
    the shape filter here does not remove them. It does not need to: the read
    path joins on the explorer's own country table, and an aggregate has no
    slug to join to. Everything is kept rather than guessed at, so a country
    added to the explorer later needs no refetch.
    """
    rows: list[dict] = []
    for ind, code in WDI_INDICATORS.items():
        try:
            doc = _get(_WDI_URL.format(ind=ind))
        except Exception as exc:                          # noqa: BLE001
            logger.warning("WDI %s: %s", ind, exc)
            continue
        if not isinstance(doc, list) or len(doc) < 2 or not doc[1]:
            logger.warning("WDI %s returned no data page: %s", ind, doc[:1])
            continue
        latest: dict[str, tuple[int, float]] = {}
        for rec in doc[1]:
            iso = (rec.get("countryiso3code") or "").strip()
            if len(iso) != 3 or rec.get("value") is None:
                continue
            try:
                year, val = int(rec["date"]), float(rec["value"])
            except (TypeError, ValueError):
                continue
            if val <= 0:
                continue
            if iso not in latest or year > latest[iso][0]:
                latest[iso] = (year, val)
        rows += [
            {"iso3": iso, "code": code, "value": val,
             "round": year, "source": "wdi"}
            for iso, (year, val) in latest.items()
        ]
        logger.info("WDI %s: %d economies, latest years %s", ind, len(latest),
                    sorted({y for y, _ in latest.values()}))
    return rows


def refresh() -> Path:
    rows = refresh_icp_levels() + refresh_wdi_levels()
    if not rows:
        raise SystemExit("no benchmark rows fetched -- nothing written")
    PPP_CSV.parent.mkdir(parents=True, exist_ok=True)
    with PPP_CSV.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["iso3", "code", "value", "round", "source"])
        w.writeheader()
        w.writerows(rows)
    back = list(csv.DictReader(PPP_CSV.open()))
    if len(back) != len(rows):
        raise SystemExit(f"round-trip lost rows: wrote {len(rows)}, read {len(back)}")
    logger.info("wrote %s (%d rows)", PPP_CSV, len(rows))
    return PPP_CSV


def _icp_node_for(code: str, sourced: set[str]) -> str | None:
    """The ICP node whose price level covers our category `code`.

    ICP stops at the class for food and at the GROUP for beverages, alcohol and
    tobacco, so a level-3 category under 01.2 is covered by 01.2's own index.
    Longest matching prefix wins, walking up our own code, so adding a deeper
    ICP series later needs no change here.
    """
    for cand in reversed(_levels(code)):
        if cand in sourced:
            return cand
    return None


def _agg(terms: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Weighted geometric mean of price levels, and the weight it covered.

    The same arithmetic `_basket_levels` applies to our own numbers: average
    the LOG ratios, weighted, over the categories that exist, with the missing
    categories' weight redistributed across the ones that do. Returns None when
    nothing is left to average.
    """
    tot = sum(w for w, _ in terms)
    if tot <= 0:
        return None
    rel = sum(w * math.log(v / 100.0) for w, v in terms) / tot
    return math.exp(rel) * 100.0, tot


def load_benchmark(
    iso3_by_slug: dict[str, str],
    weights: dict[str, float] | None = None,
) -> tuple[dict[str, dict], dict]:
    """The benchmark table, re-keyed on the explorer's country slugs.

    Returns ({}, {}) when the artifact has not been built -- the overlay is an
    optional benchmark, not a dependency, and a build with no CSV on disk still
    produces a dashboard minus one chart.

    `weights` is the SAME vector the basket ranking used. Handing the benchmark
    our weight vector is what makes the two numbers comparable: the difference
    between them is then prices and prices only, not one aggregation against
    another. When it is empty the fallback matches the ranking's own fallback --
    the unweighted mean over the two divisions, which is what `_basket_levels`
    computes when no weights exist.

    THE JOIN IS ON ISO3, and it is one-to-one in both directions. Two explorer
    countries carry an empty iso3 and are dropped rather than matched to each
    other; two slugs sharing an iso3 would each get the same benchmark, which
    is correct, and neither is dropped.
    """
    if not PPP_CSV.exists():
        logger.info("no price-level benchmark at %s -- overlay omitted", PPP_CSV)
        return {}, {}

    rows = list(csv.DictReader(PPP_CSV.open()))
    by_source: dict[str, dict[str, dict[str, tuple[float, int]]]] = {
        "icp": defaultdict(dict), "wdi": defaultdict(dict)}
    for r in rows:
        src = r["source"]
        if src not in by_source:
            continue
        try:
            by_source[src][r["iso3"]][r["code"]] = (float(r["value"]), int(r["round"]))
        except (TypeError, ValueError):
            continue
    icp, wdi = by_source["icp"], by_source["wdi"]

    # United States = 100 -> World = 100. One constant, from ICP's own GDP
    # price level for the USA. Without it the two benchmarks sit on two
    # different axes and the 45-degree line means nothing on one of them.
    us = icp.get("USA", {}).get("GDP")
    us_on_world = us[0] if us else None

    sourced = {c for c in ICP_SERIES.values() if c not in ("GDP",)}
    class_codes = sorted(set(ICP_TO_NODE.values()))

    out: dict[str, dict] = {}
    n_dup = 0
    seen_iso: dict[str, str] = {}
    for slug, iso in sorted(iso3_by_slug.items()):
        if not iso:
            continue
        if iso in seen_iso:
            n_dup += 1
        seen_iso.setdefault(iso, slug)
        e_icp, e_wdi = icp.get(iso), wdi.get(iso)
        if not e_icp and not e_wdi:
            continue
        entry: dict = {}

        if e_icp:
            # class-by-class, on our own codes -- the panel that says WHERE we
            # diverge rather than only by how much
            cls = {c: [round(e_icp[c][0], 2), e_icp[c][1]]
                   for c in class_codes if c in e_icp}
            if cls:
                entry["cls"] = cls
            terms: list[tuple[float, float]] = []
            if weights:
                for code, w in weights.items():
                    node = _icp_node_for(code, sourced)
                    if node and node in e_icp:
                        terms.append((float(w), e_icp[node][0]))
            else:
                for div in ("01", "02"):
                    if div in e_icp:
                        terms.append((1.0, e_icp[div][0]))
            got = _agg(terms)
            if got:
                entry["icp"], cov = got[0], got[1]
                entry["icp"] = round(entry["icp"], 2)
                entry["icpCov"] = round(cov, 3) if weights else None
                entry["icpYear"] = max(
                    y for c, (_, y) in e_icp.items() if c in sourced
                )
            for div, key in (("01", "icp01"), ("02", "icp02")):
                if div in e_icp:
                    entry[key] = round(e_icp[div][0], 2)
            if "GDP" in e_icp:
                entry["icpGdp"] = round(e_icp["GDP"][0], 2)
                entry["icpGdpYear"] = e_icp["GDP"][1]

        if e_wdi and us_on_world:
            for code, key, ykey in (("GDP", "wdi", "wdiYear"),
                                    ("HFCE", "wdiHfce", "wdiHfceYear")):
                if code in e_wdi:
                    v, y = e_wdi[code]
                    entry[key] = round(v * us_on_world / 100.0, 2)
                    entry[ykey] = y
        if entry:
            out[slug] = entry

    meta = {
        "labels": LABELS,
        "base": "World = 100, the same base as the basket ranking",
        "us_on_world": round(us_on_world, 2) if us_on_world else None,
        "rescaled": (
            "WDI publishes United States = 100; every WDI value here is "
            f"multiplied by {round(us_on_world, 2) if us_on_world else '?'}, "
            "the United States' own ICP price level on the World = 100 base."
        ),
        "source": (
            "World Bank ICP (classification PX.WL, rounds 2021/2017/2011) and "
            "World Bank WDI (PA.NUS.GDP.PLI, PA.NUS.PRVT.PLI)"
        ),
        "scope": {
            "icp": "COICOP divisions 01 and 02 only -- the same scope as ours",
            "wdi": "the whole economy, including rent, health and services",
        },
        "weighted": bool(weights),
        # Which ICP index covers each weighted category, so the CLIENT can
        # re-aggregate the benchmark under a reader's own weight vector rather
        # than comparing a re-weighted figure of ours against a fixed one of
        # theirs. At the published vector this reproduces `icp` exactly, which
        # is what `test_ppp_benchmark` pins.
        "nodeOf": ({c: _icp_node_for(c, sourced) for c in sorted(weights)}
                   if weights else {}),
        "n_icp": sum(1 for v in out.values() if v.get("icp") is not None),
        "n_wdi": sum(1 for v in out.values() if v.get("wdi") is not None),
        "classes": class_codes,
    }
    if n_dup:
        logger.warning("%d explorer slugs share an ISO3 with another", n_dup)
    logger.info(
        "price-level benchmark: %d countries with an ICP food level, "
        "%d with a WDI whole-economy level, of %d asked for",
        meta["n_icp"], meta["n_wdi"], len(iso3_by_slug),
    )
    return out, meta
