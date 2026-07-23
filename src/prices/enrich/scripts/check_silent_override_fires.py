"""One-off check: did SILENT_OVERRIDE ever fire historically on div-01?

Reads the persisted cross_check side-log (`config.ENRICH_DIR /
"cross_check.parquet"`, written by `cross_check.append`) and counts rows
where `consolidation_bucket == "SILENT_OVERRIDE"`. Required before retiring
the SILENT_OVERRIDE basis-mutation branch (AUDIT_LAYER_SPEC_v2.md §4 step 1).

If the side-log doesn't exist, that is reported explicitly -- it is NOT
treated as a count of 0 fires by assumption.
"""

from __future__ import annotations

import pandas as pd

from prices.enrich import config


def main() -> None:
    path = config.ENRICH_DIR / "cross_check.parquet"
    if not path.exists():
        print(f"NO SIDE-LOG FOUND at {path} -- cannot count historical fires from it.")
        return
    df = pd.read_parquet(path)
    if "consolidation_bucket" not in df.columns:
        print(
            f"Side-log at {path} has no 'consolidation_bucket' column -- cannot check."
        )
        return
    n = int((df["consolidation_bucket"] == "SILENT_OVERRIDE").sum())
    print(f"SILENT_OVERRIDE fires in {path}: {n} / {len(df)} rows")


if __name__ == "__main__":
    main()
