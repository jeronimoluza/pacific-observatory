"""Gate-1 adjudication input builder.

Splits the 708-row disagreement worklist into blinded batches for a 3rd-family
adjudicator (Claude). Each row's two candidate labels (Pass A / Pass B) are
position-shuffled deterministically (md5 of gold_row_id) into candidate_1 /
candidate_2 so the adjudicator cannot infer which model produced which, and is
told at least one may be wrong (it may pick neither). A decode map records the
candidate_N -> pass mapping for scoring after adjudication.

Outputs under data/prices/enrich/gold/gate1/:
  adjud_batches/adjud_batch_NNN.json  -- blinded rows to adjudicate
  adjud_decode.json                   -- {gold_row_id: {candidate_1: A|B, ...}}
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prices.enrich import config  # noqa: E402

GATE_DIR = config.REPO_ROOT / "data" / "prices" / "enrich" / "gold" / "gate1"
DIS_CSV = GATE_DIR / "gold_v5_gate1_disagreements.csv"
BATCH_DIR = GATE_DIR / "adjud_batches"


def _only_new(df, first_new=3000):
    idnum = df["gold_row_id"].str.replace("gv5-", "").astype(int)
    return df[idnum >= first_new].reset_index(drop=True)


def _swap(rid: str) -> bool:
    return int(hashlib.md5(rid.encode()).hexdigest(), 16) % 2 == 1


def _cand(row, side: str) -> dict:
    return {
        "verdict": str(row[f"{side}_verdict"]),
        "code": "" if pd.isna(row[f"{side}_code"]) else str(row[f"{side}_code"]),
        "division": ""
        if pd.isna(row[f"{side}_division"])
        else str(row[f"{side}_division"]),
        "rationale": ""
        if pd.isna(row[f"{side}_rationale"])
        else str(row[f"{side}_rationale"]),
    }


def build(
    batch_size: int, dis_csv=DIS_CSV, tag="", only_new=False, first_new=3000
) -> dict:
    sfx = f"_{tag}" if tag else ""
    batch_dir = GATE_DIR / f"adjud_batches{sfx}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(dis_csv)
    if only_new:
        df = _only_new(df, first_new)
    rows, decode = [], {}
    for _, r in df.iterrows():
        rid = str(r["gold_row_id"])
        a, b = _cand(r, "a"), _cand(r, "b")
        if _swap(rid):
            c1, c2, m1, m2 = b, a, "B", "A"
        else:
            c1, c2, m1, m2 = a, b, "A", "B"
        decode[rid] = {"candidate_1": m1, "candidate_2": m2}
        rows.append(
            {
                "gold_row_id": rid,
                "product_name": str(r["product_name"]),
                "country": str(r["country"]),
                "source": str(r["source"]),
                "channel": "" if pd.isna(r["channel"]) else str(r["channel"]),
                "retailer_category": ""
                if pd.isna(r["category"])
                else str(r["category"]),
                "declared_coicop_codes": ""
                if pd.isna(r["declared_coicop_codes"])
                else str(r["declared_coicop_codes"]),
                "price": None if pd.isna(r["price"]) else float(r["price"]),
                "candidate_1": c1,
                "candidate_2": c2,
            }
        )

    n_batches = 0
    for i in range(0, len(rows), batch_size):
        chunk = rows[i : i + batch_size]
        (batch_dir / f"adjud_batch_{n_batches:03d}.json").write_text(
            json.dumps(chunk, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        n_batches += 1

    (GATE_DIR / f"adjud_decode{sfx}.json").write_text(
        json.dumps(decode, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    summary = {"n_rows": len(rows), "n_batches": n_batches, "batch_size": batch_size}
    print(json.dumps(summary, indent=2))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=59)
    ap.add_argument("--dis-csv", default=str(DIS_CSV))
    ap.add_argument("--tag", default="")
    ap.add_argument("--only-new", action="store_true")
    ap.add_argument("--first-new", type=int, default=3000)
    args = ap.parse_args()
    build(args.batch_size, Path(args.dis_csv), args.tag, args.only_new, args.first_new)


if __name__ == "__main__":
    main()
