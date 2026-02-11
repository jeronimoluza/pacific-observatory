import argparse
import asyncio
import sys
import time
from pathlib import Path

import pandas as pd

# Setup path before imports
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.text.analysis.epu import EPU  # noqa: E402
from src.text.analysis.indices import IndexCalculator  # noqa: E402
from src.text.analysis.translate_keywords import translate_keywords  # noqa: E402
from src.text.analysis.utils import (  # noqa: E402
    load_all_groups,
    generate_continous_df,
)

PROJECT_ROOT = _PROJECT_ROOT

DATA_ROOT = PROJECT_ROOT / "data" / "text"
EXCLUDED_COUNTRIES = {}

country_dirs = sorted(
    [
        entry
        for entry in DATA_ROOT.iterdir()
        if entry.is_dir() and entry.name not in EXCLUDED_COUNTRIES
    ]
)

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "text"


def process_country(country, cutoff, subset_condition):
    """
    Process all EPU and uncertainty attribution indices for a single country.

    Outputs:
    - epu/epu.csv: base EPU + breadth/intensity/pairwise
    - epu/topics_epu.csv: EPU index per topic (all from topics.json)
    - uncertainty_attribution/topics.csv: absolute + framing per topic
    - uncertainty_attribution/actors.csv: absolute + framing per actor
    """
    country_name = country.name
    news_dirs = list(country.glob("*/news.csv"))

    # ── Stage 1: Base EPU ──────────────────────────────────────────────
    e_base = EPU(news_dirs, cutoff=cutoff)
    e_base.get_epu_category(subset_condition=subset_condition)
    e_base.get_count_stats(calculate_extended=True)
    e_base.calculate_epu_score()
    e_base.calculate_all_indices()

    result = e_base.epu_stats[["date", "ym", "news_total"]].copy()
    result["EPU_index"] = e_base.epu_stats["epu_weighted"]

    for cat in ["E", "P", "U"]:
        result[f"{cat}_breadth"] = e_base.epu_stats[f"{cat}_breadth_weighted"]
        result[f"{cat}_intensity"] = e_base.epu_stats[f"{cat}_intensity_weighted"]

    for pair in ["EU", "PU", "EP"]:
        result[f"{pair}_index"] = e_base.epu_stats[f"{pair}_share_weighted"]

    epu_folder = OUTPUT_DIR / country_name / "epu"
    epu_folder.mkdir(parents=True, exist_ok=True)
    result.to_csv(epu_folder / "epu.csv", encoding="utf-8", index=False)

    # ── Stage 2: Topic EPU (all topics from topics.json) ───────────────
    all_topics = load_all_groups("topics")
    topic_epu = e_base.epu_stats[["date", "ym"]].copy()

    for topic_key in all_topics:
        additional_terms = all_topics[topic_key]
        e_topic = EPU(
            news_dirs,
            cutoff=cutoff,
            additional_terms=additional_terms,
            additional_name=topic_key,
        )
        e_topic.get_epu_category(subset_condition=subset_condition)
        e_topic.get_count_stats(calculate_extended=False)
        e_topic.calculate_epu_score()
        topic_epu[f"EPU_{topic_key}_index"] = e_topic.epu_stats["epu_weighted"]

    topic_epu.to_csv(epu_folder / "topics_epu.csv", encoding="utf-8", index=False)

    # ── Stage 3: Uncertainty Attribution ───────────────────────────────
    sources = [col.replace("_body_count", "") for col in e_base.news_cols]
    calc = IndexCalculator(cutoff)

    for source_file, output_name in [("topics", "topics"), ("actors", "actors")]:
        groups = load_all_groups(source_file)
        group_names = list(groups.keys())

        # Get UG counts from raw article data
        ug_counts = e_base.calculate_group_uncertainty_counts(groups)

        # Build attribution DataFrame: merge UG counts with date/weights
        attr_df = e_base.epu_stats[["date", "ym"]].copy()
        # Carry over weight columns
        weight_cols = [c for c in e_base.epu_stats.columns if c.endswith("_weights")]
        for wc in weight_cols:
            attr_df[wc] = e_base.epu_stats[wc]

        # Merge UG counts on ym
        ug_counts["date"] = pd.to_datetime(ug_counts["ym"], format="mixed")
        ug_counts = generate_continous_df(ug_counts, e_base.min_date, e_base.max_date)
        attr_df = pd.merge(
            attr_df, ug_counts.drop(columns=["ym"]), on="date", how="left"
        )

        # Calculate both attribution types
        attr_df = calc.calculate_absolute_uncertainty_attribution(
            attr_df, sources, group_names
        )
        attr_df = calc.calculate_framing_uncertainty_attribution(
            attr_df, sources, group_names
        )

        # Extract final columns: date, ym, {group}_absolute, {group}_framing
        out_cols = ["date", "ym"]
        for g in group_names:
            abs_col = f"UG_{g}_abs_weighted"
            frm_col = f"UG_{g}_frm_weighted"
            if abs_col in attr_df.columns:
                attr_df = attr_df.rename(columns={abs_col: f"{g}_absolute"})
                out_cols.append(f"{g}_absolute")
            if frm_col in attr_df.columns:
                attr_df = attr_df.rename(columns={frm_col: f"{g}_framing"})
                out_cols.append(f"{g}_framing")

        attr_out = attr_df[[c for c in out_cols if c in attr_df.columns]]
        attr_folder = OUTPUT_DIR / country_name / "uncertainty_attribution"
        attr_folder.mkdir(parents=True, exist_ok=True)
        attr_out.to_csv(
            attr_folder / f"{output_name}.csv", encoding="utf-8", index=False
        )


if __name__ == "__main__":
    cutoff = "2020-12-31"
    subset_condition = "date >= '2015-01-01' and date <= '2026-01-31'"

    parser = argparse.ArgumentParser(description="EPU Analysis")
    parser.add_argument(
        "--country",
        type=str,
        default=None,
        help="Process a single country (e.g. thailand). Default: all countries.",
    )
    args = parser.parse_args()

    if args.country:
        matched = [d for d in country_dirs if d.name == args.country]
        if not matched:
            available = [d.name for d in country_dirs]
            print(f"Error: country '{args.country}' not found.")
            print(f"Available countries: {', '.join(available)}")
            sys.exit(1)
        country_dirs = matched

    # Ensure all keyword translations are up to date before analysis
    print("\nChecking keyword translations...")
    asyncio.run(translate_keywords())

    total_countries = len(country_dirs)
    start_time = time.time()

    print(f"\n{'='*60}")
    print(f"EPU Analysis - Processing {total_countries} countries")
    print(f"{'='*60}\n")

    for i, country in enumerate(country_dirs):
        country_start = time.time()

        # Calculate ETA
        elapsed = time.time() - start_time
        if i > 0:
            avg_per_country = elapsed / i
            remaining = (total_countries - i) * avg_per_country
            eta_min = int(remaining // 60)
            eta_sec = int(remaining % 60)
            eta_str = f"ETA: {eta_min}m {eta_sec}s"
        else:
            eta_str = "ETA: calculating..."

        print(f"\n[{i+1}/{total_countries}] {country.name} - {eta_str}")
        try:
            process_country(
                country,
                cutoff,
                subset_condition,
            )
            print("  ✓ EPU processing completed")
        except Exception as e:
            print(f"  ✗ EPU processing FAILED: {e}")
            print(f"    Skipping {country.name} due to error")
            continue

        country_elapsed = time.time() - country_start
        print(f"  Done in {country_elapsed:.1f}s")

    total_elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"Completed in {total_elapsed/60:.1f} minutes")
    print(f"{'='*60}")
