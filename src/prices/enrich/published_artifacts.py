"""Helpers for writing published CPI shadow artifacts and sidecars."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ARTIFACT_NAME = "all_countries_supermarket_prices"
SCHEMA_VERSION = "1.0.0-draft"
PRIMARY_KEY = ["url_hash", "date"]
REQUIRED_COLUMNS = [
    "url_hash",
    "product_name_original",
    "product_name",
    "product_w_cat",
    "price",
    "currency",
    "unit_value",
    "usability_status",
    "extraction_tier",
    "source",
    "country",
    "date",
    "wayback",
]


def _sum_numeric(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values.fillna(0).sum())


def _date_range(df: pd.DataFrame) -> dict[str, str | None]:
    if "date" not in df.columns or df.empty:
        return {"min": None, "max": None}

    parsed = pd.to_datetime(df["date"], errors="coerce")
    if parsed.isna().all():
        return {"min": None, "max": None}

    return {
        "min": parsed.min().isoformat(),
        "max": parsed.max().isoformat(),
    }


def build_supermarket_price_checks(
    df: pd.DataFrame, legacy_df: pd.DataFrame | None = None
) -> dict:
    """Build validation and parity checks for the published supermarket artifact."""
    missing_required_columns = [
        col for col in REQUIRED_COLUMNS if col not in df.columns
    ]
    present_primary_key = [col for col in PRIMARY_KEY if col in df.columns]
    primary_key_unique = (
        bool(present_primary_key)
        and not df.duplicated(subset=present_primary_key).any()
    )

    required_null_counts = {
        col: int(df[col].isna().sum()) for col in REQUIRED_COLUMNS if col in df.columns
    }

    enum_checks = {
        "wayback_binary": "wayback" in df.columns
        and set(pd.Series(df["wayback"]).dropna().astype(int).unique()).issubset(
            {0, 1}
        ),
        "pending_review_boolean": "pending_review" not in df.columns
        or set(pd.Series(df["pending_review"]).dropna().unique()).issubset(
            {True, False}
        ),
        "has_promotion_boolean": "has_promotion" not in df.columns
        or set(pd.Series(df["has_promotion"]).dropna().unique()).issubset(
            {True, False}
        ),
    }

    numeric_range_checks = {
        "price_non_negative": "price" in df.columns
        and bool((pd.to_numeric(df["price"], errors="coerce").dropna() >= 0).all()),
        "unit_value_non_negative": "unit_value" not in df.columns
        or bool((pd.to_numeric(df["unit_value"], errors="coerce").dropna() >= 0).all()),
        "confidence_between_zero_and_one": "confidence" not in df.columns
        or bool(
            pd.to_numeric(df["confidence"], errors="coerce")
            .dropna()
            .between(0, 1)
            .all()
        ),
    }

    parity_result = None
    if legacy_df is not None:
        parity_result = {
            "columns_match": list(df.columns) == list(legacy_df.columns),
            "row_count_match": len(df) == len(legacy_df),
            "primary_key_match": set(present_primary_key).issubset(legacy_df.columns)
            and set(
                map(tuple, df[present_primary_key].astype(str).to_records(index=False))
            )
            == set(
                map(
                    tuple,
                    legacy_df[present_primary_key].astype(str).to_records(index=False),
                )
            ),
            "required_null_count_match": {
                col: required_null_counts[col] == int(legacy_df[col].isna().sum())
                for col in required_null_counts
                if col in legacy_df.columns
            },
            "date_range_match": _date_range(df) == _date_range(legacy_df),
            "numeric_sum_match": {
                col: round(_sum_numeric(df[col]), 6)
                == round(_sum_numeric(legacy_df[col]), 6)
                for col in ["price", "unit_value", "n_candidates"]
                if col in df.columns and col in legacy_df.columns
            },
        }
        parity_result["passed"] = (
            parity_result["columns_match"]
            and parity_result["row_count_match"]
            and parity_result["primary_key_match"]
            and all(parity_result["required_null_count_match"].values())
            and parity_result["date_range_match"]
            and all(parity_result["numeric_sum_match"].values())
        )

    passed = (
        not missing_required_columns
        and primary_key_unique
        and all(count == 0 for count in required_null_counts.values())
        and all(enum_checks.values())
        and all(numeric_range_checks.values())
        and (parity_result is None or parity_result["passed"])
    )

    return {
        "artifact_name": ARTIFACT_NAME,
        "schema_version": SCHEMA_VERSION,
        "primary_key": PRIMARY_KEY,
        "row_count": len(df),
        "columns": list(df.columns),
        "missing_required_columns": missing_required_columns,
        "primary_key_unique": primary_key_unique,
        "required_null_counts": required_null_counts,
        "enum_checks": enum_checks,
        "numeric_range_checks": numeric_range_checks,
        "date_range": _date_range(df),
        "parity": parity_result,
        "passed": passed,
    }


def build_supermarket_price_manifest(
    df: pd.DataFrame,
    storage_path: Path,
    legacy_output_path: Path,
    producer: str,
) -> dict:
    """Build a manifest for the published supermarket artifact."""
    return {
        "artifact_name": ARTIFACT_NAME,
        "artifact_version": "shadow-v1",
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "producer": producer,
        "inputs": [str(legacy_output_path)],
        "row_count": len(df),
        "primary_key": PRIMARY_KEY,
        "storage_path": str(storage_path),
        "parity_target": str(legacy_output_path),
    }


def write_supermarket_prices_shadow_artifact(
    df: pd.DataFrame,
    project_root: Path,
    legacy_output_path: Path,
    producer: str = "src/prices/enrich/process.py",
) -> dict[str, Path | dict]:
    """Write the shadow published artifact plus manifest and checks sidecars."""
    target_dir = (
        project_root
        / "outputs"
        / "prices"
        / "published"
        / "online_prices"
        / "supermarket_prices"
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = target_dir / f"{ARTIFACT_NAME}.csv"
    manifest_path = target_dir / f"{ARTIFACT_NAME}.manifest.json"
    checks_path = target_dir / f"{ARTIFACT_NAME}.checks.json"
    markdown_path = target_dir / f"{ARTIFACT_NAME}.md"

    df.to_csv(artifact_path, index=False, encoding="utf-8")

    legacy_df = pd.read_csv(legacy_output_path) if legacy_output_path.exists() else None
    checks = build_supermarket_price_checks(df, legacy_df=legacy_df)
    manifest = build_supermarket_price_manifest(
        df,
        storage_path=artifact_path,
        legacy_output_path=legacy_output_path,
        producer=producer,
    )

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    checks_path.write_text(json.dumps(checks, indent=2), encoding="utf-8")

    if not markdown_path.exists():
        markdown_path.write_text(
            "# all_countries_supermarket_prices\n\nGenerated shadow artifact note.\n",
            encoding="utf-8",
        )

    return {
        "artifact_path": artifact_path,
        "manifest_path": manifest_path,
        "checks_path": checks_path,
        "markdown_path": markdown_path,
        "manifest": manifest,
        "checks": checks,
    }
