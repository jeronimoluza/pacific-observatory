"""Turn extraction findings into the ``discovered_<region>.json`` sidecars.

The agents return one verdict per article. This collapses them into measures,
joins the measures that are the same instrument seen at different moments,
checks each against the tracker so an already-recorded measure is not offered
twice, and writes the result in the shape the dashboard appends verbatim.

Fuel and food are separate trackers with separate workbooks, so the split
happens here: an event tagged ``both`` is written to each side.

Usage:
    python scripts/policy_assemble.py --region ssa
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from core.config import load_countries, load_regions  # noqa: E402
from text.analysis.policy_events import (  # noqa: E402
    build_events,
    implausible_year,
    link_lifecycles,
    link_workbook,
)
from text.plotting.policy_dashboards import canonical_country  # noqa: E402
from text.plotting.policy_dashboards_v6 import CATEGORY_DISPLAY  # noqa: E402
from text.plotting.policy_subregions import fold  # noqa: E402
from text.plotting.trackers import WORKBOOK_ROOT, latest_workbook, workbook_dir  # noqa: E402

DATA = REPO_ROOT / "data" / "text"
OUT_DIR = DATA / "policy_tracker_extended"

# The corpus starts in 2015; anything earlier is a year read off an instrument's
# name rather than off the action described.
CORPUS_START = 2000

TRACKERS = {t: workbook_dir(WORKBOOK_ROOT, t) for t in ("fuel", "food")}

# The corpus is multilingual, so a country arrives under whatever name its own
# press uses. ``canonical_country`` speaks the workbook's English vocabulary and
# does not know "RDC" or "Comores", and a name it cannot place is read as a
# foreign country and dropped. Keyed by folded form, valued by the countries.yaml
# display name; extend as new languages enter a region's corpus.
ENDONYMS = {
    "rdc": "Congo, Dem. Rep.",
    "republiquedemocratiqueducongo": "Congo, Dem. Rep.",
    "democraticrepublicofcongo": "Congo, Dem. Rep.",
    "republicademocraticadocongo": "Congo, Dem. Rep.",
    "republiqueducongo": "Congo, Rep.",
    "comores": "Comoros",
    "guineaecuatorial": "Equatorial Guinea",
    "guineeequatoriale": "Equatorial Guinea",
    "guineequatorial": "Equatorial Guinea",
    "cotedivoire": "Cote d'Ivoire",
    "capvert": "Cabo Verde",
    "caboverde": "Cabo Verde",
    "afriquedusud": "South Africa",
    "etiopia": "Ethiopia",
    "tanzanie": "Tanzania",
    "mocambique": "Mozambique",
    # The Palestinian territories arrive under half a dozen spellings; the
    # topology knows exactly one of them.
    "palestine": "West Bank and Gaza",
    "palestinianterritories": "West Bank and Gaza",
    "gaza": "West Bank and Gaza",
    "gazastrip": "West Bank and Gaza",
    "westbank": "West Bank and Gaza",
    # Both spellings clear the region gate, so without this one country would
    # split into two rows on the dashboard.
    "syria": "Syrian Arab Republic",
    # The eca press calls these countries by their common names, but the
    # topology only knows the formal ones, so every measure arrived looking
    # foreign: "Russia" alone accounted for 95 dropped events.
    "russia": "Russian Federation",
    "kyrgyzstan": "Kyrgyz Republic",
    "turkey": "Türkiye",
    # Francophone Maghreb and Sahel press.
    "algerie": "Algeria",
    "maroc": "Morocco",
    "tunisie": "Tunisia",
    "tchad": "Chad",
    # Portuguese/Spanish lac press.
    "brasil": "Brazil",
    "republicadominicana": "Dominican Republic",
    "southkorea": "Korea, Rep.",
    "korea": "Korea, Rep.",
    # Balkan, Polish, Romanian, Albanian and Turkish eca press.
    "republicamoldova": "Moldova",
    "moldawia": "Moldova",
    "modawia": "Moldova",  # fold drops the Polish ł
    "polska": "Poland",
    "crnagora": "Montenegro",
    "sjevernamakedonija": "North Macedonia",
    "macedonia": "North Macedonia",
    "francuska": "France",
    "fransa": "France",
    "slovenija": "Slovenia",
    "njemacka": "Germany",
    "greqia": "Greece",
    "greqi": "Greece",
    "yunanistan": "Greece",
    "shqiperia": "Albania",
    "srbija": "Serbia",
}

# ``fold`` keeps only [a-z0-9], so a name in Arabic or Persian script folds to
# "" and can never hit ENDONYMS. Those are matched on the raw string instead.
SCRIPT_ENDONYMS = {
    "الجزائر": "Algeria",
    "المغرب": "Morocco",
    "تونس": "Tunisia",
    "الأردن": "Jordan",
    "اليمن": "Yemen, Rep.",
    "ایران": "Iran, Islamic Rep.",
    "إيران": "Iran, Islamic Rep.",
    "جيبوتي": "Djibouti",
    "تشاد": "Chad",
    "قطاع غزة": "West Bank and Gaza",
    "غزة": "West Bank and Gaza",
    "فلسطين": "West Bank and Gaza",
    "مصر": "Egypt, Arab Rep.",
    "العراق": "Iraq",
    "سوريا": "Syrian Arab Republic",
    "لبنان": "Lebanon",
    "ليبيا": "Libya",
    # Cyrillic and Armenian eca press.
    "Молдова": "Moldova",
    "Кыргызстан": "Kyrgyz Republic",
    "Россия": "Russian Federation",
    "Русија": "Russian Federation",
    "Росія": "Russian Federation",
    "Ռուսաստան": "Russian Federation",
    "Беларусь": "Belarus",
    "България": "Bulgaria",
    "ՀՀ": "Armenia",
    "Латвия": "Latvia",
    "Македонија": "North Macedonia",
    "Унгарија": "Hungary",
    "Казахстан": "Kazakhstan",
    "Италија": "Italy",
    "Германија": "Germany",
    "Україна": "Ukraine",
}

# "Syrian Arab Republic (regime-controlled areas)", "Palestine (Gaza Strip)" --
# the extraction pass qualifies a country with the sub-national area a measure
# applies to. The qualifier is real information but it is not part of the name,
# and leaving it attached makes the row look foreign and drops it silently.
_QUALIFIER = re.compile(r"\s*\([^)]*\)\s*$")


@lru_cache(maxsize=1)
def country_vocabulary() -> frozenset[str]:
    """Folded spellings of every country countries.yaml knows.

    Needed to tell a country apart from a sub-national unit that merely names
    one: the tail of "Haryana, India" is a country, the tail of
    "Congo, Dem. Rep." is not.
    """
    out: set[str] = set()
    for slug, meta in load_countries().items():
        out.add(fold(slug))
        display = (meta or {}).get("name")
        if display:
            out.add(fold(display))
            out.add(fold(canonical_country(display)))
    return frozenset(out)


def _canonical(raw: str) -> str:
    if raw in SCRIPT_ENDONYMS:
        return SCRIPT_ENDONYMS[raw]
    name = canonical_country(raw)
    return ENDONYMS.get(fold(name), name)


def resolve_country(value: str) -> str:
    """One spelling per country, whatever language the article used."""
    raw = _QUALIFIER.sub("", value or "").strip()
    name = _canonical(raw)
    if fold(name) in country_vocabulary():
        return name

    # "Haryana, India", "Jammu and Kashmir, India" -- a state qualified by its
    # country. The measure belongs to the country, and without dropping the
    # state the row reads as foreign and is discarded. Only reached when the
    # whole string is not itself a country, so "Hong Kong SAR, China" and
    # "Korea, Rep." are never split on their own comma.
    if "," in raw:
        tail = _canonical(raw.rsplit(",", 1)[1].strip())
        if fold(tail) in country_vocabulary():
            return tail
    return name


def region_countries(region: str) -> set[str]:
    """Folded names of every country the region's topology claims."""
    topology = load_regions().get(region) or {}
    if not topology:
        raise SystemExit(f"unknown region: {region}")
    names = load_countries()
    out = set()
    for sub in (topology.get("subregions") or {}).values():
        for slug in sub.get("countries") or []:
            out.add(fold(slug))
            display = (names.get(slug) or {}).get("name")
            if display:
                out.add(fold(display))
                out.add(fold(canonical_country(display)))
    return out


def read_findings(region: str) -> list[dict]:
    """Every agent verdict for a region, in shard order."""
    rows: list[dict] = []
    bad = 0
    for path in sorted((OUT_DIR / "findings" / region).glob("shard_*.jsonl")):
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
    if bad:
        print(f"  WARN: {bad} unparseable finding lines skipped")
    return rows


def workbook_rows(region: str, tracker: str) -> list[dict]:
    """The tracker's own policy rows, for the already-recorded check."""
    import pandas as pd

    path = latest_workbook(TRACKERS[tracker], region)
    if path is None:
        print(f"  WARN: no {tracker} workbook at {path}")
        return []
    frame = pd.read_excel(path, sheet_name="Policies").fillna("")
    return [{k: str(v) for k, v in row.items()} for row in frame.to_dict("records")]


def dated_by(event: dict) -> tuple[str, str, str]:
    """The date the timeline uses, and how well that date is supported.

    ``_best_date`` records basis and confidence per date field, so the answer
    depends on which field supplied the date: an announcement dated from the
    text and an effective date guessed from the publication are not equally
    trustworthy, and the description must say which one it is showing.
    """
    for field in ("announced_date", "effective_date"):
        if event.get(field):
            return (
                event[field],
                event.get(f"{field}_basis") or "unknown",
                event.get(f"{field}_confidence") or "n/a",
            )
    # No date in any article's text. The measure still existed by the day it was
    # first reported, and the timeline drops anything without a year -- so the
    # earliest article date stands in, labelled for what it is rather than
    # passed off as evidence.
    reported = event.get("article_dates") or []
    if reported:
        return reported[0], "publication", "low"
    return "", "unknown", "n/a"


def describe(event: dict) -> str:
    """The sentence the dashboard shows under a discovered measure."""
    sources = ", ".join(event.get("sources") or []) or "the corpus"
    _, basis, conf = dated_by(event)
    text = (
        f"Discovered from {event['n_articles']} news article(s) in {sources}. "
        f"Date basis: {basis} ({conf} confidence)."
    )
    if event.get("evidence"):
        text += f' Evidence: "{event["evidence"]}"'
    return text


def render(event: dict, index: int) -> dict:
    """One event in the shape the v6 dashboard appends to the workbook rows."""
    years = Counter(d[:4] for d in event.get("article_dates") or [] if d[:4].isdigit())
    date, basis, conf = dated_by(event)
    cat = event.get("category", "")
    return {
        "Country": event.get("country", ""),
        "Policy": event.get("measure", ""),
        "Policy Description": describe(event),
        "Label": event.get("status", ""),
        "Active or Proposed Date": date,
        "Source": "; ".join(event.get("sources") or []),
        "category": cat,
        "category_display": CATEGORY_DISPLAY.get(cat, cat),
        "subcategory": event.get("subcategory", ""),
        # ``event_year`` only knows the text's own dates; when the publication
        # date stood in above, the year has to come from it too or the measure
        # stays off the timeline.
        "onset_year": event.get("event_year")
        or (int(date[:4]) if date[:4].isdigit() else None),
        "peak_year": int(years.most_common(1)[0][0]) if years else None,
        "n_articles": event.get("n_articles", 0),
        "years": dict(years),
        "provenance": event.get("provenance", "corpus"),
        "date_basis": basis,
        "date_confidence": conf,
        "action_type": event.get("action_type", ""),
        "lifecycle_id": event.get("lifecycle_id", ""),
        "ID_v6": f"disc-{index:04d}",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    ap.add_argument("--threshold", type=float, default=0.5, help="event clustering")
    ap.add_argument("--match", type=float, default=0.45, help="workbook match")
    args = ap.parse_args()

    findings = read_findings(args.region)
    accepted = [r for r in findings if r.get("is_policy")]
    print(f"{len(findings):,} verdicts, {len(accepted):,} accepted")

    events = link_lifecycles(build_events(findings, threshold=args.threshold))
    print(f"  events: {len(events):,}")

    # The evidence quote does not survive clustering, so it is carried across by
    # the first member the event names.
    quote_by_cand = {r.get("cand_id"): r.get("evidence") for r in accepted}
    for event in events:
        for cand in event.get("cand_ids") or []:
            if quote_by_cand.get(cand):
                event["evidence"] = quote_by_cand[cand]
                break

    dropped = [e for e in events if implausible_year(e, corpus_start=CORPUS_START)]
    events = [e for e in events if not implausible_year(e, corpus_start=CORPUS_START)]
    if dropped:
        print(f"  dropped (year predates the corpus): {len(dropped)}")

    # One spelling per country, before the region test rather than after it:
    # "RDC" is a Congolese measure, and a test that runs first reads it as a
    # foreign country and throws it away.
    for event in events:
        event["country"] = resolve_country(event.get("country", ""))

    # The region's press reports the region's neighbours: a US reserve release
    # and a Chinese tariff exemption both arrive through SSA outlets, correctly
    # attributed and entirely out of scope for an SSA tracker. Measures naming
    # several countries at once ("the Sahel region") go the same way -- there is
    # no single country row to put them on.
    inside = region_countries(args.region)
    foreign = [e for e in events if fold(e.get("country", "")) not in inside]
    events = [e for e in events if fold(e.get("country", "")) in inside]
    if foreign:
        names = sorted({e["country"] for e in foreign})
        print(
            f"  dropped (outside {args.region}): {len(foreign)} across "
            f"{len(names)} names -- {', '.join(names[:8])}"
        )

    for tracker, directory in TRACKERS.items():
        mine = [e for e in events if e.get("tracker") in (tracker, "both")]
        linked, stats = link_workbook(
            mine, workbook_rows(args.region, tracker), threshold=args.match
        )
        # A measure the tracker already holds is not news; the sidecar carries
        # what the workbook is missing.
        fresh = [e for e in linked if e["provenance"] == "corpus"]
        rows = [render(e, i) for i, e in enumerate(fresh)]

        out_dir = OUT_DIR if tracker == "fuel" else OUT_DIR / "food_security"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"discovered_{args.region}.json"
        out.write_text(json.dumps(rows, indent=1))

        years = Counter(r["onset_year"] for r in rows if r["onset_year"])
        pre = sum(n for y, n in years.items() if y < 2025)
        print(
            f"  {tracker}: {stats['n_events']} events, "
            f"{stats['n_matched_workbook']} already in the tracker, "
            f"{len(rows)} new ({pre} pre-2025) -> {out}"
        )


if __name__ == "__main__":
    main()
