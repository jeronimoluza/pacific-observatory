"""Nightly tier-c quorum spot check.

Samples 1% of yesterday's `tier_c_llm*` cache rows, re-runs each as a 3-way
quorum through the tier-c LLM, and reports per-field disagreement rate.
Cron-callable. Writes telemetry to
`data/prices/_enrich/_tier_c_quorum_telemetry.parquet`.

If per-field disagreement > 10% over a week, manual escalation is the
expected response — this script does not auto-escalate.

Usage:
    python scripts/nightly_quorum_spot_check.py
    python scripts/nightly_quorum_spot_check.py --sample-frac 0.02 --days 1
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prices.enrich import config  # noqa: E402
from prices.enrich.tier_b import cache  # noqa: E402

TELEMETRY_PATH = config.ENRICH_DIR / "_tier_c_quorum_telemetry.parquet"
FIELDS = (
    "pricing_basis",
    "standard_unit",
    "coicop_code",
    "sub_label_id",
    "is_promotion",
    "is_bundle",
    "is_multipack",
)


def _select_rows(days: int, sample_frac: float, seed: int) -> pd.DataFrame:
    df = cache.read_cache()
    if df.empty or "match_method" not in df.columns:
        return df.iloc[0:0]
    df = df[df["match_method"].astype(str).str.startswith("tier_c_llm")]
    if df.empty or "created_at" not in df.columns:
        return df
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=days)).isoformat()
    df = df[df["created_at"].astype(str) >= cutoff]
    if df.empty:
        return df
    return df.sample(frac=sample_frac, random_state=seed)


def _run_quorum(rows: pd.DataFrame, n: int) -> list[dict]:
    """Re-run each row N times through tier-c and collect per-field counts."""
    from prices.enrich.stages import tier_c

    out: list[dict] = []
    for _, row in rows.iterrows():
        product = pd.Series(
            {
                "first_name": row.get("product_name_original")
                or row.get("first_name")
                or "",
                "category": row.get("category") or "",
                "country": row.get("country") or "",
                "currency": row.get("currency") or "",
                "product_identity_key": row.get("product_identity_key") or "",
                "canonical_loose": row.get("canonical_loose") or "",
                "input_hashes": [row.get("input_hash")],
            }
        )
        votes: dict[str, list] = {f: [] for f in FIELDS}
        for _ in range(n):
            tier_c.L1_CACHE.clear()
            df_one = pd.DataFrame([product.to_dict()])
            captured: list[dict] = []
            orig = cache.append_enrichments
            cache.append_enrichments = lambda r: captured.extend(r)
            try:
                asyncio.run(tier_c.run_residual(df_one))
            finally:
                cache.append_enrichments = orig
            if not captured:
                continue
            ans = captured[0]
            for f in FIELDS:
                votes[f].append(ans.get(f))

        rec = {
            "input_hash": row.get("input_hash"),
            "country": row.get("country"),
            "n_quorum": n,
            "baseline_match_method": row.get("match_method"),
        }
        for f in FIELDS:
            vs = votes[f]
            if not vs:
                rec[f"{f}_disagree"] = None
                continue
            top, top_n = Counter(vs).most_common(1)[0]
            rec[f"{f}_top"] = top
            rec[f"{f}_disagree"] = (len(vs) - top_n) / len(vs)
        out.append(rec)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-frac", type=float, default=0.01)
    parser.add_argument("--days", type=int, default=1, help="Look back N days")
    parser.add_argument("--quorum", type=int, default=3, help="N parallel runs")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rows = _select_rows(args.days, args.sample_frac, args.seed)
    if rows.empty:
        print("No tier_c_llm rows found in the lookback window.")
        return 0
    print(f"Spot-checking {len(rows)} rows × {args.quorum} runs ...")
    telemetry = _run_quorum(rows, args.quorum)
    if not telemetry:
        print("Quorum produced no results.")
        return 0
    df = pd.DataFrame(telemetry)
    df["logged_at"] = datetime.now(timezone.utc).isoformat()

    TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if TELEMETRY_PATH.exists():
        existing = pd.read_parquet(TELEMETRY_PATH)
        out = pd.concat([existing, df], ignore_index=True)
    else:
        out = df
    out.to_parquet(TELEMETRY_PATH, index=False)

    print(f"Wrote {len(df)} new rows to {TELEMETRY_PATH}")
    print("\nPer-field disagreement rate (this run):")
    for f in FIELDS:
        col = f"{f}_disagree"
        if col not in df.columns:
            continue
        vals = [v for v in df[col].tolist() if v is not None]
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        flag = " ⚠" if avg > 0.10 else ""
        print(f"  {f}: {avg:.1%}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
