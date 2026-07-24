"""Flash-lite reliability probe: run gemini-3.1-flash-lite N times on a fixed
sample and measure self-consistency + agreement vs the gpt-5 Pass A labels.

Answers "how bad is flash-lite as a gold labeler?" by its own noise floor at
temperature 0. Writes labels/selfconsistency_flashlite.json; prints a report.
"""

import argparse
import asyncio
import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prices.enrich import config  # noqa: E402
from prices.enrich.tier_b.taxonomy_index import load_taxonomy_index  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "passb", ROOT / "scripts" / "gold_v5_label_pass_b.py"
)
passb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(passb)

GOLD_DIR = config.REPO_ROOT / "data" / "prices" / "enrich" / "gold"
OUT_PATH = GOLD_DIR / "labels" / "selfconsistency_flashlite.json"


def _sample(n_batch0: int, n_nonlatin: int) -> pd.DataFrame:
    cand = pd.read_parquet(GOLD_DIR / "gold_v5_candidates.parquet")
    b0 = pd.read_csv(GOLD_DIR / "batches" / "gold_v5_batch_000.csv")
    b0_ids = list(b0["gold_row_id"].head(n_batch0))
    rows0 = cand[cand["gold_row_id"].isin(b0_ids)]
    nonlatin = (
        cand[
            (cand["half"] == "unscoped")
            & (cand["script"].isin(["cjk_han", "japanese_kana", "thai", "hangul"]))
        ]
        .sort_values("gold_row_id")
        .head(n_nonlatin)
    )
    return pd.concat([rows0, nonlatin], ignore_index=True)


async def _one_pass(payloads):
    labels = await passb._call(passb._agent(), payloads)
    return {lb.gold_row_id: (lb.verdict, lb.code, lb.division) for lb in labels}


async def run(
    n_passes: int, n_batch0: int, n_nonlatin: int, with_taxonomy: bool = False
):
    passb.MODEL = "gemini-3.1-flash-lite"
    leaves, _ = load_taxonomy_index()
    if with_taxonomy:
        from prices.enrich.tier_b.taxonomy_index import load_coicop_context

        ctx = load_coicop_context()
        _orig_agent = passb._agent
        passb._agent = lambda extra="": _orig_agent(
            "\n\n## VALID COICOP LEAVES — a `leaf` code MUST be copied exactly from this list:\n"
            + ctx
            + extra
        )
    sample = _sample(n_batch0, n_nonlatin)
    payloads = [passb._payload(r) for _, r in sample.iterrows()]
    ids = [p["gold_row_id"] for p in payloads]

    per_row = {i: [] for i in ids}
    n_ok, n_fail = 0, 0
    for k in range(n_passes):
        try:
            res = await _one_pass(payloads)
            for i in ids:
                if i in res:
                    per_row[i].append(res[i])
            n_ok += 1
        except Exception as e:
            n_fail += 1
            print(f"pass {k}: FAILED {type(e).__name__}: {str(e)[:70]}")

    pass_a = {}
    pa_path = GOLD_DIR / "labels" / "pass_a_batch_000.json"
    if pa_path.exists():
        for x in json.load(open(pa_path)):
            pass_a[x["gold_row_id"]] = (
                x.get("verdict"),
                x.get("code"),
                x.get("division"),
            )

    rows_report = []
    agree_vc, agree_v, agree_d, valid_frac = [], [], [], []
    perfect = 0
    xf_vc = xf_v = xf_d = xf_n = 0
    for i in ids:
        obs = per_row[i]
        if not obs:
            continue
        vc = Counter((v, c) for v, c, _ in obs)
        vv = Counter(v for v, _, _ in obs)
        dd = Counter(d for _, _, d in obs)
        mode_vc, mode_vc_n = vc.most_common(1)[0]
        top_vc = mode_vc_n / len(obs)
        top_v = vv.most_common(1)[0][1] / len(obs)
        top_d = dd.most_common(1)[0][1] / len(obs)
        vfrac = sum(1 for v, c, _ in obs if v != "leaf" or c in leaves) / len(obs)
        agree_vc.append(top_vc)
        agree_v.append(top_v)
        agree_d.append(top_d)
        valid_frac.append(vfrac)
        if len(vc) == 1:
            perfect += 1
        row = {
            "gold_row_id": i,
            "n_obs": len(obs),
            "n_unique_verdict_code": len(vc),
            "modal_verdict_code": list(mode_vc),
            "self_agree_verdict_code": round(top_vc, 3),
            "self_agree_verdict": round(top_v, 3),
            "leaf_valid_frac": round(vfrac, 3),
        }
        if i in pass_a:
            pav, pac, pad = pass_a[i]
            row["pass_a"] = [pav, pac]
            xf_n += 1
            if (pav, pac) == mode_vc:
                xf_vc += 1
            if pav == mode_vc[0]:
                xf_v += 1
            if pad == dd.most_common(1)[0][0]:
                xf_d += 1
        rows_report.append(row)

    def _mean(xs):
        return round(sum(xs) / len(xs), 3) if xs else None

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": "gemini-3.1-flash-lite",
        "n_passes_ok": n_ok,
        "n_passes_failed": n_fail,
        "n_rows": len(rows_report),
        "self_consistency": {
            "mean_agree_verdict_code": _mean(agree_vc),
            "mean_agree_verdict_only": _mean(agree_v),
            "mean_agree_division_only": _mean(agree_d),
            "rows_perfectly_consistent": perfect,
            "pct_rows_perfect": round(perfect / len(rows_report), 3)
            if rows_report
            else None,
            "mean_leaf_valid_frac": _mean(valid_frac),
        },
        "cross_family_vs_gpt5_passA": {
            "n_overlap": xf_n,
            "agree_verdict_code": round(xf_vc / xf_n, 3) if xf_n else None,
            "agree_verdict_only": round(xf_v / xf_n, 3) if xf_n else None,
            "agree_division_only": round(xf_d / xf_n, 3) if xf_n else None,
        },
        "rows": rows_report,
    }
    out_path = OUT_PATH.with_name(
        "selfconsistency_flashlite_taxonomy.json" if with_taxonomy else OUT_PATH.name
    )
    out_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("\n===== flash-lite self-consistency probe =====")
    print(f"passes ok/fail: {n_ok}/{n_fail}  rows: {len(rows_report)}")
    sc = summary["self_consistency"]
    print(
        f"self-agree (verdict+code): mean {sc['mean_agree_verdict_code']}  "
        f"perfect rows: {sc['rows_perfectly_consistent']}/{len(rows_report)} ({sc['pct_rows_perfect']})"
    )
    print(
        f"self-agree (verdict only): {sc['mean_agree_verdict_only']}   "
        f"(division only): {sc['mean_agree_division_only']}"
    )
    print(f"leaf-code valid frac: {sc['mean_leaf_valid_frac']}")
    xf = summary["cross_family_vs_gpt5_passA"]
    print(
        f"vs gpt-5 Pass A (n={xf['n_overlap']}): verdict+code {xf['agree_verdict_code']}  "
        f"verdict {xf['agree_verdict_only']}  division {xf['agree_division_only']}"
    )
    print(f"-> {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--passes", type=int, default=50)
    ap.add_argument("--n-batch0", type=int, default=20)
    ap.add_argument("--n-nonlatin", type=int, default=10)
    ap.add_argument(
        "--with-taxonomy",
        action="store_true",
        help="Inject the 538-leaf codebook into the prompt",
    )
    args = ap.parse_args()
    asyncio.run(run(args.passes, args.n_batch0, args.n_nonlatin, args.with_taxonomy))


if __name__ == "__main__":
    main()
