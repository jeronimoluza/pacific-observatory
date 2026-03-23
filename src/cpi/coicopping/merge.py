"""Merge stage for the COICOP pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from .published_artifacts import write_supermarket_prices_shadow_artifact
from .quantity.extraction import merge_quantities_with_gemini
from .utils import get_project_root


FINAL_COLUMNS = [
    "url_hash",
    "product_name_original",
    "product_name",
    "product_w_cat",
    "price",
    "currency",
    "amount",
    "units",
    "unit_value",
    "usability_status",
    "extraction_tier",
    "standard_unit",
    "n_candidates",
    "has_promotion",
    "rejection_reason",
    "pending_review",
    "coicop_code",
    "coicop_title",
    "confidence",
    "source",
    "country",
    "product_url",
    "date",
    "product_id",
    "wayback",
]


def run_merge(project_root: Path) -> pd.DataFrame:
    data_dir = project_root / "data" / "cpi" / "coicopping"
    output_dir = project_root / "data" / "cpi" / "analysis"

    quantities_path = data_dir / "quantities.csv"
    gemini_path = data_dir / "gemini_classification.csv"
    output_path = output_dir / "all_countries_supermarket_prices.csv"

    if not quantities_path.exists():
        raise FileNotFoundError(
            f"Quantities file not found at {quantities_path}. Run quantities stage first."
        )

    df_quantities = pd.read_csv(quantities_path)
    df_final = merge_quantities_with_gemini(df_quantities, gemini_path)

    available_columns = [col for col in FINAL_COLUMNS if col in df_final.columns]
    df_final = df_final[available_columns]

    output_dir.mkdir(parents=True, exist_ok=True)
    df_final.to_csv(output_path, index=False, encoding="utf-8")

    shadow_result = write_supermarket_prices_shadow_artifact(
        df_final,
        project_root=project_root,
        legacy_output_path=output_path,
        producer="src/cpi/coicopping/merge.py",
    )

    print(f"✓ Saved {len(df_final)} records to {output_path}")
    print(f"✓ Shadow-wrote published artifact to {shadow_result['artifact_path']}")
    print(f"✓ Wrote checks sidecar to {shadow_result['checks_path']}")

    classified = (
        df_final["coicop_code"].notna().sum()
        if "coicop_code" in df_final.columns
        else 0
    )
    unclassified = (
        df_final["coicop_code"].isna().sum() if "coicop_code" in df_final.columns else 0
    )
    print("\nMerge summary:")
    print(f"  - Total records: {len(df_final)}")
    print(f"  - Classified: {classified}")
    print(f"  - Unclassified: {unclassified}")
    return df_final


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge stage for COICOP pipeline")
    parser.parse_args()

    project_root = get_project_root()
    try:
        run_merge(project_root)
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
