"""Stage 3 — the competence-vs-difficulty map.

Joins the panel's per-item labels to the eval items' truth + difficulty, bins by
KNN-entropy decile, and reports for each model: accuracy-vs-truth (competence)
and agreement-with-Opus (mimicry) per bin. The crossover — the entropy where a
cheap model's accuracy falls below Opus's by more than a tolerance — is where
that model "stops being Opus-level". Also prints an ASCII competence chart and
the routing thresholds the map implies.

Run: python -m prices.enrich.experiments.knn_competence.analyze [--eps 0.03]
"""

from __future__ import annotations

import argparse
import json

import pandas as pd

from prices.enrich import config

OUT_DIR = (
    config.REPO_ROOT / "data" / "prices" / "enrich" / "_experiments" / "knn_competence"
)
REFERENCE = "opus"


def _load() -> pd.DataFrame:
    """Join eval items (truth + difficulty) to every per-model labels_<m>.jsonl."""
    items = {
        r["name"]: r
        for r in (
            json.loads(x)
            for x in (OUT_DIR / "eval_items.jsonl").read_text().splitlines()
            if x
        )
    }
    base = {
        name: {
            "name": name,
            "true_code": it["true_code"],
            "entropy": it["knn_entropy_bits"],
            "n_distinct": it["n_distinct_candidates"],
            "knn_top1": it["knn_codes"][0],
        }
        for name, it in items.items()
    }
    for lf in sorted(OUT_DIR.glob("labels_*.jsonl")):
        model = lf.stem[len("labels_") :]
        for line in lf.read_text().splitlines():
            if not line:
                continue
            p = json.loads(line)
            row = base.get(p["name"])
            if row is None:
                continue
            row[f"code__{model}"] = p.get("code")
            row[f"conf__{model}"] = p.get("confidence")
    rows = [r for r in base.values() if any(k.startswith("code__") for k in r)]
    return pd.DataFrame(rows)


def _models(df: pd.DataFrame) -> list[str]:
    return sorted(c[len("code__") :] for c in df.columns if c.startswith("code__"))


def build(eps: float = 0.03, n_bins: int = 10) -> pd.DataFrame:
    df = _load()
    models = _models(df)
    df["correct_knn"] = df["knn_top1"] == df["true_code"]
    for m in models:
        df[f"correct__{m}"] = df[f"code__{m}"] == df["true_code"]
        if REFERENCE in models:
            df[f"agree_ref__{m}"] = df[f"code__{m}"] == df[f"code__{REFERENCE}"]

    df = df.sort_values("entropy").reset_index(drop=True)
    df["bin"] = pd.qcut(df["entropy"].rank(method="first"), n_bins, labels=False)

    recs = []
    for b, grp in df.groupby("bin"):
        rec = {
            "bin": int(b),
            "entropy_lo": round(float(grp["entropy"].min()), 3),
            "entropy_hi": round(float(grp["entropy"].max()), 3),
            "n": int(len(grp)),
            "acc_knn": round(float(grp["correct_knn"].mean()), 3),
        }
        for m in models:
            rec[f"acc_{m}"] = round(float(grp[f"correct__{m}"].mean()), 3)
            if REFERENCE in models and m != REFERENCE:
                rec[f"agreeRef_{m}"] = round(float(grp[f"agree_ref__{m}"].mean()), 3)
        recs.append(rec)
    cmap = pd.DataFrame(recs)

    out = OUT_DIR / "competence_map.csv"
    cmap.to_csv(out, index=False)

    _print_report(df, cmap, models, eps)
    print(f"\nwrote {out}")
    return cmap


def _print_report(df, cmap, models, eps) -> None:
    print("\n=== Overall accuracy-vs-truth ===")
    for m in ["knn"] + models:
        col = "correct_knn" if m == "knn" else f"correct__{m}"
        print(f"  {m:10s} {df[col].mean():.3f}")

    print("\n=== Competence by KNN-entropy bin (accuracy-vs-truth) ===")
    hdr = "bin  ent_lo-ent_hi   n   knn  " + " ".join(f"{m[:6]:>6s}" for m in models)
    print(hdr)
    for _, r in cmap.iterrows():
        cells = " ".join(f"{r[f'acc_{m}']:6.3f}" for m in models)
        print(
            f"{int(r['bin']):>3d}  {r['entropy_lo']:.2f}-{r['entropy_hi']:.2f}  "
            f"{int(r['n']):>3d} {r['acc_knn']:5.3f}  {cells}"
        )

    if REFERENCE in models:
        print(
            f"\n=== Crossover: where each model falls > {eps:.0%} below {REFERENCE} ==="
        )
        for m in models:
            if m == REFERENCE:
                continue
            crossed = None
            for _, r in cmap.iterrows():
                if r[f"acc_{REFERENCE}"] - r[f"acc_{m}"] > eps:
                    crossed = r
                    break
            if crossed is None:
                print(
                    f"  {m:8s} tracks {REFERENCE} across the whole range (no crossover)"
                )
            else:
                print(
                    f"  {m:8s} peels off at bin {int(crossed['bin'])} "
                    f"(entropy ~{crossed['entropy_lo']:.2f} bits) — "
                    f"below there it stays Opus-level"
                )
        print(
            "\nRouting implied: send an item to the cheapest model whose competence "
            "frontier covers its KNN-entropy; escalate the rest to Opus."
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eps", type=float, default=0.03)
    ap.add_argument("--bins", type=int, default=10)
    args = ap.parse_args()
    build(eps=args.eps, n_bins=args.bins)


if __name__ == "__main__":
    main()
