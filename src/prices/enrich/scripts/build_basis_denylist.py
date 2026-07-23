"""Build `data/prices/enrich/gold/basis_denylist.parquet` from the curated
source review JSON. Cold-start: every row is authored with `evidence_state
= "UNOBSERVED"` (the monitor job computes real evidence later from the
corpus -- this script does not touch the corpus), so every derived `action`
is "flag" per the §2 authoring invariant:
    action = "reject" iff semantic == "HIGH" AND evidence_state == "CONFIRMED"

Run: PYTHONPATH=src <venv>/bin/python src/prices/enrich/scripts/build_basis_denylist.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from prices.enrich import config

SOURCE_JSON = Path(
    "/Users/jeronimoluza/.claude/jobs/e5ad10b3/tmp/allowed_bases_review_v2.json"
)

CONFIDENCE_TO_SEMANTIC = {"HIGH": "HIGH", "MED": "MED", "n/a": "MED"}


def build() -> pd.DataFrame:
    rows = json.loads(SOURCE_JSON.read_text())
    out = []
    for r in rows:
        semantic = CONFIDENCE_TO_SEMANTIC.get(r.get("confidence", "MED"), "MED")
        evidence_state = "UNOBSERVED"
        action = (
            "reject"
            if (semantic == "HIGH" and evidence_state == "CONFIRMED")
            else "flag"
        )
        out.append(
            {
                "code": r["code"],
                "label": r.get("label", ""),
                "division": "01",
                "profile": r.get("profile", ""),
                "excluded": r.get("excluded") or "",
                "action": action,
                "semantic": semantic,
                "evidence_state": evidence_state,
                "rationale": r.get("rationale", ""),
            }
        )
    return pd.DataFrame(out)


def main() -> None:
    df = build()
    out_path = config.BASIS_DENYLIST_PARQUET
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    print("wrote", out_path)
    print("rows:", len(df))
    print("distinct leaves:", df["code"].nunique())
    print("action value counts:")
    print(df["action"].value_counts())


if __name__ == "__main__":
    main()
