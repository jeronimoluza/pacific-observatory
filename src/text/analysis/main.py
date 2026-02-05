import argparse
import sys
import time
from pathlib import Path

# Setup path before imports
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.text.analysis.epu import EPU  # noqa: E402
from src.text.analysis.utils import load_topics_words  # noqa: E402

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


def process_country(country, cutoff, subset_condition, additional_terms_keys):
    """
    Process all EPU indices for a single country and output one CSV.

    Returns DataFrame with columns:
    - date, ym, news_total
    - EPU_index (base)
    - EPU_{topic}_index for each topic
    - E/P/U_breadth, E/P/U_intensity, EU/PU/EP_index
    """
    country_name = country.name
    news_dirs = list(country.glob("*/news.csv"))

    # 1. Calculate base EPU with extended indices
    e_base = EPU(news_dirs, cutoff=cutoff)
    e_base.get_epu_category(subset_condition=subset_condition)
    e_base.get_count_stats(calculate_extended=True)
    e_base.calculate_epu_score()
    e_base.calculate_all_indices()

    # Extract base EPU and extended indices
    result = e_base.epu_stats[["date", "ym", "news_total"]].copy()
    result["EPU_index"] = e_base.epu_stats["epu_weighted"]

    # Add breadth indices (weighted only)
    for cat in ["E", "P", "U"]:
        result[f"{cat}_breadth"] = e_base.epu_stats[f"{cat}_breadth_weighted"]
        result[f"{cat}_intensity"] = e_base.epu_stats[f"{cat}_intensity_weighted"]

    # Add pairwise indices (rename _share to _index)
    for pair in ["EU", "PU", "EP"]:
        result[f"{pair}_index"] = e_base.epu_stats[f"{pair}_share_weighted"]

    # 2. Calculate topic-specific EPU indices (inflation, job)
    for topic in additional_terms_keys:
        additional_terms = load_topics_words(additional_name=topic)
        e_topic = EPU(
            news_dirs,
            cutoff=cutoff,
            additional_terms=additional_terms,
            additional_name=topic,
        )
        e_topic.get_epu_category(subset_condition=subset_condition)
        e_topic.get_count_stats(calculate_extended=False)
        e_topic.calculate_epu_score()

        result[f"EPU_{topic}_index"] = e_topic.epu_stats["epu_weighted"]

    # 3. Save single output file
    saved_folder = OUTPUT_DIR / country_name / "epu"
    saved_folder.mkdir(parents=True, exist_ok=True)
    result.to_csv(saved_folder / "epu.csv", encoding="utf-8", index=False)

    return result


if __name__ == "__main__":
    cutoff = "2020-12-31"
    subset_condition = "date >= '2015-01-01' and date <= '2026-01-31'"

    additional_terms_keys = ["inflation", "job"]

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
                additional_terms_keys,
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
