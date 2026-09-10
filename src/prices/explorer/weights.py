"""Expenditure weights for the cross-country basket.

WHY THIS EXISTS. The basket compares a country's matched leaves against the
world median for the same leaves and averages the gaps up the COICOP tree, one
level at a time (`sources.ladder_agg`). Every child of a node counts once at its
parent, which is the right default when nothing is known about how much people
actually buy -- and the wrong one the moment something is. Six of Macao's
classes hold a single leaf each, all six are beverages, and equal-per-child
handed those six about a third of the basket; the country read 347 against a
world median of 100 on the strength of a bottle of water priced at $32.81 a
litre. Weights are what stop the taxonomy's shape from deciding the answer.

WHAT WILLIAM ASKED FOR, and what is actually available. From the 2026-09-09
call: "Of the countries that report their weights, what are the average weights
over the major divisions... then everything underneath that gets an equal weight
that's proportionate to the division weight. So you have, say food is 40%, then
each food item gets 40 divided by the number of items." He added that "we need
to get a plausible global weights database, and I don't know if there is one
already available."

There are two, and between them they cover exactly what he described:

  ICP 2021 (World Bank)   household final consumption expenditure, published at
                          COICOP CLASS depth for food and at GROUP depth for
                          beverages, alcohol and tobacco. 163 of our countries.
                          This is the DEFAULT.

  IMF CPI WGT_PT          the countries' own published CPI weights, DIVISION
                          depth only. 128 countries. This is literally "the
                          countries that report their weights"; it is stored
                          beside the ICP vector as an alternative division split
                          rather than replacing it, because ICP's hierarchy
                          nests (food + non-alcoholic = division 01) and mixing
                          two sources inside one tree does not.

ONE CORRECTION TO THE WORKED EXAMPLE. "Food is 40%" is food's share of the whole
CPI basket. This dashboard holds only the divisions in `load_taxonomy`, so there
is no "everything" here for food to be 40% of; renormalised inside the divisions
on screen the median reads closer to food 91% / alcohol and tobacco 9%. Nothing
here hardcodes which divisions those are -- more will arrive -- but any figure
shown to a reader has to name the universe it is a share OF, or it contradicts
the number he has in his head.

EXPENDITURE IS NOT A CPI WEIGHT. ICP measures household final consumption from
national accounts under a common product specification; a CPI weight comes from
a national household survey against a national basket. They differ on own
production, on imputed rent, and on urban-only frames. "A plausible global
weights database" is exactly the claim being made, and no more than that.

The refresh needs the network. The render never does: `default_weights` reads a
cached CSV and returns an empty vector when it is absent, so a build with no
weights table still produces a dashboard -- equal-per-child, as before.
"""

from __future__ import annotations

import csv
import json
import logging
import urllib.request
from collections import defaultdict
from pathlib import Path

from prices.explorer.sources import REPO_ROOT, _levels

logger = logging.getLogger(__name__)

WEIGHTS_CSV = REPO_ROOT / "data" / "prices" / "weights" / "expenditure_weights.csv"

# ICP series -> the node in OUR COICOP 2018 taxonomy it corresponds to.
#
# ICP's classification is COICOP 1999-shaped, so this is a crosswalk and not an
# identity. It is 1:1 at food-class depth, with three known imprecisions worth
# stating rather than discovering later: COICOP 2018 moved pulses and tubers
# into 01.1.7, widened 01.1.2 from "meat" to "live animals and meat", and split
# ready-made food out as 01.1.9. All three are small next to a slider the reader
# can move, and all three are invisible at the level the weights are applied.
#
# ICP stops at the GROUP for beverages, alcohol and tobacco -- there is no class
# detail published under them at all (verified against the source-90 series
# list: 48 series, 15 under 1101/1102). Those three entries therefore name a
# level-2 node, and `default_weights` spreads them down. Narcotics (02.4) has no
# ICP series and receives nothing.
ICP_TO_NODE = {
    "1101110": "01.1.1",   # Bread and cereals
    "1101120": "01.1.2",   # Meat
    "1101130": "01.1.3",   # Fish and seafood
    "1101140": "01.1.4",   # Milk, cheese and eggs
    "1101150": "01.1.5",   # Oils and fats
    "1101160": "01.1.6",   # Fruit
    "1101170": "01.1.7",   # Vegetables
    "1101180": "01.1.8",   # Sugar, jam, honey, chocolate and confectionery
    "1101190": "01.1.9",   # Food products n.e.c.
    "1101200": "01.2",     # NON-ALCOHOLIC BEVERAGES  (group)
    "1102100": "02.1",     # ALCOHOLIC BEVERAGES      (group)
    "1102200": "02.3",     # TOBACCO                  (group)
}

# ICP rounds, newest first. 62 (ICP 2011) is listed for the record: its data
# endpoint does not return JSON, and it is not needed -- sources 90 and 78
# between them already carry 2011 values for the handful of economies that have
# nothing newer.
ICP_SOURCES = (90, 78)

_ICP_URL = (
    "https://api.worldbank.org/v2/sources/{src}/country/all/"
    "classification/CN/series/{ser}/time/all/data"
    "?format=json&per_page=20000"
)


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.loads(r.read().decode())


def refresh_icp() -> list[dict]:
    """Latest available ICP expenditure per (economy, series).

    NO VINTAGE FLOOR. Taking whatever each economy last reported buys three
    ranked countries that a >=2017 rule would drop -- Macao, Venezuela and Yemen
    -- and Macao is the country whose basket this whole exercise exists to fix.
    The cost is that a 2011 value sits in a different currency era and a
    different ICP round, so the round year travels with every row and has to
    reach the screen. A weight is a share, which ages far better than a price
    level does, but it still ages.
    """
    latest: dict[tuple[str, str], tuple[int, float]] = {}
    for src in ICP_SOURCES:
        for ser in ICP_TO_NODE:
            try:
                doc = _get(_ICP_URL.format(src=src, ser=ser))
            except Exception as exc:                      # noqa: BLE001
                logger.warning("ICP source %s series %s: %s", src, ser, exc)
                continue
            for rec in doc.get("source", {}).get("data", []):
                if rec.get("value") is None:
                    continue
                by = {v["concept"]: v for v in rec["variable"]}
                iso = by.get("Country", {}).get("id", "")
                yr = by.get("Time", {}).get("id", "")
                if len(iso) != 3 or not yr.startswith("YR"):
                    continue
                year = int(yr[2:])
                key = (iso, ser)
                if key not in latest or year > latest[key][0]:
                    latest[key] = (year, float(rec["value"]))
    rows = [
        {"iso3": iso, "code": ICP_TO_NODE[ser], "value": val,
         "round": year, "source": "icp"}
        for (iso, ser), (year, val) in latest.items()
    ]
    logger.info("ICP: %d values over %d economies",
                len(rows), len({r["iso3"] for r in rows}))
    return rows


def refresh_imf(divisions: list[str]) -> list[dict]:
    """The countries' own published CPI weights, by division.

    This is the series William described without knowing it existed. `cpi.py`
    already builds the key `{country}.CPI.{component}.IX.{frequency}`; the
    fourth field is the transformation, and swapping IX for WGT_PT returns the
    weight instead of the index. Same client, same dataset, one field.

    Division depth is all there is -- both COICOP codelists on this dataset stop
    at CP01..CP12 -- which is exactly the grain he asked for and one level
    coarser than the sliders. Stored, not used by default: see the module
    docstring on why one source per tree beats two.
    """
    try:
        import sdmx
    except ImportError:
        logger.info("sdmx not installed; skipping the IMF weight table")
        return []
    client = sdmx.Client("IMF_DATA")
    rows: list[dict] = []
    for div in divisions:
        key = f".CPI.CP{div}.WGT_PT.M"
        try:
            frame = sdmx.to_pandas(
                client.data("CPI", key=key, params={"startPeriod": "2023"})
            ).dropna()
        except Exception as exc:                          # noqa: BLE001
            logger.warning("IMF WGT_PT %s: %s", div, exc)
            continue
        idx = frame.index.to_frame(index=False)
        idx["v"] = frame.to_numpy()
        period = next(c for c in idx.columns if c.upper().startswith("TIME"))
        country = next(c for c in idx.columns if c.upper().startswith("COUNTRY"))
        idx = idx.sort_values(period).groupby(country, as_index=False).last()
        for _, r in idx.iterrows():
            rows.append({"iso3": str(r[country]), "code": div,
                         "value": float(r["v"]), "round": str(r[period]),
                         "source": "imf_wgt_pt"})
    logger.info("IMF WGT_PT: %d values over %d countries",
                len(rows), len({r["iso3"] for r in rows}))
    return rows


def refresh(divisions: list[str]) -> Path:
    rows = refresh_icp() + refresh_imf(divisions)
    if not rows:
        raise SystemExit("no weight rows fetched -- nothing written")
    WEIGHTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with WEIGHTS_CSV.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["iso3", "code", "value", "round", "source"])
        w.writeheader()
        w.writerows(rows)
    back = list(csv.DictReader(WEIGHTS_CSV.open()))
    if len(back) != len(rows):
        raise SystemExit(f"round-trip lost rows: wrote {len(rows)}, read {len(back)}")
    logger.info("wrote %s (%d rows)", WEIGHTS_CSV, len(rows))
    return WEIGHTS_CSV


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def default_weights(tax: dict, level: int) -> tuple[dict[str, float], dict]:
    """The default weight vector, at `level`, over the taxonomy on screen.

    Four steps, in this order:

    1. Keep only economies reporting EVERY in-scope category. A partial reporter
       tilts the median toward whichever categories it happens to publish.
    2. Renormalise each economy's categories to sum to 1. This is what makes the
       vector a share of what is on this dashboard rather than a share of a
       national CPI basket that mostly is not.
    3. Take the MEDIAN across economies, then renormalise -- medians do not sum
       to 1 on their own. Median and not mean because the food share has a long
       right tail, and one economy spending 71% of its consumption on food
       should not drag the default for everyone.
    4. Spread each sourced node's weight equally over its descendants at `level`
       that exist in the taxonomy. This is William's "everything underneath gets
       an equal weight proportionate to the division weight", applied wherever
       the source stops rather than only at the division.

    Returns (weights, provenance). An absent CSV returns ({}, source="equal"),
    and the caller falls back to equal-per-child.
    """
    at_level = sorted(c for c, m in tax.items() if m.get("lvl") == level)
    if not WEIGHTS_CSV.exists():
        logger.info("no weights table at %s -- equal weights", WEIGHTS_CSV)
        return {}, {"source": "equal", "label": "equal weight per category",
                    "n_reporting": 0, "level": level}

    rows = [r for r in csv.DictReader(WEIGHTS_CSV.open()) if r["source"] == "icp"]
    in_scope = sorted({r["code"] for r in rows} & {
        c for c in tax if any(c == n for n in tax)})
    in_scope = [c for c in in_scope if c in tax]
    if not in_scope:
        return {}, {"source": "equal", "label": "equal weight per category",
                    "n_reporting": 0, "level": level}

    by_iso: dict[str, dict[str, float]] = defaultdict(dict)
    rounds: dict[str, int] = {}
    for r in rows:
        if r["code"] in in_scope:
            by_iso[r["iso3"]][r["code"]] = float(r["value"])
            rounds[r["iso3"]] = int(r["round"])
    complete = {i: v for i, v in by_iso.items() if len(v) == len(in_scope)}
    if not complete:
        return {}, {"source": "equal", "label": "equal weight per category",
                    "n_reporting": 0, "level": level}

    shares: dict[str, list[float]] = {c: [] for c in in_scope}
    for vals in complete.values():
        total = sum(vals.values())
        if total <= 0:
            continue
        for c, v in vals.items():
            shares[c].append(v / total)
    med = {c: _median(v) for c, v in shares.items() if v}
    tot = sum(med.values())
    med = {c: v / tot for c, v in med.items()}

    # spread each sourced node down to `level` over the descendants that exist
    out: dict[str, float] = {}
    for code, w in med.items():
        kids = [c for c in at_level if _levels(c)[: len(_levels(code))] == _levels(code)]
        if not kids:
            continue
        for k in kids:
            out[k] = out.get(k, 0.0) + w / len(kids)
    tot = sum(out.values())
    if tot > 0:
        out = {k: v / tot for k, v in out.items()}

    yrs = sorted({rounds[i] for i in complete})
    prov = {
        "source": "icp",
        "label": f"World Bank ICP household expenditure, median of "
                 f"{len(complete)} economies",
        "stat": "median",
        "n_reporting": len(complete),
        "rounds": {str(y): sum(1 for i in complete if rounds[i] == y) for y in yrs},
        "level": level,
        "sourced_at": {c: round(med[c], 5) for c in sorted(med)},
    }
    logger.info("default weights: %d nodes at level %d from %d economies",
                len(out), level, len(complete))
    return out, prov
