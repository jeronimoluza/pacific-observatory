"""Annotation cache gate: decides full / tail / skip for a country's source_counts.

Split out of ``orchestrator.py`` (TX-20) without changing behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

from src.text.analysis import annotate, source_counts
from src.text.analysis.utils import LANGUAGE_ALIASES
from src.text.source_keys import source_key

KEYWORDS_ROOT = Path(__file__).parent / "keywords"


def _languages_used(source_languages: dict[str, str]) -> set[str]:
    return {LANGUAGE_ALIASES.get(lang, lang) for lang in source_languages.values()}


def _bundle_for_language(language: str) -> annotate.KeywordBundle:
    return annotate.KeywordBundle.for_language(language)


def _dedup_source_counts(
    df: pd.DataFrame, daily_tail_start: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Normalize ym, roll past daily rows into months, drop (source_key, date) duplicates.

    The cache can carry monthly ym in two forms ("2026-4" and "2026-04") plus
    daily form ("2026-04-01") — leftover from past builds when daily_tail_start
    moved or different code paths produced different paddings. Two distinct ym
    strings that resolve to the same date break the pivot in
    standardize.pivot_to_wide. Normalize monthly ym to zero-padded ("2026-04")
    and dedupe by (source_key, date), keeping the daily form when both monthly
    and daily exist for the same date.

    Rows dated before ``daily_tail_start`` are summed into one monthly row per
    source. When the tail moves forward a month, the old tail month is cached
    as daily rows, and incremental annotation adds the late articles of that
    month as a separate monthly row. The pivot's index only has the 1st of a
    past month, so without the roll-up every day but the 1st was dropped: on
    2026-10-05 September kept ~3% of its articles. Past-month rows are
    disjoint article sets (incremental annotation replaces a source's cells from
    its start month on), so summing is exact.
    """
    if (
        df is None
        or df.empty
        or "ym" not in df.columns
        or "source_key" not in df.columns
    ):
        return df
    work = df.copy()
    ym_str = work["ym"].astype(str)
    # Normalize monthly form: "YYYY-M" or "YYYY-MM" → "YYYY-MM"
    monthly_mask = ym_str.str.fullmatch(r"\d{4}-\d{1,2}")
    if monthly_mask.any():
        normalized = ym_str.where(~monthly_mask).copy()
        parts = ym_str[monthly_mask].str.split("-", expand=True)
        normalized.loc[monthly_mask] = parts[0] + "-" + parts[1].str.zfill(2)
        work["ym"] = normalized
    work["_date"] = pd.to_datetime(work["ym"], format="mixed")
    if daily_tail_start is not None:
        past = work["_date"] < daily_tail_start
        if past.any():
            rolled = work[past].copy()
            rolled["ym"] = rolled["_date"].dt.strftime("%Y-%m")
            metric_cols = [
                c for c in work.columns if c not in ("source_key", "ym", "_date")
            ]
            rolled = rolled.groupby(["source_key", "ym"], as_index=False)[
                metric_cols
            ].sum()
            rolled["_date"] = pd.to_datetime(rolled["ym"], format="%Y-%m")
            work = pd.concat([rolled, work[~past]], ignore_index=True)[
                list(df.columns) + ["_date"]
            ]
    work["_len"] = work["ym"].astype(str).str.len()
    work = (
        work.sort_values(["source_key", "_date", "_len"], kind="stable")
        .drop_duplicates(subset=["source_key", "_date"], keep="last")
        .drop(columns=["_date", "_len"])
        .reset_index(drop=True)
    )
    return work


def _daily_backfill_cutoff(cached_df, daily_tail_start):
    """Cutoff forcing re-annotation of a tail month cached at monthly grain.

    Returns the day before ``daily_tail_start`` when the cache holds rows on or
    after the tail but none of them are in daily form, and ``None`` otherwise.
    Being derived from the cache keeps this idempotent: once the month has been
    re-annotated the daily rows are present and no further backfill fires.
    """
    if daily_tail_start is None or cached_df is None or cached_df.empty:
        return None
    if "ym" not in cached_df.columns:
        return None
    ym = cached_df["ym"].astype(str)
    dates = pd.to_datetime(ym, format="mixed", errors="coerce")
    at_or_after = dates >= daily_tail_start
    if not at_or_after.any():
        return None
    if ((ym.str.len() > 7) & at_or_after).any():
        return None
    return daily_tail_start - pd.Timedelta(days=1)


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
    diagnostics: dict,
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

    # The tail can move backwards, because it follows the newest article rather
    # than the calendar. When it does, the month it lands on is already cached
    # at monthly grain, and no month's count has moved, so the lateness check
    # below finds nothing and the daily rows never appear.
    # Re-annotate that month at daily grain instead. This reads the need off
    # the cache itself rather than a stored tail, so caches written before the
    # tail became data-driven need no migration.
    backfill_cutoff = _daily_backfill_cutoff(cached_df, daily_tail_start)
    cached_norm = _dedup_source_counts(cached_df, daily_tail_start)

    # Lateness window (TX-23): a source is re-annotated from the first month
    # whose row count in news.csv differs from its cached A_total. That catches
    # rows past the tail and rows merged late with a date at or before it.
    sources_to_extend: list[tuple[Path, str, annotate.KeywordBundle, pd.Timestamp]] = []
    bundles = {lang: _bundle_for_language(lang) for lang in languages}
    for fp in news_dirs:
        sk = _source_key(fp)
        start = source_counts.first_stale_month(
            fp, cached_norm[cached_norm["source_key"] == sk], subset_start, subset_end
        )
        if backfill_cutoff is not None:
            backfill_start = backfill_cutoff + pd.Timedelta(days=1)
            start = backfill_start if start is None else min(start, backfill_start)
        if start is None:
            continue
        lang = LANGUAGE_ALIASES.get(
            source_languages.get(str(fp), "en"), source_languages.get(str(fp), "en")
        )
        sources_to_extend.append((fp, sk, bundles[lang], start))

    if not sources_to_extend:
        diagnostics["mode"] = "reused"
        for sk in source_keys:
            _advance(sk)
        return cached_norm

    diagnostics["mode"] = "incremental"
    extended_keys = {sk for _, sk, _, _ in sources_to_extend}
    for sk in source_keys:
        if sk not in extended_keys:
            _advance(sk)
    extended_frames: list[pd.DataFrame] = []
    new_tails = dict(cached_params.tails)
    cached_dates = pd.to_datetime(cached_norm["ym"].astype(str), format="mixed")
    replaced = pd.Series(False, index=cached_norm.index)
    for fp, sk, bundle, start in sources_to_extend:
        df_new, diag = annotate.annotate_source(
            fp,
            sk,
            bundle,
            daily_tail_start=daily_tail_start,
            subset_start=start if subset_start is None else max(start, subset_start),
            subset_end=subset_end,
        )
        diagnostics["sources"][sk] = diag
        diagnostics["total_articles"] += diag.get("n_total", 0)
        _advance(sk)
        extended_frames.append(df_new)
        replaced |= (cached_norm["source_key"] == sk) & (cached_dates >= start)
        new_tails[sk] = {
            "last_date": (
                diag["max_date"].strftime("%Y-%m-%d")
                if diag.get("max_date") is not None
                else new_tails.get(sk, {}).get("last_date")
            ),
            # n_total counts the whole deduped file, before the subset
            # filter, so it replaces the cached count rather than adding to it.
            "n_rows": int(diag.get("n_total", 0)),
        }

    # Replace, never append: the source's cached cells from its start month on
    # give way to the re-annotated ones.
    new_rows = pd.concat(extended_frames, ignore_index=True)
    merged = pd.concat([cached_norm[~replaced], new_rows], ignore_index=True)
    df_out = _dedup_source_counts(merged, daily_tail_start)

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
    return source_key(news_csv)
