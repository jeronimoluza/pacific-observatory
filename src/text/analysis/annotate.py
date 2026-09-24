"""Single-pass combined-automaton annotator.

Replaces the per-EPU-instance flow where every topic and actor EPU rescanned
all article bodies. Here, each article body is scanned exactly once with a
combined Aho-Corasick automaton whose payloads carry category tags. Output is
a per-source-per-month counts frame; the body is dropped immediately after
per-article matching and never persisted.

Public API:
    annotate_source(news_csv, source_key, language, keyword_bundle) -> pd.DataFrame
    build_combined_automaton(language, keyword_bundle) -> CombinedAutomaton
    annotate_country(country_dir, source_languages, keyword_bundle, max_parallel_sources)
"""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable

import ahocorasick
import numpy as np
import pandas as pd

from text.analysis.utils import (
    LANGUAGE_ALIASES,
    NON_SPACE_DELIMITED,
    _is_latin_boundary,
    _is_word_boundary,
    load_all_groups,
    load_concepts,
    load_topics_words,
    resolved_language,
)


# ── Category bundle ──────────────────────────────────────────────────


@dataclass
class KeywordBundle:
    """Holds the complete keyword sets for one language used by one country.

    `epu` carries the canonical {"economic", "policy", "uncertainty"} lists.
    `topics` and `actors` carry the full group->terms mappings as loaded from
    `topics.json` and `actors.json` respectively.
    """

    language: str
    epu: dict[str, list[str]]
    topics: dict[str, list[str]]
    actors: dict[str, list[str]]
    script_language: str = ""
    concepts: dict[str, list] = field(default_factory=dict)
    groups: dict[str, list] = field(default_factory=dict)

    @classmethod
    def for_language(cls, language: str) -> "KeywordBundle":
        lang = LANGUAGE_ALIASES.get(language, language)
        concepts, groups = load_concepts(lang)
        return cls(
            language=lang,
            epu=load_topics_words(language=lang),
            topics=load_all_groups("topics", language=lang),
            actors=load_all_groups("actors", language=lang),
            script_language=resolved_language(lang, "topics"),
            concepts=concepts,
            groups=groups,
        )


# ── Combined automaton ───────────────────────────────────────────────


@dataclass
class CombinedAutomaton:
    """An ahocorasick.Automaton plus the category list and per-term length cache.

    Each automaton payload is `(category_tag, term_lower, is_prefix)`. Counts are
    resolved per category via greedy non-overlapping dedupe against the
    list of (start, end) tuples for that category.
    """

    automaton: ahocorasick.Automaton
    categories: tuple[str, ...]
    check_boundaries: bool = field(default=True)


def _category_iter(bundle: KeywordBundle) -> Iterable[tuple[str, list[str]]]:
    """Yield (category_tag, terms) for every category in a bundle."""
    yield "econ", bundle.epu.get("economic", [])
    yield "policy", bundle.epu.get("policy", [])
    yield "uncertain", bundle.epu.get("uncertainty", [])
    for topic_key, terms in bundle.topics.items():
        yield f"topic:{topic_key}", terms
    for actor_key, terms in bundle.actors.items():
        yield f"actor:{actor_key}", terms
    for concept_id, forms in bundle.concepts.items():
        yield f"concept:{concept_id}", forms
    for group_id, forms in bundle.groups.items():
        yield f"group:{group_id}", forms


def _forms_key(forms: list) -> tuple:
    """Concept forms as hashable ``(text, is_prefix)`` pairs."""
    return tuple(
        (f["prefix"], True) if isinstance(f, dict) else (f, False) for f in forms
    )


def _bundle_cache_key(bundle: KeywordBundle) -> tuple:
    """Stable key for lru_cache that captures every term in the bundle."""
    epu_key = tuple(
        (cat, tuple(bundle.epu.get(cat, [])))
        for cat in ("economic", "policy", "uncertainty")
    )
    topics_key = tuple((k, tuple(v)) for k, v in sorted(bundle.topics.items()))
    actors_key = tuple((k, tuple(v)) for k, v in sorted(bundle.actors.items()))
    concepts_key = tuple((k, _forms_key(v)) for k, v in sorted(bundle.concepts.items()))
    groups_key = tuple((k, _forms_key(v)) for k, v in sorted(bundle.groups.items()))
    return (
        bundle.language,
        bundle.script_language or bundle.language,
        epu_key,
        topics_key,
        actors_key,
        concepts_key,
        groups_key,
    )


@lru_cache(maxsize=64)
def _build_combined_automaton_cached(cache_key: tuple) -> CombinedAutomaton:
    """Inner cache. Reconstructs the automaton from the immutable cache_key.

    Critical: a single term may appear in multiple categories (e.g. "government"
    is both a policy term and an actor:government keyword). `add_word(word, v)`
    overwrites the prior value, so we must accumulate the FULL list of (tag,
    term) tuples for each word and emit them all on match.
    """
    (
        language,
        script_language,
        epu_key,
        topics_key,
        actors_key,
        concepts_key,
        groups_key,
    ) = cache_key
    categories: list[str] = []
    by_word: dict[str, list[tuple[str, str, bool]]] = {}

    def add(tag: str, terms, is_prefix: bool = False):
        for term in terms:
            t = _compose_sara_am(term.lower())
            by_word.setdefault(t, []).append((tag, t, is_prefix))

    for cat, terms in epu_key:
        tag = {"economic": "econ", "policy": "policy", "uncertainty": "uncertain"}[cat]
        categories.append(tag)
        add(tag, terms)
    for topic_key, terms in topics_key:
        tag = f"topic:{topic_key}"
        categories.append(tag)
        add(tag, terms)
    for actor_key, terms in actors_key:
        tag = f"actor:{actor_key}"
        categories.append(tag)
        add(tag, terms)
    for family, key in (("concept", concepts_key), ("group", groups_key)):
        for group_id, forms in key:
            tag = f"{family}:{group_id}"
            categories.append(tag)
            for text, is_prefix in forms:
                add(tag, [text], is_prefix)

    A = ahocorasick.Automaton()
    for word, tag_list in by_word.items():
        A.add_word(word, tuple(tag_list))
    A.make_automaton()
    return CombinedAutomaton(
        automaton=A,
        categories=tuple(categories),
        check_boundaries=script_language not in NON_SPACE_DELIMITED,
    )


def build_combined_automaton(bundle: KeywordBundle) -> CombinedAutomaton:
    """Public constructor that goes through the lru_cache."""
    return _build_combined_automaton_cached(_bundle_cache_key(bundle))


# ── Per-body matcher ─────────────────────────────────────────────────


def _match_all_categories(body: str, combo: CombinedAutomaton) -> dict[str, int]:
    """Run one Aho-Corasick pass and return per-category match counts.

    Implements the same greedy non-overlapping dedupe as the legacy
    ``match_keywords`` in ``utils.py`` — but per category, so two categories
    matching overlapping byte ranges are counted independently.

    Only categories with a match are returned: with 1,700 concept and group
    categories, a full dict per article held 1.4 GB per 20,000-row chunk.
    """
    if not body:
        return {}

    text = str(body)
    per_cat_matches: dict[str, list[tuple[int, int]]] = defaultdict(list)

    for end_idx, payload in combo.automaton.iter(text):
        # `payload` is a tuple of (cat, term, is_prefix) tuples — the same word
        # may belong to several categories (e.g. policy + actor:government).
        for cat, term, is_prefix in payload:
            start_idx = end_idx - len(term) + 1
            end_pos = end_idx + 1
            if combo.check_boundaries:
                if is_prefix:
                    # A prefix form keeps only the left boundary, so the
                    # suffixes of an agglutinative language still match.
                    if start_idx > 0 and (
                        text[start_idx - 1].isalnum() or text[start_idx - 1] == "_"
                    ):
                        continue
                elif not _is_word_boundary(text, start_idx, end_pos):
                    continue
            elif term.isascii():
                # Latin term in a non-space-delimited pack. Bounding it against
                # ASCII letters only keeps `GDP` matching when Thai or Han
                # characters sit flush against it, while stopping `UN` from
                # matching inside "fund" and `AI` inside "said".
                if not _is_latin_boundary(text, start_idx, end_pos):
                    continue
            per_cat_matches[cat].append((start_idx, end_pos))

    counts: dict[str, int] = {}
    for cat, matches in per_cat_matches.items():
        matches.sort(key=lambda m: (m[0], -(m[1] - m[0])))
        last_end = -1
        c = 0
        for start, end in matches:
            if start >= last_end:
                c += 1
                last_end = end
        counts[cat] = c
    return counts


# ── Per-source annotation ───────────────────────────────────────────


def _process_body(body: str | float) -> str:
    """Mirror EPU.process_data body normalization (strip newlines and zero-width
    spaces, lower, NFC).

    Khmer sources insert U+200B between words (about 64 per article in
    kampuchea_thmey_daily), and one inside a phrase stops the phrase matching.
    Sara am is composed too (see `_compose_sara_am`).
    """
    if not isinstance(body, str):
        return ""
    import unicodedata

    return _compose_sara_am(
        unicodedata.normalize(
            "NFC", body.replace("\n", "").replace("\u200b", "").lower()
        )
    )


def _compose_sara_am(text: str) -> str:
    """Write Thai and Lao sara am as one character.

    matichon and thai_rath spell ำ as nikhahit + sara aa (ํา), and KPL spells
    ຳ as ໍາ; NFC leaves both pairs apart, so a form written ำ never matched
    them. Applied to bodies and keyword terms alike.
    """
    return text.replace("\u0e4d\u0e32", "\u0e33").replace("\u0ecd\u0eb2", "\u0eb3")


def _ym_for_date(d: pd.Timestamp, daily_tail_start: pd.Timestamp | None) -> str:
    if daily_tail_start is not None and d >= daily_tail_start:
        return d.strftime("%Y-%m-%d")
    return f"{d.year}-{d.month}"


def _grouped_for_frame(
    df: pd.DataFrame,
    combo: CombinedAutomaton,
    daily_tail_start: pd.Timestamp | None,
) -> pd.DataFrame:
    """Monthly counts for one already-deduped, already-filtered frame.

    Split out of `annotate_source` so the identical aggregation can run over a
    chunk. Every column produced here is a count or a sum, so concatenating the
    per-chunk results and summing them by ym reproduces the whole-file answer.
    Returned frame is indexed by ym and carries no source_key column.
    """
    col = {cat: j for j, cat in enumerate(combo.categories)}
    matrix = np.zeros((len(df), len(col)), dtype=np.int64)
    for i, body in enumerate(df.get("body", pd.Series([], dtype=str))):
        for cat, c in _match_all_categories(_process_body(body), combo).items():
            matrix[i, col[cat]] = c

    ym_series = df["date"].apply(lambda d: _ym_for_date(d, daily_tail_start))

    cat_df = pd.DataFrame(matrix, index=df.index, columns=list(combo.categories))

    e_present = cat_df["econ"] > 0
    p_present = cat_df["policy"] > 0
    u_present = cat_df["uncertain"] > 0
    epu_present = e_present & p_present & u_present

    work = pd.DataFrame(
        {
            "ym": ym_series,
            "econ": e_present,
            "policy": p_present,
            "uncertain": u_present,
            "eu": e_present & u_present,
            "pu": p_present & u_present,
            "ep": e_present & p_present,
            "epu": epu_present,
            "econ_count": cat_df["econ"],
            "policy_count": cat_df["policy"],
            "uncertain_count": cat_df["uncertain"],
        },
        index=df.index,
    )

    grouped = work.groupby("ym").agg(
        A_total=("ym", "count"),
        E_count=("econ", "sum"),
        P_count=("policy", "sum"),
        U_count=("uncertain", "sum"),
        EU_count=("eu", "sum"),
        PU_count=("pu", "sum"),
        EP_count=("ep", "sum"),
        EPU_count=("epu", "sum"),
    )

    grouped["E_kwsum"] = (
        work[work["econ"]]
        .groupby("ym")["econ_count"]
        .sum()
        .reindex(grouped.index, fill_value=0)
    )
    grouped["P_kwsum"] = (
        work[work["policy"]]
        .groupby("ym")["policy_count"]
        .sum()
        .reindex(grouped.index, fill_value=0)
    )
    grouped["U_kwsum"] = (
        work[work["uncertain"]]
        .groupby("ym")["uncertain_count"]
        .sum()
        .reindex(grouped.index, fill_value=0)
    )

    # Topic / actor counts: per-month, number of articles where (E∩P∩U∩category).
    # Plus a parallel U∩category column used by `calculate_group_uncertainty_counts`,
    # and an unconditional category column — articles mentioning the category at
    # all, with no E/P/U condition. The unconditional count is what answers "how
    # much is this topic being discussed", as opposed to "how much of the
    # uncertainty is about this topic"; the two diverge badly for topics that are
    # covered routinely rather than in moments of doubt.
    # One groupby per condition over every category at once; a groupby per
    # category took 1,700 x 3 passes per chunk once concepts arrived.
    cats = [c for c in combo.categories if c not in ("econ", "policy", "uncertain")]
    present = cat_df[cats] > 0

    def per_month(mask: pd.Series) -> pd.DataFrame:
        return (
            present[mask]
            .groupby(work.loc[mask, "ym"])
            .sum()
            .reindex(grouped.index, fill_value=0)
            .astype(int)
        )

    epu_x, u_x, g_x = (
        per_month(epu_present),
        per_month(u_present),
        per_month(pd.Series(True, index=df.index)),
    )
    columns = {}
    for cat in cats:
        base = (
            cat.replace("topic:", "topic_")
            .replace("actor:", "actor_")
            .replace("concept:", "concept_")
            .replace("group:", "group_")
        )
        columns[f"{base}_count"] = epu_x[cat]
        columns[f"{base}_U_count"] = u_x[cat]
        columns[f"{base}_A_count"] = g_x[cat]
    return pd.concat([grouped, pd.DataFrame(columns, index=grouped.index)], axis=1)


def annotate_source(
    news_csv: Path,
    source_key: str,
    bundle: KeywordBundle,
    daily_tail_start: pd.Timestamp | None = None,
    subset_start: pd.Timestamp | None = None,
    subset_end: pd.Timestamp | None = None,
    chunksize: int = 20_000,
) -> tuple[pd.DataFrame, dict]:
    """Annotate a single source's news.csv and aggregate to monthly counts.

    Reads the CSV in chunks: peak memory scales with `chunksize`, not with file
    size. ECA carries a 7.9 GB news.csv that cost >16 GB to load whole, which is
    what forced the streaming form. Dedup stays global via a hash set, so the
    result matches a whole-file `drop_duplicates()` keeping the first occurrence.

    Returns
    -------
    counts : DataFrame
        One row per (source_key, ym). Columns: source_key, ym, A_total,
        E_count, P_count, U_count, E_kwsum, P_kwsum, U_kwsum,
        EU_count, PU_count, EP_count, plus topic_<k>_count and
        actor_<k>_count for every key in the bundle.
    diagnostics : dict
        Per-source numbers used by the build summary report:
        {n_total, n_dropped_nan_body, n_dropped_nan_date, min_date, max_date}.
    """
    combo = build_combined_automaton(bundle)

    cols = pd.read_csv(news_csv, encoding="utf-8", nrows=0).columns.tolist()
    want = [c for c in ("date", "body", "language", "url") if c in cols]

    seen: set[int] = set()
    frames: list[pd.DataFrame] = []
    n_total = 0
    n_dropped_nan_date = 0
    n_dropped_nan_body = 0
    min_date = None
    max_date = None

    reader = pd.read_csv(news_csv, encoding="utf-8", usecols=want, chunksize=chunksize)
    for chunk in reader:
        # Mirror legacy EPU.process_data: dedupe on loaded columns BEFORE date
        # parsing. Hashing row content keeps that global across chunks; keeping
        # the first sighting matches drop_duplicates' default.
        hashes = pd.util.hash_pandas_object(chunk, index=False).to_numpy()
        keep = []
        for i, h in enumerate(hashes):
            if h not in seen:
                seen.add(h)
                keep.append(i)
        chunk = chunk.iloc[keep].reset_index(drop=True)

        n_total += len(chunk)
        chunk["date"] = pd.to_datetime(
            chunk.get("date"), format="mixed", errors="coerce"
        )
        n_dropped_nan_date += int(chunk["date"].isna().sum())
        chunk = chunk[~chunk["date"].isna()].reset_index(drop=True)

        if subset_start is not None:
            chunk = chunk[chunk["date"] >= subset_start]
        if subset_end is not None:
            chunk = chunk[chunk["date"] <= subset_end]
        chunk = chunk.reset_index(drop=True)

        if "body" in chunk.columns:
            n_dropped_nan_body += int(chunk["body"].isna().sum())
            chunk = chunk[~chunk["body"].isna()].reset_index(drop=True)

        if not chunk.empty:
            cmin, cmax = chunk["date"].min(), chunk["date"].max()
            min_date = cmin if min_date is None else min(min_date, cmin)
            max_date = cmax if max_date is None else max(max_date, cmax)

        frames.append(_grouped_for_frame(chunk, combo, daily_tail_start))

    if not frames:
        empty = pd.DataFrame(
            {
                "date": pd.Series([], dtype="datetime64[ns]"),
                "body": pd.Series([], dtype=object),
            }
        )
        frames.append(_grouped_for_frame(empty, combo, daily_tail_start))

    grouped = pd.concat(frames)
    grouped = grouped.groupby(level="ym").sum()

    grouped = grouped.reset_index()
    grouped.insert(0, "source_key", source_key)

    diagnostics = {
        "n_total": n_total,
        "n_dropped_nan_body": n_dropped_nan_body,
        "n_dropped_nan_date": n_dropped_nan_date,
        "min_date": min_date,
        "max_date": max_date,
    }
    return grouped, diagnostics


def annotate_country(
    sources: list[tuple[Path, str, KeywordBundle]],
    daily_tail_start: pd.Timestamp | None = None,
    subset_start: pd.Timestamp | None = None,
    subset_end: pd.Timestamp | None = None,
    max_parallel_sources: int = 1,
    progress_cb: Callable[[str], None] | None = None,
) -> tuple[pd.DataFrame, dict[str, dict]]:
    """Annotate every source for one country and concatenate the per-source frames.

    Parameters
    ----------
    sources : list of (news_csv, source_key, bundle)
    progress_cb : invoked with the ``source_key`` after each source completes.
    """
    if max_parallel_sources < 1:
        raise ValueError("max_parallel_sources must be >= 1")

    results: list[pd.DataFrame] = []
    diagnostics: dict[str, dict] = {}

    def _one(item):
        news_csv, source_key, bundle = item
        return source_key, annotate_source(
            news_csv,
            source_key,
            bundle,
            daily_tail_start=daily_tail_start,
            subset_start=subset_start,
            subset_end=subset_end,
        )

    if max_parallel_sources == 1:
        for item in sources:
            source_key, (df, diag) = _one(item)
            results.append(df)
            diagnostics[source_key] = diag
            if progress_cb is not None:
                progress_cb(source_key)
    else:
        with ThreadPoolExecutor(max_workers=max_parallel_sources) as pool:
            for source_key, (df, diag) in pool.map(_one, sources):
                results.append(df)
                diagnostics[source_key] = diag
                if progress_cb is not None:
                    progress_cb(source_key)

    if not results:
        return pd.DataFrame(), diagnostics
    return pd.concat(results, ignore_index=True), diagnostics
