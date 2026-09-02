"""Collapse extracted articles into policy events, then link them to the trackers.

The extraction pass judges one article at a time, so a measure reported by six
outlets over three days arrives as six accepted rows. Left alone the timeline
would show six dots for one decision, and the count of "policies found" would be
a count of press interest.

Three resolutions run here, in order:

1. *article to event* -- rows in the same country and subcategory whose measure
   text agrees are one event. Numbers do most of the work: "20 cents per litre"
   and "THB 10,000" identify a measure far better than its prose does, so two
   rows carrying different numbers are held apart even when their wording
   matches, and two carrying the same number are joined even when it does not.

2. *event to lifecycle* -- the same instrument announced in 2019 and extended in
   2022 is one policy with two events. They are linked, not merged: the timeline
   wants both dots.

3. *event to workbook* -- an event that matches an existing tracker row is that
   row's missing date, not a new policy. Without this step discovery re-finds
   everything the workbook already holds and every count doubles.

Nothing here writes to a tracker workbook.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from text.analysis.policy_retrieval import GENERIC, tokens

NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")

# Words every measure name carries; they inflate similarity between unrelated
# measures in the same subcategory, which is exactly where it does most harm.
MEASURE_STOP = GENERIC | {
    "rate",
    "rates",
    "price",
    "prices",
    "pricing",
    "scheme",
    "fund",
    "relief",
    "temporary",
    "national",
    "federal",
    "cent",
    "cents",
    "percent",
    "baht",
    "thb",
    "fjd",
    "usd",
    "litre",
    "liter",
    "per",
    "million",
    "billion",
}


def content(text: str) -> set:
    return {t for t in tokens(text or "") if t not in MEASURE_STOP and len(t) > 2}


def numbers(text: str) -> set:
    """Numeric tokens, normalised so 10,000 and 10000 compare equal."""
    return {n.replace(",", "").rstrip(".0") or "0" for n in NUM_RE.findall(text or "")}


def date_key(value: Optional[str]) -> Optional[Tuple[int, int, int, int]]:
    """Sortable key for a possibly partial ISO date, with its precision.

    Partial dates are the norm here -- an article often supports a year and
    nothing more -- so they are kept partial rather than padded to a false
    January 1st. Precision travels with the key so a consumer can tell an
    exact date from a year.
    """
    if not value:
        return None
    m = re.match(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$", str(value).strip())
    if not m:
        return None
    year, month, day = m.group(1), m.group(2), m.group(3)
    precision = 3 if day else (2 if month else 1)
    return (int(year), int(month or 1), int(day or 1), precision)


def similarity(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    """How much two extracted rows look like the same measure.

    Jaccard over content words, then the numbers arbitrate: a shared number is
    strong evidence of one measure, a conflicting one strong evidence of two.
    """
    ta, tb = content(a.get("measure", "")), content(b.get("measure", ""))
    if not ta or not tb:
        return 0.0
    jac = len(ta & tb) / len(ta | tb)
    na, nb = numbers(a.get("measure", "")), numbers(b.get("measure", ""))
    if na and nb:
        if na & nb:
            return min(1.0, jac + 0.35)
        if not (na & nb):
            return jac * 0.4
    return jac


def containment(event: Dict[str, Any], probe_text: str) -> float:
    """How much of a measure name is covered by a workbook row's prose.

    Jaccard is symmetric and so cannot compare a five-word measure name with a
    fifty-word policy description: their union is dominated by the longer side
    and the score collapses toward zero however well they agree. Containment
    asks the question that actually matters here -- does the workbook row say
    what this measure says -- and is scaled by the shorter side.
    """
    ta = content(event.get("measure", ""))
    tb = content(probe_text)
    if not ta or not tb:
        return 0.0
    overlap = len(ta & tb) / min(len(ta), len(tb))
    na, nb = numbers(event.get("measure", "")), numbers(probe_text)
    if na and nb and na & nb:
        overlap = min(1.0, overlap + 0.2)
    return overlap


def _root(parent: Dict[int, int], i: int) -> int:
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def cluster(
    rows: Sequence[Dict[str, Any]], threshold: float = 0.5, window_days: int = 120
) -> List[List[int]]:
    """Group row indices into events within (country, subcategory) blocks.

    Comparison is blocked because two measures in different subcategories are
    different measures by construction, and comparing every row against every
    other is quadratic in a pool that only grows.
    """
    blocks: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        blocks[(r.get("policy_country", ""), r.get("subcategory", ""))].append(i)

    parent = {i: i for i in range(len(rows))}
    for members in blocks.values():
        for x, i in enumerate(members):
            for j in members[x + 1 :]:
                if similarity(rows[i], rows[j]) < threshold:
                    continue
                ki, kj = (
                    date_key(rows[i].get("announced_date")),
                    date_key(rows[j].get("announced_date")),
                )
                if ki and kj:
                    gap = abs(
                        (ki[0] - kj[0]) * 365 + (ki[1] - kj[1]) * 30 + ki[2] - kj[2]
                    )
                    if gap > window_days:
                        continue
                parent[_root(parent, i)] = _root(parent, j)

    groups: Dict[int, List[int]] = defaultdict(list)
    for i in range(len(rows)):
        groups[_root(parent, i)].append(i)
    return [sorted(v) for v in groups.values()]


def _best_date(members: Sequence[Dict[str, Any]], field: str) -> Dict[str, Any]:
    """Earliest supported value for a date field, preferring explicit evidence.

    An article reporting a measure today and an article recalling that it began
    in 2015 disagree; the second is the one that carries the date the timeline
    wants, so explicit beats publication regardless of which is earlier.
    """
    scored = []
    for r in members:
        key = date_key(r.get(field))
        if not key:
            continue
        basis = r.get("date_basis", "publication")
        rank = {"explicit": 0, "inferred": 1, "publication": 2}.get(basis, 2)
        scored.append((rank, key, r))
    if not scored:
        return {field: None, f"{field}_basis": None, f"{field}_evidence": None}
    scored.sort(key=lambda s: (s[0], s[1]))
    rank, key, row = scored[0]
    return {
        field: row.get(field),
        f"{field}_basis": row.get("date_basis"),
        f"{field}_evidence": row.get("date_evidence"),
        f"{field}_confidence": row.get("date_confidence"),
    }


def _merge_tracker(members: Sequence[Dict[str, Any]]) -> str:
    """Which tracker an event belongs to, given one verdict per article."""
    seen = {
        (m.get("tracker") or "").lower()
        for m in members
        if (m.get("tracker") or "").lower() in {"fuel", "food", "both"}
    }
    if not seen or "both" in seen or seen == {"fuel", "food"}:
        return "both"
    return seen.pop()


def build_events(
    rows: Sequence[Dict[str, Any]], threshold: float = 0.5
) -> List[Dict[str, Any]]:
    """Collapse accepted extraction rows into one record per measure."""
    accepted = [r for r in rows if r.get("is_policy")]
    events = []
    for group in cluster(accepted, threshold=threshold):
        members = [accepted[i] for i in group]
        # The longest measure name is the most specific one on offer.
        label = max((m.get("measure", "") for m in members), key=len)
        event = {
            "measure": label,
            "country": members[0].get("policy_country", ""),
            "category": members[0].get("category", ""),
            "subcategory": members[0].get("subcategory", ""),
            "status": members[0].get("status", ""),
            "n_articles": len(members),
            "sources": sorted(
                {m.get("source", "") for m in members if m.get("source")}
            ),
            "cand_ids": [m.get("cand_id") for m in members],
            "article_dates": sorted(
                {m["article_date"] for m in members if m.get("article_date")}
            ),
            # Which dashboard the measure belongs on. Members of one event can
            # disagree -- a cost-of-living package read as "fuel" by one article
            # and "food" by another -- and a split verdict is exactly what
            # "both" means, so disagreement widens rather than picks a side.
            "tracker": _merge_tracker(members),
            # An announcement outranks an amendment, which outranks a passing
            # mention: the event should be named by the strongest thing seen.
            "action_type": next(
                (
                    kind
                    for kind in ("new", "change", "mention")
                    if any(m.get("action_type") == kind for m in members)
                ),
                "",
            ),
            "languages": sorted(
                {m.get("language", "") for m in members if m.get("language")}
            ),
        }
        for field in ("announced_date", "effective_date", "end_date"):
            event.update(_best_date(members, field))
        key = date_key(event.get("announced_date")) or date_key(
            event.get("effective_date")
        )
        event["event_year"] = key[0] if key else None
        event["date_precision"] = key[3] if key else 0
        events.append(event)
    events.sort(key=lambda e: (e["country"], e["event_year"] or 9999, e["measure"]))
    return events


def link_lifecycles(events: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Join events that are the same instrument seen at different moments.

    The date window in :func:`cluster` deliberately keeps an announcement and a
    later extension apart, because both belong on the timeline. They still need
    to be recognisable as one policy, so a lifecycle id is stamped across them.
    """
    parent = {i: i for i in range(len(events))}
    blocks: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for i, e in enumerate(events):
        blocks[(e["country"], e["subcategory"])].append(i)
    for members in blocks.values():
        for x, i in enumerate(members):
            for j in members[x + 1 :]:
                if similarity(events[i], events[j]) >= 0.5:
                    parent[_root(parent, i)] = _root(parent, j)
    out = []
    for i, e in enumerate(events):
        e = dict(e)
        e["lifecycle_id"] = f"lc{_root(parent, i):04d}"
        out.append(e)
    counts: Dict[str, int] = defaultdict(int)
    for e in out:
        counts[e["lifecycle_id"]] += 1
    for e in out:
        e["lifecycle_size"] = counts[e["lifecycle_id"]]
    return out


def link_workbook(
    events: Sequence[Dict[str, Any]],
    workbook_rows: Iterable[Dict[str, str]],
    threshold: float = 0.45,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Mark each event as new to the corpus or already held by the tracker.

    Matching is blocked on country and category rather than subcategory: the
    workbook's own subcategory choice and the extractor's need not agree, and
    disagreeing about which of two sibling cells a measure belongs in is not a
    reason to call it a different measure. Scoring uses :func:`containment`,
    not the symmetric measure used between articles, because a measure name and
    a policy description are of very different lengths.
    """
    by_country: Dict[Tuple[str, str], List[Dict[str, str]]] = defaultdict(list)
    for row in workbook_rows:
        key = ((row.get("Country") or "").strip(), (row.get("Category") or "").strip())
        by_country[key].append(row)

    matched_rows = set()
    out = []
    for event in events:
        cands = by_country.get((event["country"], event["category"]), [])
        best, best_score = None, 0.0
        for row in cands:
            probe = f"{row.get('Policy', '')} {row.get('Policy Description', '')}"
            score = containment(event, probe)
            if score > best_score:
                best, best_score = row, score
        event = dict(event)
        if best is not None and best_score >= threshold:
            event["provenance"] = "both"
            event["workbook_policy"] = best.get("Policy", "")
            event["workbook_id"] = best.get("ID_v6", "")
            event["match_score"] = round(best_score, 3)
            matched_rows.add(best.get("ID_v6", "") or best.get("Policy", ""))
        else:
            event["provenance"] = "corpus"
            event["workbook_policy"] = None
            event["match_score"] = round(best_score, 3)
        out.append(event)

    stats = {
        "n_events": len(out),
        "n_matched_workbook": sum(1 for e in out if e["provenance"] == "both"),
        "n_new": sum(1 for e in out if e["provenance"] == "corpus"),
        "n_workbook_rows_touched": len(matched_rows),
    }
    return out, stats
