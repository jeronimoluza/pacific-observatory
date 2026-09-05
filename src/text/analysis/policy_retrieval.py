"""Date policy-tracker rows by matching them against the news corpus.

A tracker workbook records which measures are in force; it does not record when
they began. ``Active or Proposed Date`` is a verification stamp, not an
effective date, so 95% of rows read 2026 regardless of how old the measure is.

The corpus reports measures when they happen, and reaches back to 2003. Matching
a policy row to the articles that reported it therefore recovers the one thing
the workbook lacks: a first-reported date and an article-count series per policy.

Anchor terms are weighted by inverse document frequency over the policy rows
themselves, so shared vocabulary ("fuel", "price", "government") is demoted and
row-specific vocabulary ("Pertalite", "B20", "RM600") drives the match.

This module only ever reads the workbooks. Results are written by the caller.
"""

from __future__ import annotations

import csv
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Sequence, Tuple

csv.field_size_limit(10**9)

TOKEN_RE = re.compile(r"[a-z][a-z0-9\-]{2,}|[a-z]?\d{1,4}[a-z]?")
DATE_RE = re.compile(r"\s*((?:19|20)\d{2})-(\d{2})")

# Roundups and letters pages mention many unrelated measures in one article and
# are the dominant false-positive class when matching on body text.
DIGEST_RE = re.compile(
    r"pacnews|briefs?\b|round-?up|bulletin|newsletter|letters to the editor|"
    r"in case you missed|week in review|daily digest",
    re.I,
)

# Words that carry no discriminating power between one policy row and another.
GENERIC = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "these",
    "those",
    "government",
    "national",
    "policy",
    "policies",
    "measure",
    "measures",
    "programme",
    "program",
    "scheme",
    "support",
    "announced",
    "announce",
    "introduced",
    "implement",
    "implemented",
    "implementation",
    "provide",
    "provided",
    "continue",
    "continued",
    "continuing",
    "maintain",
    "maintained",
    "new",
    "under",
    "over",
    "per",
    "also",
    "which",
    "who",
    "will",
    "would",
    "shall",
    "may",
    "can",
    "could",
    "into",
    "during",
    "through",
    "between",
    "about",
    "after",
    "before",
    "state",
    "public",
    "sector",
    "million",
    "billion",
    "percent",
    "cent",
    "year",
    "years",
    "month",
    "months",
}


def tokens(text: str) -> List[str]:
    return TOKEN_RE.findall((text or "").lower())


def row_text(row: Dict[str, str]) -> str:
    return " ".join(str(row.get(k, "") or "") for k in ("Policy", "Policy Description"))


def build_idf(rows: Sequence[Dict[str, str]]) -> Dict[str, float]:
    """Inverse document frequency over policy rows, used to rank anchor terms."""
    df: Counter = Counter()
    for row in rows:
        for term in set(tokens(row_text(row))) - GENERIC:
            df[term] += 1
    n = max(len(rows), 1)
    return {term: math.log(n / count) for term, count in df.items()}


def anchor_terms(
    row: Dict[str, str], idf: Dict[str, float], top_k: int = 8
) -> Tuple[List[str], List[str]]:
    """Split a row's vocabulary into identifying terms and supporting terms.

    The ``Policy`` cell names the instrument; ``Policy Description`` is analyst
    prose justifying it. Searching the description alone retrieves the topic
    ("cane", "crop", "farm" finds every sugar story), so title terms are kept
    separate and a match is later required to include at least one of them.
    """
    title = [
        t for t in dict.fromkeys(tokens(row.get("Policy", ""))) if t not in GENERIC
    ]
    desc = [
        t
        for t in dict.fromkeys(tokens(row.get("Policy Description", "")))
        if t not in GENERIC and t not in set(title)
    ]

    def by_idf(terms: List[str]) -> List[str]:
        return sorted(terms, key=lambda t: (-idf.get(t, 0.0), t))

    return by_idf(title)[:top_k], by_idf(desc)[:top_k]


def iter_articles(country_dir: Path) -> Iterator[Dict[str, str]]:
    """Yield every article under ``country_dir``, one dict per corpus row."""
    for path in sorted(country_dir.glob("*/news.csv")):
        with path.open(newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if not header:
                continue
            idx = {name: i for i, name in enumerate(header)}
            for values in reader:
                if len(values) < len(header):
                    continue
                yield {key: values[i] for key, i in idx.items() if i < len(values)}


def corpus_df(country_dir: Path, terms: set) -> Tuple[Counter, int]:
    """Document frequency of ``terms`` across one country's corpus.

    IDF fitted on policy rows alone is misleading: a term can be rare among
    policies yet ubiquitous in news ("sugar" sits in one Fiji policy row and in
    thousands of Fiji articles). Only the corpus knows what actually
    discriminates, so term weights are fitted here.
    """
    df: Counter = Counter()
    n = 0
    for article in iter_articles(country_dir):
        n += 1
        for term in (
            set(tokens(article.get("title", "") + " " + article.get("body", "")))
            & terms
        ):
            df[term] += 1
    return df, n


def match_country(
    country_dir: Path,
    queries: Dict[str, Dict[str, List[str]]],
    weights: Dict[str, float],
    min_terms: int = 3,
    min_score: float = 14.0,
    min_title_terms: int = 1,
    exclude_digests: bool = True,
) -> Dict[str, Any]:
    """Scan one country's corpus once, scoring every policy query in parallel.

    ``queries`` maps a policy key to its ``title`` and ``desc`` term lists;
    ``weights`` maps a term to its corpus IDF. An article matches when it
    carries at least ``min_title_terms`` identifying terms, ``min_terms`` terms
    overall, and a weight sum past ``min_score`` -- so a few rare terms qualify
    where many common ones do not. An inverted index keeps the scan linear in
    article length rather than in the number of policies.
    """
    index: Dict[str, List[Tuple[str, bool]]] = defaultdict(list)
    for key, parts in queries.items():
        for term in parts["title"]:
            index[term].append((key, True))
        for term in parts["desc"]:
            index[term].append((key, False))

    hits: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    scanned = 0
    skipped_digests = 0
    for article in iter_articles(country_dir):
        scanned += 1
        title = article.get("title", "")
        if exclude_digests and DIGEST_RE.search(title):
            skipped_digests += 1
            continue
        found = set(tokens(title + " " + article.get("body", ""))) & index.keys()
        if not found:
            continue
        per_policy: Dict[str, List[Tuple[str, bool]]] = defaultdict(list)
        for term in found:
            for key, is_title in index[term]:
                per_policy[key].append((term, is_title))
        for key, matched in per_policy.items():
            if len(matched) < min_terms:
                continue
            if sum(1 for _, is_title in matched if is_title) < min_title_terms:
                continue
            score = sum(weights.get(t, 0.0) for t, _ in matched)
            if score < min_score:
                continue
            hits[key].append(
                {
                    "date": article.get("date", ""),
                    "url": article.get("url", ""),
                    "title": title,
                    "source": article.get("source", ""),
                    "language": article.get("language", ""),
                    "terms": sorted(t for t, _ in matched),
                    "title_terms": sorted(t for t, is_t in matched if is_t),
                    "score": round(score, 2),
                }
            )
    return {
        "hits": dict(hits),
        "scanned": scanned,
        "skipped_digests": skipped_digests,
    }


def summarize(
    matches: List[Dict[str, Any]], onset_share: float = 0.15
) -> Dict[str, Any]:
    """Collapse an article list into the fields a timeline needs.

    ``first_reported`` is the single earliest match and is therefore decided by
    whichever false positive is oldest. ``onset_year`` is the first year whose
    coverage reaches ``onset_share`` of the policy's peak year, which survives a
    stray early hit; where the two disagree the row wants review.
    """
    years: Counter = Counter()
    dated: List[tuple] = []
    for match in matches:
        if DATE_RE.match(match.get("date", "")):
            years[int(match["date"][:4])] += 1
            dated.append((match["date"][:10], match))
    dated.sort(key=lambda x: x[0])

    onset = None
    if years:
        floor = max(2, onset_share * max(years.values()))
        onset = next((y for y in sorted(years) if years[y] >= floor), None)
    onset_first = next((d for d, _ in dated if onset and d[:4] == str(onset)), None)
    return {
        "n_articles": len(matches),
        "n_dated": len(dated),
        "first_reported": dated[0][0] if dated else None,
        "last_reported": dated[-1][0] if dated else None,
        "onset_year": onset,
        "onset_first_date": onset_first,
        "peak_year": max(years, key=lambda y: years[y]) if years else None,
        "years": dict(sorted(years.items())),
        "earliest": [m for _, m in dated[:5]],
        "onset_examples": [m for d, m in dated if onset and d[:4] == str(onset)][:5],
    }


def load_rows(workbook: Path, tracker: str) -> List[Dict[str, str]]:
    """Read one tracker workbook through the existing dashboard loader."""
    from text.plotting.policy_dashboards import load_policy_rows

    rows, _, _ = load_policy_rows(workbook, "Policies")
    for row in rows:
        row["_tracker"] = tracker
    return rows


def run(
    corpus_dirs: Dict[str, Path],
    workbooks: Dict[str, Path],
    idf_workbooks: Sequence[Path],
    min_terms: int = 3,
    min_score: float = 14.0,
    max_df: float = 0.02,
    top_k: int = 10,
) -> Dict[str, Any]:
    """Match every policy row for ``corpus_dirs``' countries against the corpus.

    ``idf_workbooks`` is the full set used to fit term weights; matching runs
    only over the countries named in ``corpus_dirs``.
    """
    idf_rows: List[Dict[str, str]] = []
    for path in idf_workbooks:
        tracker = "food" if "food_security" in str(path) else "fuel"
        idf_rows.extend(load_rows(path, tracker))
    idf = build_idf(idf_rows)

    rows: List[Dict[str, str]] = []
    for tracker, path in workbooks.items():
        rows.extend(load_rows(path, tracker))

    results: Dict[str, Any] = {"policies": {}, "corpus": {}}
    for country, corpus_dir in corpus_dirs.items():
        target = [r for r in rows if (r.get("Country") or "").strip() == country]
        candidates: Dict[str, Dict[str, List[str]]] = {}
        for row in target:
            key = f"{row['_tracker']}:{country}:{row.get('#', '')}"
            title_terms, desc_terms = anchor_terms(row, idf, top_k=top_k)
            if title_terms:
                candidates[key] = {"title": title_terms, "desc": desc_terms}
                results["policies"][key] = {
                    "country": country,
                    "tracker": row["_tracker"],
                    "policy": row.get("Policy", ""),
                    "category": row.get("Category", ""),
                    "subcategory": row.get("Subcategory", ""),
                    "workbook_date": row.get("Active or Proposed Date", ""),
                }

        # Pass 1: learn what each candidate term is worth in this corpus.
        vocab = {
            t for parts in candidates.values() for ts in parts.values() for t in ts
        }
        df, n_articles = corpus_df(corpus_dir, vocab)
        weights = {t: math.log(n_articles / max(df.get(t, 0), 1)) for t in vocab}

        # A term in more than max_df of articles cannot identify one policy.
        def keep(terms: List[str]) -> List[str]:
            return [t for t in terms if df.get(t, 0) <= max_df * n_articles]

        queries = {
            key: {"title": keep(parts["title"]), "desc": keep(parts["desc"])}
            for key, parts in candidates.items()
        }
        for key, parts in queries.items():
            results["policies"][key]["terms"] = {
                part: [
                    {"term": t, "df": df.get(t, 0), "weight": round(weights[t], 2)}
                    for t in ts
                ]
                for part, ts in parts.items()
            }
            results["policies"][key]["dropped_terms"] = [
                t
                for part in ("title", "desc")
                for t in candidates[key][part]
                if t not in parts[part]
            ]

        # Pass 2: match with corpus-fitted weights, anchored on title terms.
        outcome = match_country(
            corpus_dir,
            {k: v for k, v in queries.items() if v["title"]},
            weights,
            min_terms=min_terms,
            min_score=min_score,
        )
        results["corpus"][country] = {
            "scanned": outcome["scanned"],
            "skipped_digests": outcome["skipped_digests"],
            "n_queries": len(queries),
            "n_articles_for_df": n_articles,
        }
        for key in candidates:
            results["policies"][key]["match"] = summarize(outcome["hits"].get(key, []))
    return results
