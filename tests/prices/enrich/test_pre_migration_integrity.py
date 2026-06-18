"""Pre-migration integrity check.

Loads the real legacy enrichments.parquet, samples 1000 rows, recomputes
input_hash from the row's structured input using the current formula, and
asserts the value matches what the migration script would write. If this
fails the migration is unsafe — block it.

Marked `slow`; skipped when the real cache file is not present (CI without
data, fresh checkouts).
"""

import hashlib
import json

import pandas as pd
import pytest

from prices.enrich.tier_b import cache as enrich_cache
from prices.enrich import config
from prices.enrich.versioning import canonical_json, input_hash

SAMPLE_SIZE = 1000
SAMPLE_SEED = 20260610


def _structured_input(row: pd.Series) -> dict:
    return {
        "product_name_original": str(row["product_name_original"]),
        "category": "" if pd.isna(row.get("category")) else str(row["category"]),
        "country": str(row["country"]),
        "currency": str(row["currency"]),
    }


@pytest.fixture(scope="module")
def legacy_cache():
    """Union of all schema-version partitions plus the unpartitioned legacy
    file (whichever exist). Post-migration this includes the rows with the
    stored input_hash that the byte-exact check actually exercises."""
    df = enrich_cache.read_cache()
    if df.empty:
        pytest.skip(f"no cache rows found under {config.CACHE_DIR}")
    return df


@pytest.mark.slow
def test_input_hash_recompute_byte_exact(legacy_cache):
    n = min(SAMPLE_SIZE, len(legacy_cache))
    sample = legacy_cache.sample(n=n, random_state=SAMPLE_SEED)

    mismatches: list[dict] = []
    for _, row in sample.iterrows():
        inp = _structured_input(row)
        computed = input_hash(inp)

        # Sanity: canonical_json is deterministic and stable across runs.
        assert hashlib.sha256(canonical_json(inp).encode()).hexdigest() == computed

        if "input_hash" in legacy_cache.columns and pd.notna(row.get("input_hash")):
            stored = str(row["input_hash"])
            if stored != computed:
                mismatches.append(
                    {"stored": stored, "computed": computed, "input": inp}
                )

    if mismatches:
        sample_msg = json.dumps(mismatches[:3], indent=2, ensure_ascii=False)
        pytest.fail(
            f"{len(mismatches)}/{n} rows have stored input_hash != recomputed. "
            f"Migration is unsafe. First 3:\n{sample_msg}"
        )


@pytest.mark.slow
def test_required_input_columns_present(legacy_cache):
    required = {"product_name_original", "country", "currency"}
    missing = required - set(legacy_cache.columns)
    assert not missing, f"cache missing input columns: {missing}"


@pytest.mark.slow
def test_no_null_in_join_columns(legacy_cache):
    n = len(legacy_cache)
    for col in ("product_name_original", "country", "currency"):
        nulls = int(legacy_cache[col].isna().sum())
        assert (
            nulls == 0
        ), f"{nulls}/{n} rows have null {col} — would corrupt input_hash"
