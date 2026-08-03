"""Classifier eval (W2.3).

On the name-disjoint held-out split: leaf-among-leaves accuracy, GREEN top-1,
reject->leaf leakage at tau=0, precision-coverage curve by tau, per-script and
per-leaf tables, and prediction throughput. When gold v5 exists, additionally
scores the model against it (the disjoint measuring stick). Writes
``eval_report.md`` + csvs + ``eval_metrics.json`` into the version directory.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from prices.enrich import config
from prices.enrich.classifier import (
    EVAL_METRICS_FILE,
    EVAL_REPORT_FILE,
    REJECT_CLASSES,
    version_dir,
)
from prices.enrich.classifier.dataset import load_table
from prices.enrich.classifier.predict import Predictor

GOLD_FINAL = (
    config.REPO_ROOT / "data" / "prices" / "enrich" / "gold" / "gold_v5_final.parquet"
)
TAUS = [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 0.98]
TOP_LEAVES = 30


def _holdout_metrics(pred, conf, leaf_among, y):
    reject = list(REJECT_CLASSES)
    green = ~np.isin(y, reject)
    leaf_pred = ~np.isin(pred, reject)
    curve = []
    for t in TAUS:
        m = leaf_pred & (conf >= t)
        n = int(m.sum())
        curve.append(
            {
                "tau": t,
                "coverage": round(n / len(y), 4),
                "precision": round(float((pred[m] == y[m]).mean()), 4) if n else None,
                "n": n,
            }
        )
    return {
        "n_test": int(len(y)),
        "n_green": int(green.sum()),
        "green_top1_acc": round(float((pred[green] == y[green]).mean()), 4),
        "leaf_among_leaves_acc": round(
            float((leaf_among[green] == y[green]).mean()), 4
        ),
        "reject_to_leaf_leakage": round(float(leaf_pred[~green].mean()), 4),
    }, pd.DataFrame(curve)


def _per_script(te, pred, conf, leaf_among, y):
    reject = list(REJECT_CLASSES)
    green = ~np.isin(y, reject)
    leaf_pred = ~np.isin(pred, reject)
    rows = []
    for s in pd.Series(te["script"]).value_counts().index:
        m = (te["script"] == s).to_numpy()
        g = m & green
        rows.append(
            {
                "script": s,
                "test_keys": int(m.sum()),
                "test_green": int(g.sum()),
                "green_top1": round(float((pred[g] == y[g]).mean()), 4)
                if g.sum()
                else None,
                "leaf_among_leaves": round(float((leaf_among[g] == y[g]).mean()), 4)
                if g.sum()
                else None,
                "rejects_to_leaf": round(float(leaf_pred[m & ~green].mean()), 4)
                if (m & ~green).sum()
                else None,
            }
        )
    return pd.DataFrame(rows)


def _per_leaf(pred, y):
    reject = list(REJECT_CLASSES)
    green = ~np.isin(y, reject)
    rows = []
    for lf in pd.Series(y[green]).value_counts().head(TOP_LEAVES).index:
        pm = pred == lf
        tm = y == lf
        rows.append(
            {
                "leaf": lf,
                "support": int(tm.sum()),
                "precision": round(float((y[pm] == lf).mean()), 4)
                if pm.sum()
                else None,
                "recall": round(float((pred[tm] == lf).mean()), 4)
                if tm.sum()
                else None,
            }
        )
    return pd.DataFrame(rows)


def _gold_metrics(predictor: Predictor) -> dict | None:
    if not GOLD_FINAL.exists():
        return None
    g = pd.read_parquet(GOLD_FINAL)
    leaf = g[g["verdict"] == "leaf"].copy()
    excl = g[g["verdict"] == "exclude"].copy()
    out = {"n_gold_leaf": int(len(leaf)), "n_gold_exclude": int(len(excl))}
    if len(leaf):
        pred, _, leaf_among = predictor.scores(leaf["product_name"].tolist())
        code = leaf["code"].to_numpy()
        out["gold_top1_acc"] = round(float((pred == code).mean()), 4)
        out["gold_leaf_among_leaves_acc"] = round(float((leaf_among == code).mean()), 4)
    if len(excl):
        epred, _, _ = predictor.scores(excl["product_name"].tolist())
        out["gold_exclude_to_leaf_leakage"] = round(
            float((~np.isin(epred, list(REJECT_CLASSES))).mean()), 4
        )
    return out


def _report_md(version, summary, curve, per_script, per_leaf, gold, throughput) -> str:
    lines = [
        f"# Classifier eval — {version}",
        "",
        "## Held-out (name-key-disjoint) summary",
        "",
        f"- test keys: {summary['n_test']} (green {summary['n_green']})",
        f"- GREEN top-1: **{summary['green_top1_acc']}**",
        f"- leaf-among-leaves: **{summary['leaf_among_leaves_acc']}**",
        f"- reject->leaf leakage (tau=0): **{summary['reject_to_leaf_leakage']}**",
        f"- throughput: **{throughput}** names/s",
        "",
        "## Precision-coverage by tau",
        "",
        curve.to_markdown(index=False),
        "",
        "## Per-script",
        "",
        per_script.to_markdown(index=False),
        "",
        f"## Per-leaf (top {TOP_LEAVES} by support)",
        "",
        per_leaf.to_markdown(index=False),
    ]
    if gold:
        lines += ["", "## Gold v5", "", "```json", json.dumps(gold, indent=2), "```"]
    return "\n".join(lines) + "\n"


def run(version: str) -> dict:
    df = load_table(version)
    te = df[df["split"] == "test"].reset_index(drop=True)
    predictor = Predictor(version)

    keys = te["key"].tolist()
    t0 = time.time()
    pred, conf, leaf_among = predictor.scores(keys)
    throughput = int(len(keys) / max(time.time() - t0, 1e-9))
    y = te["label"].to_numpy()

    summary, curve = _holdout_metrics(pred, conf, leaf_among, y)
    per_script = _per_script(te, pred, conf, leaf_among, y)
    per_leaf = _per_leaf(pred, y)
    gold = _gold_metrics(predictor)

    vdir = version_dir(version)
    curve.to_csv(vdir / "precision_coverage.csv", index=False)
    per_script.to_csv(vdir / "per_script.csv", index=False)
    per_leaf.to_csv(vdir / "per_leaf.csv", index=False)

    metrics = {
        "version": version,
        **summary,
        "throughput_names_per_sec": throughput,
        "per_leaf_precision": {
            r["leaf"]: r["precision"]
            for _, r in per_leaf.iterrows()
            if r["precision"] is not None
        },
        "gold": gold,
    }
    Path(vdir / EVAL_METRICS_FILE).write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    Path(vdir / EVAL_REPORT_FILE).write_text(
        _report_md(version, summary, curve, per_script, per_leaf, gold, throughput),
        encoding="utf-8",
    )
    return metrics
