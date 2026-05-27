"""Run the enrich pipeline against eval_set.csv and append per-field scores to eval_history.csv."""

import asyncio
from datetime import datetime, timezone

import pandas as pd

from prices.enrich import cache, config
from prices.enrich.stages.enrich import _enrich_async, _structured_input
from prices.enrich.versioning import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    TAXONOMY_VERSION,
    cache_key,
)

FIELDS = [
    "pricing_basis",
    "amount_value",
    "standard_unit",
    "count",
    "multiplier",
    "coicop_code",
    "sub_label_id",
    "is_promotion",
    "is_bundle",
    "is_multipack",
    "state",
]


def main() -> None:
    eval_df = pd.read_csv(config.EVAL_SET_CSV)
    eval_df = eval_df.rename(columns={"product_name": "product_name_original"})

    asyncio.run(_enrich_async(eval_df))

    cached = cache.read_cache()
    eval_df["cache_key"] = eval_df.apply(
        lambda r: cache_key(_structured_input(r)), axis=1
    )
    joined = eval_df.merge(cached, on="cache_key", how="left", suffixes=("_exp", ""))

    scores: dict[str, str] = {}
    for f in FIELDS:
        exp = f"expected_{f}"
        if exp not in joined.columns:
            continue
        ok = (joined[exp].astype(str) == joined[f].astype(str)).sum()
        scores[f] = f"{ok}/{len(joined)}"

    row = {
        "date": datetime.now(timezone.utc).isoformat(),
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "taxonomy_version": TAXONOMY_VERSION,
        "model": config.MODEL_NAME,
        **scores,
    }
    hist_df = pd.DataFrame([row])
    hist_path = config.EVAL_HISTORY_CSV
    if hist_path.exists():
        prev = pd.read_csv(hist_path)
        hist_df = pd.concat([prev, hist_df], ignore_index=True)
    hist_df.to_csv(hist_path, index=False)
    print(hist_df.tail(2).to_string())


if __name__ == "__main__":
    main()
