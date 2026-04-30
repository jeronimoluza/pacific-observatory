"""New per-unit orchestration: annotate (full or tail) → standardize → write outputs.

Replaces the legacy `process_unit` flow that used the EPU class with
preloaded article DataFrames. The new flow uses `source_counts.parquet`
as the per-country atomic artifact and computes aggregates by concatenating
constituent country counts on the fly (no aggregate cache).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd

from src.text.analysis import annotate, source_counts
from src.text.analysis.outputs import build_outputs
from src.text.analysis.standardize import standardize_unit
from src.text.analysis.utils import LANGUAGE_ALIASES, load_all_groups

KEYWORDS_ROOT = Path(__file__).parent / "keywords"

_logger = logging.getLogger("po.text.build")


# ── Diagnostics frozen for the summary report ────────────────────────


class UnitDiagnostics(dict):
    """Per-unit diagnostics captured during build (article counts, sources
    excluded from baseline, NaN drops, mode, runtime, status)."""

    def __init__(self):
        super().__init__()
        self["sources"] = {}
        self["mode"] = "unknown"
        self["status"] = "ok"
        self["error"] = None
        self["excluded_sources"] = []
        self["total_articles"] = 0


# ── Helpers ──────────────────────────────────────────────────────────


def _country_dir_for_path(news_csv: Path) -> Path:
    return news_csv.parent.parent


def _country_cache_dir(country_dir: Path, data_root: Path, cache_root: Path) -> Path:
    rel = country_dir.relative_to(data_root)
    return cache_root / rel


def _languages_used(source_languages: dict[str, str]) -> set[str]:
    return {LANGUAGE_ALIASES.get(lang, lang) for lang in source_languages.values()}


def _bundle_for_language(language: str) -> annotate.KeywordBundle:
    return annotate.KeywordBundle.for_language(language)


def _group_news_dirs_by_country(news_dirs: Iterable[Path]) -> dict[Path, list[Path]]:
    """Aggregate units span multiple countries — group news.csv paths by country dir."""
    grouped: dict[Path, list[Path]] = defaultdict(list)
    for fp in news_dirs:
        grouped[_country_dir_for_path(fp)].append(fp)
    return dict(grouped)


# ── Annotation gate (decides full / tail / skip) ─────────────────────


def _ensure_country_source_counts(
    country_dir: Path,
    cache_dir: Path,
    news_dirs: list[Path],
    source_languages: dict[str, str],
    daily_tail_start: pd.Timestamp | None,
    subset_start: pd.Timestamp | None,
    subset_end: pd.Timestamp | None,
    max_parallel_sources: int,
    diagnostics: UnitDiagnostics,
    progress_cb: Callable[[int], None] | None = None,
    file_articles: dict[Path, int] | None = None,
) -> pd.DataFrame:
    """Ensure the country's `source_counts.parquet` is current and return it.

    Decides whether to do a full re-annotate, an incremental tail-only
    annotate, or to reuse the cache as-is, based on the staleness predicate
    and per-source tail extensions.

    Mutates `diagnostics["mode"]` to one of: "full", "incremental", "reused".
    """
    source_keys = sorted(_source_key(fp) for fp in news_dirs)
    languages = _languages_used(source_languages)
    keyword_hashes = source_counts.keyword_hash_bundle(KEYWORDS_ROOT, languages)

    sk_to_fp = {_source_key(fp): fp for fp in news_dirs}

    def _advance(source_key: str) -> None:
        if progress_cb is None or file_articles is None:
            return
        fp = sk_to_fp.get(source_key)
        if fp is not None:
            progress_cb(int(file_articles.get(fp, 0)))

    cached_df, cached_params = source_counts.read_source_counts(cache_dir)
    stale, reason = source_counts.is_stale(cached_params, source_keys, keyword_hashes)

    if stale:
        diagnostics["mode"] = "full"
        diagnostics["staleness_reason"] = reason
        bundles = {lang: _bundle_for_language(lang) for lang in languages}
        sources = [
            (
                fp,
                _source_key(fp),
                bundles[
                    LANGUAGE_ALIASES.get(
                        source_languages.get(str(fp), "en"),
                        source_languages.get(str(fp), "en"),
                    )
                ],
            )
            for fp in news_dirs
        ]
        df_full, source_diags = annotate.annotate_country(
            sources,
            daily_tail_start=daily_tail_start,
            subset_start=subset_start,
            subset_end=subset_end,
            max_parallel_sources=max_parallel_sources,
            progress_cb=_advance,
        )
        for k, v in source_diags.items():
            diagnostics["sources"][k] = v
            diagnostics["total_articles"] += v.get("n_total", 0)

        new_tails = {
            sk: {
                "last_date": (
                    diag["max_date"].strftime("%Y-%m-%d")
                    if diag.get("max_date") is not None
                    else None
                ),
                "n_rows": int(diag.get("n_total", 0)),
            }
            for sk, diag in source_diags.items()
        }
        params_obj = source_counts.SourceCountsParams(
            schema_version=source_counts.SCHEMA_VERSION,
            source_set=source_keys,
            keyword_hashes=keyword_hashes,
            tails=new_tails,
        )
        source_counts.write_source_counts(cache_dir, df_full, params_obj)
        return df_full

    # Tail-only path: check whether any source has new rows past the cached tail.
    sources_to_extend: list[tuple[Path, str, annotate.KeywordBundle, pd.Timestamp]] = []
    bundles = {lang: _bundle_for_language(lang) for lang in languages}
    for fp in news_dirs:
        sk = _source_key(fp)
        ext = source_counts.tail_extension(fp, cached_params, sk)
        if ext is None:
            continue
        cutoff, n_new = ext
        if cutoff is None or n_new <= 0:
            continue
        lang = LANGUAGE_ALIASES.get(
            source_languages.get(str(fp), "en"), source_languages.get(str(fp), "en")
        )
        sources_to_extend.append((fp, sk, bundles[lang], cutoff))

    if not sources_to_extend:
        diagnostics["mode"] = "reused"
        for sk in source_keys:
            _advance(sk)
        return cached_df

    diagnostics["mode"] = "incremental"
    extended_keys = {sk for _, sk, _, _ in sources_to_extend}
    for sk in source_keys:
        if sk not in extended_keys:
            _advance(sk)
    extended_frames: list[pd.DataFrame] = []
    new_tails = dict(cached_params.tails)
    for fp, sk, bundle, cutoff in sources_to_extend:
        # Only annotate rows strictly after the cached tail.
        df_new, diag = annotate.annotate_source(
            fp,
            sk,
            bundle,
            daily_tail_start=daily_tail_start,
            subset_start=cutoff + pd.Timedelta(days=1),
            subset_end=subset_end,
        )
        diagnostics["sources"][sk] = diag
        diagnostics["total_articles"] += diag.get("n_total", 0)
        _advance(sk)
        extended_frames.append(df_new)
        if diag.get("max_date") is not None:
            new_tails[sk] = {
                "last_date": diag["max_date"].strftime("%Y-%m-%d"),
                "n_rows": int(diag.get("n_total", 0))
                + int(new_tails.get(sk, {}).get("n_rows", 0)),
            }

    # Replace the cached tail rows for affected sources with the new ones.
    if extended_frames:
        new_rows = pd.concat(extended_frames, ignore_index=True)
        # Per affected source, drop cached rows whose ym is newer than the cutoff
        # (we re-annotated those rows). For simplicity we drop the affected
        # source's rows beyond the smallest cutoff per source and append.
        merged = pd.concat([cached_df, new_rows], ignore_index=True)
        # Last-write-wins on (source_key, ym) key.
        merged = merged.drop_duplicates(subset=["source_key", "ym"], keep="last")
        df_out = merged
    else:
        df_out = cached_df

    params_obj = source_counts.SourceCountsParams(
        schema_version=source_counts.SCHEMA_VERSION,
        source_set=source_keys,
        keyword_hashes=keyword_hashes,
        tails=new_tails,
    )
    source_counts.write_source_counts(cache_dir, df_out, params_obj)
    return df_out


def _source_key(news_csv: Path) -> str:
    """Mirror baseline.source_key_for_news_path."""
    country = news_csv.parent.parent.name
    newspaper = news_csv.parent.name.replace(country, "").strip("_")
    return f"{country}_{newspaper}"


# ── Per-unit entry point ─────────────────────────────────────────────


def process_unit_v2(
    name: str,
    level: str,
    news_dirs: list[Path],
    output_dir: Path,
    cache_dir: Path,
    cutoff_start_date: str | None,
    cutoff_end_date: str | None,
    subset_condition: str,
    source_languages: dict[str, str],
    max_parallel_sources: int,
    data_root: Path,
    cache_root: Path,
    progress_cb: Callable[[int], None] | None = None,
    file_articles: dict[Path, int] | None = None,
) -> UnitDiagnostics:
    """Process a single unit (country / subregion / region aggregate).

    Returns the per-unit diagnostics dict.
    """
    diagnostics = UnitDiagnostics()
    diagnostics["name"] = name
    diagnostics["level"] = level
    diagnostics["n_sources"] = len(news_dirs)

    today = pd.Timestamp.today()
    current_tail_start = today.replace(day=1).strftime("%Y-%m-%d")
    daily_tail_ts = pd.Timestamp(current_tail_start)

    # Subset: subset_condition is a pandas-style "date >= ... and date <= ..."
    subset_start, subset_end = _parse_subset_condition(subset_condition)

    all_topics = load_all_groups("topics")
    all_actors = load_all_groups("actors")

    # Country units write directly to their own cache_dir; aggregate units
    # don't have a cache — they read from constituent countries.
    if level == "country":
        df = _ensure_country_source_counts(
            country_dir=news_dirs[0].parent.parent,
            cache_dir=cache_dir,
            news_dirs=news_dirs,
            source_languages=source_languages,
            daily_tail_start=daily_tail_ts,
            subset_start=subset_start,
            subset_end=subset_end,
            max_parallel_sources=max_parallel_sources,
            diagnostics=diagnostics,
            progress_cb=progress_cb,
            file_articles=file_articles,
        )
    else:
        # Aggregate: ensure each constituent country has source_counts; auto-build.
        diagnostics["mode"] = "aggregate"
        per_country = _group_news_dirs_by_country(news_dirs)
        country_frames: list[pd.DataFrame] = []
        for country_dir, fps in per_country.items():
            country_cache = _country_cache_dir(country_dir, data_root, cache_root)
            country_langs = {str(fp): source_languages.get(str(fp), "en") for fp in fps}
            sub_diag = UnitDiagnostics()
            sub_diag["name"] = country_dir.name
            df_country = _ensure_country_source_counts(
                country_dir=country_dir,
                cache_dir=country_cache,
                news_dirs=fps,
                source_languages=country_langs,
                daily_tail_start=daily_tail_ts,
                subset_start=subset_start,
                subset_end=subset_end,
                max_parallel_sources=max_parallel_sources,
                diagnostics=sub_diag,
                progress_cb=progress_cb,
                file_articles=file_articles,
            )
            country_frames.append(df_country)
            for k, v in sub_diag["sources"].items():
                diagnostics["sources"][k] = v
            diagnostics["total_articles"] += sub_diag["total_articles"]
        df = (
            pd.concat(country_frames, ignore_index=True)
            if country_frames
            else pd.DataFrame()
        )

    if df.empty:
        diagnostics["status"] = "skipped"
        diagnostics["error"] = "no source_counts available"
        return diagnostics

    if "A_total" in df.columns:
        diagnostics["total_articles"] = int(df["A_total"].sum())

    # Standardize and write outputs.
    bundle = standardize_unit(
        source_counts=df,
        cutoff_start=cutoff_start_date,
        cutoff_end=cutoff_end_date,
        daily_tail_start=current_tail_start,
        topic_keys=list(all_topics.keys()),
        actor_keys=list(all_actors.keys()),
    )
    build_outputs(
        e_base=bundle["e_base"],
        topic_epus=bundle["topic_epus"],
        actor_epus=bundle["actor_epus"],
        ug_counts_all=bundle["ug_counts_all"],
        cutoff_start_date=cutoff_start_date,
        cutoff_end_date=cutoff_end_date,
        daily_tail_start=current_tail_start,
        country_name=name,
        full_write=True,
        replace_from=None,
        output_dir=output_dir,
    )
    return diagnostics


# ── Helpers ──────────────────────────────────────────────────────────


def _parse_subset_condition(
    condition: str | None,
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Extract start/end timestamps from a `date >= 'YYYY-MM-DD' and date <= '...'` string.

    Falls back to (None, None) if parsing fails — the annotator then sees no
    subset bounds and uses every available row.
    """
    if not condition:
        return None, None
    import re

    start = None
    end = None
    m = re.search(r"date\s*>=\s*'(\d{4}-\d{2}-\d{2})'", condition)
    if m:
        start = pd.Timestamp(m.group(1))
    m = re.search(r"date\s*<=\s*'(\d{4}-\d{2}-\d{2})'", condition)
    if m:
        end = pd.Timestamp(m.group(1))
    return start, end
