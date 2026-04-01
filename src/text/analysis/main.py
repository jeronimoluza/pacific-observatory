import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

# Setup path before imports
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.text.analysis.outputs import (  # noqa: E402
    build_outputs,
    collect_params,
    json_default,
)
from src.text.analysis.runners import (  # noqa: E402
    run_full_epu,
    run_full_groups_only,
    run_incremental_epu,
)
from src.text.analysis.translate_keywords import translate_keywords  # noqa: E402
from src.text.analysis.utils import load_all_groups  # noqa: E402

PROJECT_ROOT = _PROJECT_ROOT
DATA_ROOT = PROJECT_ROOT / "data" / "text"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "text"
CACHE_DIR = PROJECT_ROOT / "data" / "text" / "cache"
TEXT_CONFIGS_DIR = PROJECT_ROOT / "src" / "text" / "configs"

EXCLUDED_COUNTRIES = {}
REQUIRED_COLUMNS = {"url", "date", "title", "body", "_scraped_at"}


# ── Validation ────────────────────────────────────────────────────────


def _validate_news_files(news_dirs: list[Path], yes: bool = False) -> list[Path]:
    """Validate news.csv files: check required columns, count NaN, ask to drop.

    Returns the list of valid news.csv paths (unchanged — NaN rows are dropped
    during EPU processing, not here, but the user is warned).
    """
    if not news_dirs:
        return news_dirs

    stats = []
    total_rows = 0
    nan_rows = 0

    for fp in news_dirs:
        # Check required columns
        try:
            cols = set(pd.read_csv(fp, nrows=0, encoding="utf-8").columns)
        except Exception:
            print(f"  ERROR: cannot read {fp}")
            continue
        missing = REQUIRED_COLUMNS - cols
        if missing:
            raise ValueError(
                f"{fp.parent.name}/news.csv is missing required column(s): "
                f"{', '.join(sorted(missing))}"
            )

        # Count NaN in date and body (single pass)
        try:
            df = pd.read_csv(fp, usecols=["date", "body"], encoding="utf-8")
            n = len(df)
            no_date = int(df["date"].isna().sum())
            no_body = int(df["body"].isna().sum())
            total_rows += n
            nan_rows += int((df["date"].isna() | df["body"].isna()).sum())
            stats.append((fp.parent.name, n, no_date, no_body))
        except Exception:
            stats.append((fp.parent.name, 0, 0, 0))

    has_nan = any(nd > 0 or nb > 0 for _, _, nd, nb in stats)
    if has_nan:
        print()
        print(f"  {'Source':<35} {'Rows':>6} {'No date':>8} {'No body':>8}")
        print("  " + "-" * 60)
        for name, n, nd, nb in stats:
            if nd > 0 or nb > 0:
                print(f"  {name:<35} {n:>6} {nd:>8} {nb:>8}")
        pct = (nan_rows / total_rows * 100) if total_rows > 0 else 0
        print(
            f"  {nan_rows} rows have missing date or body "
            f"({pct:.1f}% of {total_rows} total)."
        )
        if not yes:
            import click

            click.confirm(
                "  Drop these rows before calculating EPU?",
                default=True,
                abort=True,
            )
        else:
            print("  Auto-dropping rows with missing date or body (--yes).")

    return news_dirs


def _check_cutoff_coherence(
    news_dirs: list[Path], cutoff: str, yes: bool = False
) -> list[Path]:
    """Check if any source's data starts after the cutoff date.

    Returns the filtered list of news.csv paths (sources outside cutoff excluded).
    """
    cutoff_ts = pd.Timestamp(cutoff)
    valid = []
    excluded = []

    for fp in news_dirs:
        try:
            dates = pd.read_csv(fp, usecols=["date"], encoding="utf-8")["date"]
            dates = pd.to_datetime(dates, format="mixed", errors="coerce").dropna()
            if dates.empty:
                excluded.append((fp, "no valid dates"))
                continue
            min_date = dates.min()
            if min_date > cutoff_ts:
                excluded.append((fp, f"data starts {min_date.date()}"))
            else:
                valid.append(fp)
        except Exception:
            excluded.append((fp, "cannot read"))

    if excluded:
        for fp, reason in excluded:
            print(
                f"  WARNING: '{fp.parent.name}' — {reason}, after cutoff {cutoff}. "
                f"The standardization period has no data for this source, so its "
                f"standard deviation cannot be computed. This source will be excluded "
                f"from the index."
            )
        msg = (
            f"  Excluding {len(excluded)} source(s). "
            f"Continue with {len(valid)} remaining?"
        )
        if not yes:
            import click

            click.confirm(msg, default=True, abort=True)
        else:
            print(msg + " (--yes)")

    return valid


# ── Discovery ─────────────────────────────────────────────────────────


def _get_country_dirs(exclude_countries: set[str] | None = None) -> list[Path]:
    excluded = {name.lower() for name in EXCLUDED_COUNTRIES}
    if exclude_countries:
        excluded |= {name.lower() for name in exclude_countries}

    country_dirs = []
    if not DATA_ROOT.exists():
        return country_dirs
    for region_dir in sorted(DATA_ROOT.iterdir()):
        if not region_dir.is_dir() or region_dir.name.startswith((".", "_", "cache")):
            continue
        for subregion_dir in sorted(region_dir.iterdir()):
            if not subregion_dir.is_dir() or subregion_dir.name.startswith((".", "_")):
                continue
            for country_dir in sorted(subregion_dir.iterdir()):
                if country_dir.is_dir() and country_dir.name.lower() not in excluded:
                    country_dirs.append(country_dir)
    return country_dirs


def _source_language(news_csv: Path) -> str:
    """Get language for a source from its YAML config."""
    try:
        parts = news_csv.relative_to(DATA_ROOT).parts
    except ValueError:
        return "en"
    if len(parts) >= 5:
        config_path = (
            TEXT_CONFIGS_DIR / parts[0] / parts[1] / parts[2] / f"{parts[3]}.yaml"
        )
        if config_path.exists():
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            return cfg.get("language", "en")
    return "en"


def _discover_units(
    country_dirs: list[Path],
    include_aggregates: bool = True,
) -> list[dict]:
    """Build ordered list of processing units from country data directories.

    Returns units in processing order: countries first, then subregion
    aggregates, then region aggregates.
    """
    from collections import defaultdict

    units = []

    for d in country_dirs:
        rgn = d.parent.parent.name
        sub = d.parent.name
        ctry = d.name
        news_dirs = sorted(d.glob("*/news.csv"))
        if news_dirs:
            src_langs = {str(fp): _source_language(fp) for fp in news_dirs}
            units.append(
                {
                    "name": ctry,
                    "level": "country",
                    "news_dirs": news_dirs,
                    "output_dir": OUTPUT_DIR / rgn / sub / ctry,
                    "cache_dir": CACHE_DIR / rgn / sub / ctry,
                    "source_languages": src_langs,
                }
            )

    if not include_aggregates:
        return units

    subregion_groups = defaultdict(list)
    for d in country_dirs:
        subregion_groups[(d.parent.parent.name, d.parent.name)].append(d)

    for (rgn, sub), dirs in sorted(subregion_groups.items()):
        all_news = []
        for d in dirs:
            all_news.extend(sorted(d.glob("*/news.csv")))
        if all_news:
            src_langs = {str(fp): _source_language(fp) for fp in all_news}
            units.append(
                {
                    "name": f"{sub} (aggregate)",
                    "level": "subregion",
                    "news_dirs": all_news,
                    "output_dir": OUTPUT_DIR / rgn / sub / "_aggregate",
                    "cache_dir": CACHE_DIR / rgn / sub / "_aggregate",
                    "source_languages": src_langs,
                }
            )

    region_groups = defaultdict(list)
    for d in country_dirs:
        region_groups[d.parent.parent.name].append(d)

    for rgn, dirs in sorted(region_groups.items()):
        all_news = []
        for d in dirs:
            all_news.extend(sorted(d.glob("*/news.csv")))
        if all_news:
            src_langs = {str(fp): _source_language(fp) for fp in all_news}
            units.append(
                {
                    "name": f"{rgn} (aggregate)",
                    "level": "region",
                    "news_dirs": all_news,
                    "output_dir": OUTPUT_DIR / rgn / "_aggregate",
                    "cache_dir": CACHE_DIR / rgn / "_aggregate",
                    "source_languages": src_langs,
                }
            )

    return units


# ── Redo helper ───────────────────────────────────────────────────────


def _redo_groups(
    group_type,
    groups_subset,
    news_dirs,
    cutoff,
    subset_condition,
    daily_tail_start,
    params,
    cache_df,
    tail_ts,
    output_dir,
    source_languages,
):
    """Recompute full-history for specific groups and update cache/params/CSVs.

    Args:
        group_type: "topics" or "actors".
        groups_subset: dict of group_key -> additional_terms to recompute.
        params: params dict (mutated in place).
        cache_df: cache DataFrame (new version returned).

    Returns updated cache_df.
    """
    params_key = f"{group_type}_epu"
    csv_name = f"{group_type}_epu.csv"

    print(f"  [redo] recomputing {group_type}: {', '.join(sorted(groups_subset))}")
    redo_epus = run_full_groups_only(
        news_dirs,
        cutoff,
        subset_condition,
        daily_tail_start,
        groups_subset,
        source_languages=source_languages,
    )

    # Overwrite params
    params.setdefault(params_key, {})
    for k, e in redo_epus.items():
        params[params_key][k] = e.params

    # Patch cache
    for k, e in redo_epus.items():
        col = f"EPU_{k}_index"
        pre = e.epu_stats[e.epu_stats["date"] < tail_ts][
            ["date", "epu_weighted"]
        ].rename(columns={"epu_weighted": col})
        cache_df = cache_df.drop(columns=[col], errors="ignore")
        cache_df = cache_df.merge(pre, on="date", how="left")

    # Overwrite columns in output CSV
    csv_path = output_dir / "epu" / csv_name
    if csv_path.exists():
        existing_csv = pd.read_csv(csv_path, encoding="utf-8")
        existing_csv["date"] = pd.to_datetime(existing_csv["date"])
        for k, e in redo_epus.items():
            col = f"EPU_{k}_index"
            new_col_df = e.epu_stats[["date", "epu_weighted"]].rename(
                columns={"epu_weighted": col}
            )
            existing_csv = existing_csv.drop(columns=[col], errors="ignore")
            existing_csv = existing_csv.merge(new_col_df, on="date", how="left")
        existing_csv["date"] = existing_csv["date"].dt.strftime("%Y-%m-%d")
        existing_csv.to_csv(csv_path, index=False, encoding="utf-8")
        print(f"  {csv_name} updated for: {', '.join(sorted(groups_subset))}")

    return cache_df


# ── Orchestration ─────────────────────────────────────────────────────


def process_unit(
    name: str,
    news_dirs: list[Path],
    output_dir: Path,
    cache_dir: Path,
    cutoff: str,
    subset_condition: str,
    recalculate_params: bool = False,
    redo_topics: set[str] | None = None,
    redo_actors: set[str] | None = None,
    yes: bool = False,
    source_languages: dict[str, str] | None = None,
):
    """Process all EPU and uncertainty attribution indices for a unit.

    A unit can be a country, subregion aggregate, or region aggregate.

    Full mode (no cache or --recalculate-params): reads all articles, writes
    params.json and epu_stats_cache.csv.

    Incremental mode (cache exists): reads only current-month articles, applies
    stored sigma/scaling from params.json, prepends cached pre-tail rows.
    """
    country_name = name
    params_path = cache_dir / "params.json"
    cache_path = cache_dir / "epu_stats_cache.csv"

    today = pd.Timestamp.today()
    daily_tail_start = today.replace(day=1).strftime("%Y-%m-%d")
    all_topics = load_all_groups("topics")
    all_actors = load_all_groups("actors")

    # ── Summary: article counts and date range per source ────────────
    total_articles = 0
    min_date_all, max_date_all = None, None
    for fp in news_dirs:
        try:
            dates = pd.read_csv(fp, usecols=["date"], encoding="utf-8")["date"]
            dates = pd.to_datetime(dates, format="mixed", errors="coerce").dropna()
            n = len(dates)
            total_articles += n
            source_name = fp.parent.name
            if n > 0:
                lo, hi = dates.min(), dates.max()
                print(f"  {source_name}: {n} articles ({lo.date()} to {hi.date()})")
                min_date_all = lo if min_date_all is None else min(min_date_all, lo)
                max_date_all = hi if max_date_all is None else max(max_date_all, hi)
            else:
                print(f"  {source_name}: 0 articles")
        except Exception:
            print(f"  {fp.parent.name}: unable to read")
    if min_date_all is not None:
        print(
            f"  total: {total_articles} articles "
            f"({min_date_all.date()} to {max_date_all.date()})"
        )
    else:
        print(f"  total: {total_articles} articles")

    # ── Data validation ──────────────────────────────────────────────
    news_dirs = _validate_news_files(news_dirs, yes=yes)
    if not news_dirs:
        print(f"  No valid news files for {name}. Skipping.")
        return
    news_dirs = _check_cutoff_coherence(news_dirs, cutoff, yes=yes)
    if not news_dirs:
        print(f"  All sources excluded for {name}. Skipping.")
        return

    # ── Redo branch: selectively recompute specific topics/actors ────
    if redo_topics or redo_actors:
        if not (params_path.exists() and cache_path.exists()):
            raise RuntimeError(
                f"No cache found for '{country_name}'. "
                "Run without --redo-* first to build the initial cache."
            )

        params = json.loads(params_path.read_text(encoding="utf-8"))
        cache_df = pd.read_csv(cache_path, encoding="utf-8", low_memory=False)
        cache_df["date"] = pd.to_datetime(cache_df["date"])
        tail_ts = pd.Timestamp(daily_tail_start)

        if redo_topics:
            topics_subset = {k: all_topics[k] for k in redo_topics}
            cache_df = _redo_groups(
                "topics",
                topics_subset,
                news_dirs,
                cutoff,
                subset_condition,
                daily_tail_start,
                params,
                cache_df,
                tail_ts,
                output_dir,
                source_languages,
            )

        if redo_actors:
            actors_subset = {k: all_actors[k] for k in redo_actors}
            cache_df = _redo_groups(
                "actors",
                actors_subset,
                news_dirs,
                cutoff,
                subset_condition,
                daily_tail_start,
                params,
                cache_df,
                tail_ts,
                output_dir,
                source_languages,
            )

        with open(params_path, "w", encoding="utf-8") as f:
            json.dump(params, f, indent=2, default=json_default)
        cache_df.to_csv(cache_path, index=False, encoding="utf-8")
        print("  params.json and cache updated")
        return

    use_cache = params_path.exists() and cache_path.exists() and not recalculate_params

    # Read params once for all cache checks
    params = None
    if use_cache:
        params = json.loads(params_path.read_text(encoding="utf-8"))
        cached_sources = set(params.get("sources", []))
        current_sources = set()
        for fp in news_dirs:
            _country = fp.parent.parent.name
            _newspaper = fp.parent.name.replace(_country, "").strip("_")
            current_sources.add(f"{_country}_{_newspaper}")
        new_sources = current_sources - cached_sources
        if new_sources:
            print(
                f"  [cache] new sources detected: {', '.join(sorted(new_sources))}; "
                "forcing full recompute"
            )
            use_cache = False
            params = None

    # Optional backfill when new topics or actors are added
    missing_topic_epus_full = {}
    missing_actor_epus_full = {}
    if use_cache:
        have_topics = set((params.get("topics_epu") or {}).keys())
        want_topics = set(all_topics.keys())
        missing_topics = sorted(want_topics - have_topics)

        have_actors = set((params.get("actors_epu") or {}).keys())
        want_actors = set(all_actors.keys())
        missing_actors = sorted(want_actors - have_actors)

        # Read cache_df once for both backfill blocks
        cache_df = None
        tail_ts = pd.Timestamp(daily_tail_start)

        if missing_topics:
            print(
                "  [cache] missing topic params; recomputing only missing topics: "
                + ", ".join(missing_topics)
            )
            topics_subset = {k: all_topics[k] for k in missing_topics}
            missing_topic_epus_full = run_full_groups_only(
                news_dirs,
                cutoff,
                subset_condition,
                daily_tail_start,
                topics_subset,
                source_languages=source_languages,
            )
            params.setdefault("topics_epu", {})
            for k, e_topic in missing_topic_epus_full.items():
                params["topics_epu"][k] = e_topic.params

            if cache_df is None:
                cache_df = pd.read_csv(cache_path, encoding="utf-8", low_memory=False)
                cache_df["date"] = pd.to_datetime(cache_df["date"])
            for k, e_topic in missing_topic_epus_full.items():
                col = f"EPU_{k}_index"
                topic_pre = e_topic.epu_stats[e_topic.epu_stats["date"] < tail_ts][
                    ["date", "epu_weighted"]
                ].rename(columns={"epu_weighted": col})
                cache_df = cache_df.drop(columns=[col], errors="ignore")
                cache_df = cache_df.merge(topic_pre, on="date", how="left")
            print(f"  params.json updated with {len(missing_topics)} topics")

        if missing_actors:
            print(
                "  [cache] missing actor params; recomputing only missing actors: "
                + ", ".join(missing_actors)
            )
            actors_subset = {k: all_actors[k] for k in missing_actors}
            missing_actor_epus_full = run_full_groups_only(
                news_dirs,
                cutoff,
                subset_condition,
                daily_tail_start,
                actors_subset,
                source_languages=source_languages,
            )
            params.setdefault("actors_epu", {})
            for k, e_actor in missing_actor_epus_full.items():
                params["actors_epu"][k] = e_actor.params

            if cache_df is None:
                cache_df = pd.read_csv(cache_path, encoding="utf-8", low_memory=False)
                cache_df["date"] = pd.to_datetime(cache_df["date"])
            for k, e_actor in missing_actor_epus_full.items():
                col = f"EPU_{k}_index"
                actor_pre = e_actor.epu_stats[e_actor.epu_stats["date"] < tail_ts][
                    ["date", "epu_weighted"]
                ].rename(columns={"epu_weighted": col})
                cache_df = cache_df.drop(columns=[col], errors="ignore")
                cache_df = cache_df.merge(actor_pre, on="date", how="left")
            print(f"  params.json updated with {len(missing_actors)} actors")

        # Write params and cache once after both backfill blocks
        if missing_topics or missing_actors:
            params_path.parent.mkdir(parents=True, exist_ok=True)
            with open(params_path, "w", encoding="utf-8") as f:
                json.dump(params, f, indent=2, default=json_default)
            cache_df.to_csv(cache_path, index=False, encoding="utf-8")

    if use_cache:
        print(f"  [incremental] updating {daily_tail_start} onwards from cache...")
        # Use in-memory params (already up to date after backfill).
        # Re-read cache from disk since backfill may have updated it.
        cache = pd.read_csv(cache_path, encoding="utf-8", low_memory=False)
        cache["date"] = pd.to_datetime(cache["date"])
        e_base, topic_epus, actor_epus, ug_counts_all = run_incremental_epu(
            news_dirs,
            cutoff,
            subset_condition,
            daily_tail_start,
            all_topics,
            all_actors,
            params,
            cache,
            source_languages=source_languages,
        )

        if missing_topic_epus_full:
            topic_epus.update(missing_topic_epus_full)
        if missing_actor_epus_full:
            actor_epus.update(missing_actor_epus_full)
    else:
        print(
            f"  [full] running full EPU computation over {total_articles} articles — "
            "this may take a few minutes..."
        )
        e_base, topic_epus, actor_epus, ug_counts_all = run_full_epu(
            news_dirs,
            cutoff,
            subset_condition,
            daily_tail_start,
            all_topics,
            all_actors,
            source_languages=source_languages,
        )

    calc_topics_idx, calc_actors_idx = build_outputs(
        e_base,
        topic_epus,
        actor_epus,
        ug_counts_all,
        cutoff,
        daily_tail_start,
        country_name,
        full_write=not use_cache,
        output_dir=output_dir,
    )

    # ── Write params.json + cache (full mode only) ───────────────────
    if not use_cache:
        all_news_dfs = [
            pd.read_csv(fp, encoding="utf-8", usecols=["date"], low_memory=False)
            for fp in news_dirs
            if fp.exists()
        ]
        for df in all_news_dfs:
            df["date"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")

        params = collect_params(
            country_name=country_name,
            cutoff=cutoff,
            e_base=e_base,
            topic_epus=topic_epus,
            actor_epus=actor_epus,
            calc_topics=calc_topics_idx,
            calc_actors=calc_actors_idx,
            all_news_dfs=all_news_dfs,
        )
        params_path.parent.mkdir(parents=True, exist_ok=True)
        with open(params_path, "w", encoding="utf-8") as f:
            json.dump(params, f, indent=2, default=json_default)
        print(f"  params.json written to {params_path}")

        tail_ts = pd.Timestamp(daily_tail_start)
        cache_df = e_base.epu_stats[e_base.epu_stats["date"] < tail_ts].copy()

        for topic_key, e_topic in topic_epus.items():
            col = f"EPU_{topic_key}_index"
            topic_pre = e_topic.epu_stats[e_topic.epu_stats["date"] < tail_ts][
                ["date", "epu_weighted"]
            ].rename(columns={"epu_weighted": col})
            cache_df = cache_df.drop(columns=[col], errors="ignore")
            cache_df = cache_df.merge(topic_pre, on="date", how="left")

        for actor_key, e_actor in actor_epus.items():
            col = f"EPU_{actor_key}_index"
            actor_pre = e_actor.epu_stats[e_actor.epu_stats["date"] < tail_ts][
                ["date", "epu_weighted"]
            ].rename(columns={"epu_weighted": col})
            cache_df = cache_df.drop(columns=[col], errors="ignore")
            cache_df = cache_df.merge(actor_pre, on="date", how="left")

        for source_file in ("topics", "actors"):
            ug_raw = ug_counts_all[source_file]
            if "date" not in ug_raw.columns:
                ug_raw = ug_raw.copy()
                ug_raw["date"] = pd.to_datetime(ug_raw["ym"], format="mixed")
            ug_pre = ug_raw[ug_raw["date"] < tail_ts].copy()
            ug_count_cols = [
                c for c in ug_pre.columns if "_UG_" in c and c.endswith("_count")
            ]
            if ug_count_cols:
                cache_df = pd.merge(
                    cache_df,
                    ug_pre[["date"] + ug_count_cols],
                    on="date",
                    how="left",
                )

        cache_df.to_csv(cache_path, index=False, encoding="utf-8")
        print(f"  epu_stats_cache.csv written ({len(cache_df)} rows)")


# ── CLI entry point ──────────────────────────────────────────────────


def run_analysis(
    region: str | None = None,
    subregion: str | None = None,
    countries: list[str] | None = None,
    cutoff: str | None = None,
    subset_condition: str | None = None,
    recalculate_params: bool = False,
    redo_topics: set[str] | None = None,
    redo_actors: set[str] | None = None,
    exclude_countries: set[str] | None = None,
    yes: bool = False,
):
    """Run EPU analysis for matching units (countries + aggregates).

    Parameters
    ----------
    region : filter to a single WB region slug (e.g. "eap").
    subregion : filter to a single subregion slug (e.g. "pacific_islands").
    countries : list of country slugs. If None, all countries.
    cutoff : date string for EPU standardization (default "2020-12-31").
    subset_condition : pandas query filter.
    recalculate_params : force recalculation of params.json.
    redo_topics : set of topic keys to recompute full-history.
    redo_actors : set of actor keys to recompute full-history.
    exclude_countries : set of country names to exclude.
    yes : auto-confirm interactive prompts.
    """
    if cutoff is None:
        cutoff = "2020-12-31"
    if subset_condition is None:
        today = pd.Timestamp.today().strftime("%Y-%m-%d")
        subset_condition = f"date >= '2015-01-01' and date <= '{today}'"

    country_dirs = _get_country_dirs(exclude_countries)
    if region:
        country_dirs = [d for d in country_dirs if d.parent.parent.name == region]
    if subregion:
        country_dirs = [d for d in country_dirs if d.parent.name == subregion]
    if countries:
        requested = {c.lower() for c in countries}
        country_dirs = [d for d in country_dirs if d.name.lower() in requested]

    if not country_dirs:
        print("No matching country directories found.")
        available = _get_country_dirs()
        if available:
            print(f"Available: {', '.join(d.name for d in available)}")
        return

    include_aggregates = not countries
    units = _discover_units(country_dirs, include_aggregates=include_aggregates)

    if not units:
        print("No units with news data found.")
        return

    print("\nChecking keyword translations...")
    asyncio.run(translate_keywords())

    total = len(units)
    start_time = time.time()
    mode_str = "rebuild" if recalculate_params else "auto"

    country_units = [u for u in units if u["level"] == "country"]
    agg_units = [u for u in units if u["level"] != "country"]

    print(f"\n{'=' * 60}")
    print(f"EPU Analysis — {total} unit(s) ({mode_str})")
    print(f"  Countries: {', '.join(u['name'] for u in country_units)}")
    if agg_units:
        print(f"  Aggregates: {', '.join(u['name'] for u in agg_units)}")
    print(f"  Cutoff: {cutoff}")
    print(f"{'=' * 60}")

    for i, unit in enumerate(units):
        unit_start = time.time()
        elapsed = time.time() - start_time
        if i > 0:
            avg = elapsed / i
            remaining = (total - i) * avg
            eta_str = f"ETA: {int(remaining // 60)}m {int(remaining % 60)}s"
        else:
            eta_str = ""

        eta_suffix = f" — {eta_str}" if eta_str else ""
        print(f"\n[{i + 1}/{total}] {unit['name']}{eta_suffix}")
        try:
            process_unit(
                name=unit["name"],
                news_dirs=unit["news_dirs"],
                output_dir=unit["output_dir"],
                cache_dir=unit["cache_dir"],
                cutoff=cutoff,
                subset_condition=subset_condition,
                recalculate_params=recalculate_params,
                redo_topics=redo_topics,
                redo_actors=redo_actors,
                yes=yes,
                source_languages=unit.get("source_languages"),
            )
            elapsed_unit = time.time() - unit_start
            print(f"  done ({elapsed_unit:.1f}s)")
        except Exception as e:
            print(f"  FAILED: {e}")
            print(f"    Skipping {unit['name']} due to error")
            continue


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EPU Analysis")
    parser.add_argument(
        "--country",
        type=str,
        default=None,
        help="Process a single country (e.g. thailand). Default: all countries.",
    )
    parser.add_argument(
        "--recalculate-params",
        action="store_true",
        default=False,
        help="Force recalculation of params.json even if it already exists.",
    )
    parser.add_argument(
        "--exclude-countries",
        type=str,
        default="",
        help="Comma-separated list of country names to exclude from processing.",
    )
    parser.add_argument(
        "--redo-topic",
        nargs="+",
        default=None,
        metavar="TOPIC",
        help="Recompute full-history params and outputs for specific topic(s). "
        "Requires an existing cache (run without --redo-* first).",
    )
    parser.add_argument(
        "--redo-actor",
        nargs="+",
        default=None,
        metavar="ACTOR",
        help="Recompute full-history params and outputs for specific actor(s). "
        "Requires an existing cache (run without --redo-* first).",
    )
    args = parser.parse_args()

    # Validate --redo-topic / --redo-actor keys early
    _valid_topics = set(load_all_groups("topics").keys())
    _valid_actors = set(load_all_groups("actors").keys())

    if args.redo_topic:
        _unknown = set(args.redo_topic) - _valid_topics
        if _unknown:
            print(f"Error: unknown topic(s): {', '.join(sorted(_unknown))}")
            print(f"Valid topics: {', '.join(sorted(_valid_topics))}")
            sys.exit(1)

    if args.redo_actor:
        _unknown = set(args.redo_actor) - _valid_actors
        if _unknown:
            print(f"Error: unknown actor(s): {', '.join(sorted(_unknown))}")
            print(f"Valid actors: {', '.join(sorted(_valid_actors))}")
            sys.exit(1)

    redo_topics = None
    redo_actors = None
    if not args.recalculate_params:
        redo_topics = set(args.redo_topic) if args.redo_topic else None
        redo_actors = set(args.redo_actor) if args.redo_actor else None

    exclude_countries = None
    if args.exclude_countries:
        exclude_countries = {
            name.strip().lower()
            for name in args.exclude_countries.split(",")
            if name.strip()
        }

    run_analysis(
        countries=[args.country] if args.country else None,
        recalculate_params=args.recalculate_params,
        redo_topics=redo_topics,
        redo_actors=redo_actors,
        exclude_countries=exclude_countries,
        yes=False,
    )
