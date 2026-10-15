"""Find policy measures in the news corpus that the trackers do not record.

:mod:`policy_retrieval` starts from a known row and finds the articles that
reported it. Discovery runs the other way: it scans the corpus for articles that
read like a government acting on fuel or food, and hands the survivors to a
model that decides whether each one is a policy and which taxonomy cell it is.

Two signals gate the corpus. A *topic* signal says the article is about the
right subject; it is learned from the labeled tracker rows, per Category, and
scored by how much more a term belongs to one Category than to the rest. An
*action* signal says a government did something; it is hand-authored, because
no volume of labeled prose separates "prices rose" from "cabinet capped
prices". Requiring both is what keeps the candidate pool small enough to read.

Category is as deep as keywords go. Sibling subcategories share vocabulary and
half of the 31 have fewer than 25 labeled rows, so the subcategory is left to
the extraction pass, which reads the article and picks from the closed enum.

This module only reads the workbooks and the corpus. Candidates are returned to
the caller, which writes them.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

from text.analysis.policy_retrieval import (
    DATE_RE,
    DIGEST_RE,
    GENERIC,
    corpus_df,
    iter_articles,
    load_rows,
    row_text,
    tokens,
)

# An instrument being created, priced, or withdrawn. One of these is required:
# they are what makes a sentence about governing rather than about weather.
STRONG_ACTION = set(
    """
    subsidy subsidies subsidised subsidized levy levies tariff tariffs
    excise duty duties surcharge moratorium embargo quota quotas rationing
    stockpile stockpiles buffer waiver waivers waived exemption exemptions
    rebate rebates voucher vouchers gazette gazetted decree ordinance
    statutory legislation regulation regulations deregulation moratoria
    ceiling capped freeze frozen banned prohibition licensing procurement
    tender bailout handout handouts allowance stipend transfers safety-net
    price-control windfall
    """.split()
)

# Enactment and authorship. Common in news on their own, so these only count
# once a strong term is already present; they raise the score, never open it.
WEAK_ACTION = set(
    """
    cabinet parliament ministry minister ministers authority regulator
    commission treasury budget approved approval enacted imposed impose
    introduce introduces abolish abolished scrapped suspend suspended lifted
    extend extends extended effective enforce enforced mandate mandated
    reinstate reinstated rollout phased
    """.split()
)

ACTION = STRONG_ACTION | WEAK_ACTION

# A second way into the gate. Requiring an instrument noun misses the headlines
# that name the actor instead -- "Cabinet's gasohol price cut", "Commerce
# Minister defends sugar price increase", "Thailand extends diesel discount".
# A measured recall probe found this shape in 11 of 13 missed measures, almost
# all Thai. Alone each of these three sets is far too common to gate on; a
# headline carrying one of each is reliably about a government moving a price.
# This path costs 846 extra candidates and recovers 5 of the 13, at the same
# ~35% precision as the instrument path. Letting the country's own name count as
# an actor was tried and dropped: another 1,016 candidates bought one more.
ACTOR = set(
    """
    cabinet parliament ministry minister ministers govt government authority
    regulator commission committee department council junta premier pdmo
    """.split()
)

MOVEMENT = set(
    """
    cut cuts hike hikes raise raises raised lower lowers lowered boost boosts
    discount discounts increase increases slash slashes scrap scraps extend
    extends extended approve approves approved launch launches launched
    introduce introduces allow allows allowed sell sells plan plans defends
    """.split()
)

# A digest headline lists several unrelated stories, so any instrument word in
# it belongs to a story the article only summarises. Two of these arrive as one
# outlet's section furniture ("Phuket Gazette World News: ...", carried over
# when The Thaiger absorbed that archive) and the rest as semicolon lists; both
# are the dominant false positive once the gate reads headlines.
DIGEST_TITLE_RE = re.compile(
    r"world news\s*:|thailand news\s*:|national news\s*:|news (?:round-?up|update)\s*:",
    re.I,
)


def is_digest(title: str) -> bool:
    """True when a headline summarises several stories rather than reporting one."""
    return (
        title.count(";") >= 2
        or bool(DIGEST_TITLE_RE.search(title))
        or bool(DIGEST_RE.search(title))
    )


# Any digit-bearing token is dropped. Volumes, prices, article numbers and
# date stamps ("jul-26") are frequent in policy prose and perfectly
# category-specific, so a discriminative score ranks them top while they match
# nothing useful in news. Instrument codes ("B20", "RM600") go with them: they
# identify one country's measure, which is retrieval's job, not a category's.
NUMERIC_RE = re.compile(r"\d")

# Place names leak one country's measures into another's timeline. Country
# tokens are read off the workbooks; demonyms have to be listed.
DEMONYMS = set(
    """
    afghan algerian argentine australian bangladeshi brazilian british
    cambodian chinese colombian egyptian ethiopian european fijian filipino
    french german ghanaian indian indonesian iranian iraqi japanese kenyan
    korean lankan malaysian mexican moroccan nepali nigerian pakistani
    peruvian russian samoan saudi singaporean spanish swedish thai tongan
    turkish ukrainian vietnamese zambian
    """.split()
)

CALENDAR = set(
    """
    monday tuesday wednesday thursday friday saturday sunday january
    february march april june july august september october november
    december quarter quarterly monthly weekly daily fortnightly biweekly
    annual annually hour hours week weeks day days date dates duration
    beginning etc
    """.split()
)

# The workbooks carry analyst QA prose in some Policy Description cells
# ("verify exact rate", "no records found"). It is category-specific by
# accident of who wrote those rows and describes the audit, not the measure.
META = set(
    """
    summaries summary verify verified verification exact records record
    scope status instrument note notes final recent based where confirm
    confirmed pending unclear unknown review reviewed check checked listed
    """.split()
)


def place_terms(rows: Sequence[Dict[str, str]]) -> Set[str]:
    """Every token appearing in a Country cell, plus known demonyms."""
    places: Set[str] = set(DEMONYMS)
    for row in rows:
        places.update(tokens(str(row.get("Country", "") or "")))
    return places


def category_vocab(
    rows: Sequence[Dict[str, str]],
    min_support: int = 4,
    top_k: int = 60,
) -> Dict[str, List[str]]:
    """Terms that belong to one Category more than to the rest.

    Raw frequency returns "price" and "fuel" for every category; a plain rate
    ratio goes the other way and returns whatever appears in exactly
    ``min_support`` rows, because rarity alone maximises it. Ranking instead by
    the log-odds ratio divided by its standard error asks for effect *and*
    evidence, so a term needs both to be lopsided and to be attested.

    Numbers, place names and calendar words are dropped outright: each is highly
    category-specific in policy prose and worthless as a news query.
    """
    stop = GENERIC | ACTION | CALENDAR | META | place_terms(rows)
    per_cat: Dict[str, Counter] = defaultdict(Counter)
    totals: Counter = Counter()
    n_cat: Counter = Counter()
    for row in rows:
        cat = (row.get("Category") or "").strip().lower()
        if not cat:
            continue
        n_cat[cat] += 1
        terms = {
            t
            for t in set(tokens(row_text(row))) - stop
            if not NUMERIC_RE.search(t) and len(t) > 3
        }
        for term in terms:
            per_cat[cat][term] += 1
            totals[term] += 1

    n_all = max(sum(n_cat.values()), 1)
    prior = 0.5
    vocab: Dict[str, List[str]] = {}
    for cat, counts in per_cat.items():
        n_in = max(n_cat[cat], 1)
        n_out = max(n_all - n_in, 1)
        scored: List[Tuple[float, str]] = []
        for term, count in counts.items():
            if count < min_support:
                continue
            out = totals[term] - count
            odds_in = (count + prior) / (n_in - count + prior)
            odds_out = (out + prior) / (n_out - out + prior)
            delta = math.log(odds_in) - math.log(odds_out)
            se = math.sqrt(1.0 / (count + prior) + 1.0 / (out + prior))
            scored.append((delta / se, term))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        vocab[cat] = [term for _, term in scored[:top_k]]
    return vocab


def fit_weights(
    country_dir: Path, vocab: Iterable[str], max_df: float = 0.05
) -> Tuple[Dict[str, float], Dict[str, int], int]:
    """Weight every gate term by how rare it is in this country's own corpus.

    A term's weight has to be learned where it will be used. "Sugar" is rare
    among policy rows and ubiquitous in Fijian news; only the corpus knows that.
    Terms above ``max_df`` of articles are returned with weight zero so they can
    still be seen but cannot carry a match on their own.
    """
    terms = set(vocab)
    df, n_articles = corpus_df(country_dir, terms)
    weights = {}
    for term in terms:
        count = df.get(term, 0)
        if count > max_df * n_articles:
            weights[term] = 0.0
        else:
            weights[term] = math.log(n_articles / max(count, 1))
    return weights, dict(df), n_articles


def scan(
    country_dir: Path,
    country: str,
    vocab: Dict[str, List[str]],
    weights: Dict[str, float],
    min_score: float = 6.0,
    exclude_digests: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[int, int]]:
    """Score every article against every Category pack in one pass.

    A headline is admitted two ways: it names an instrument (``STRONG_ACTION``),
    or it names a government actor moving something (``ACTOR`` and
    ``MOVEMENT``). Either way it must also carry a category term, and the field
    ``admitted_by`` records which path let it in so the two can be measured
    apart.

    The gate reads the headline only. Scanning bodies passed 9% of the corpus:
    "duty", "regulations" and "decree" occur in passing in almost any article
    about a government, so a body match says the piece mentions governing, not
    that it reports a measure. A newsroom that reports a measure puts it in the
    headline -- "Govt scraps fuel duty" -- so requiring an instrument *and* a
    category term there is both tighter and closer to what is being asked.

    The body still contributes to ``score``, which ranks candidates for review;
    it just cannot admit one. Returns the survivors and the per-year article
    count, which the timeline needs as a denominator: a year with few articles
    and a year with no policy look identical without it.
    """
    index: Dict[str, List[str]] = defaultdict(list)
    for cat, terms in vocab.items():
        for term in terms:
            index[term].append(cat)

    candidates: List[Dict[str, Any]] = []
    coverage: Counter = Counter()
    for article in iter_articles(country_dir):
        date = article.get("date", "")
        if DATE_RE.match(date):
            coverage[int(date[:4])] += 1
        title = article.get("title", "")
        if not title:
            continue
        if exclude_digests and is_digest(title):
            continue

        head = set(tokens(title))
        topic = head & index.keys()
        if not topic:
            continue
        strong = head & STRONG_ACTION
        actor_path = bool(head & ACTOR) and bool(head & MOVEMENT)
        if not strong and not actor_path:
            continue

        body = set(tokens(article.get("body", "")))
        body_topic = (body & index.keys()) - topic
        per_cat: Counter = Counter()
        for term in topic:
            for cat in index[term]:
                per_cat[cat] += 2
        for term in body_topic:
            for cat in index[term]:
                per_cat[cat] += 1
        score = sum(weights.get(t, 0.0) for t in topic | strong) + 0.25 * sum(
            weights.get(t, 0.0) for t in body_topic
        )
        admitted_by = "instrument" if strong else "actor"

        if score < min_score:
            continue
        candidates.append(
            {
                "country": country,
                "date": date[:10],
                "url": article.get("url", ""),
                "title": title,
                "source": article.get("source", ""),
                "language": article.get("language", "") or "en",
                "category_hint": max(per_cat, key=lambda c: per_cat[c]),
                "title_topic": sorted(topic),
                "title_action": sorted(head & ACTION),
                "strong_action": sorted(strong),
                "admitted_by": admitted_by,
                "body_topic": sorted(body_topic)[:20],
                "score": round(score, 2),
            }
        )
    return candidates, dict(sorted(coverage.items()))


def run(
    corpus_dirs: Dict[str, Path],
    vocab_workbooks: Sequence[Path],
    min_score: float = 6.0,
    max_df: float = 0.05,
    top_k: int = 60,
) -> Dict[str, Any]:
    """Build the Category packs, then scan each country once.

    ``vocab_workbooks`` is every tracker workbook; vocabulary is pooled across
    regions and trackers because the taxonomy is shared and no single region has
    enough rows per category to learn from alone.
    """
    rows: List[Dict[str, str]] = []
    for path in vocab_workbooks:
        tracker = "food" if "food_security" in str(path) else "fuel"
        rows.extend(load_rows(Path(path), tracker))
    vocab = category_vocab(rows, top_k=top_k)
    all_terms = {t for terms in vocab.values() for t in terms} | ACTION

    results: Dict[str, Any] = {
        "vocab": vocab,
        "n_vocab_rows": len(rows),
        "countries": {},
    }
    for country, corpus_dir in corpus_dirs.items():
        weights, df, n_articles = fit_weights(Path(corpus_dir), all_terms, max_df)
        kept = {
            cat: [t for t in terms if weights.get(t, 0.0) > 0.0]
            for cat, terms in vocab.items()
        }
        candidates, coverage = scan(
            Path(corpus_dir),
            country,
            kept,
            weights,
            min_score=min_score,
        )
        results["countries"][country] = {
            "n_articles": n_articles,
            "n_candidates": len(candidates),
            "coverage_by_year": coverage,
            "dropped_terms": sorted(
                t for t in all_terms if weights.get(t, 0.0) == 0.0 and t in df
            ),
            "candidates": candidates,
        }
    return results
