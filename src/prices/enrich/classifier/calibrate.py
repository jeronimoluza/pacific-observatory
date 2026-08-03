"""Per-script reliability table (W2.2 calibration).

Bins held-out predictions by (script, confidence band) and records empirical
top-1 accuracy + support. Downstream the gate can read this to temper
``w_model`` confidence where the model is optimistic (e.g. low-support CJK).
"""

from __future__ import annotations

import pandas as pd

from prices.enrich.classifier import RELIABILITY_FILE, version_dir
from prices.enrich.classifier.dataset import load_table
from prices.enrich.classifier.predict import Predictor

CONF_BINS = [0.0, 0.3, 0.5, 0.7, 0.9, 0.95, 1.01]
BIN_LABELS = ["<0.3", "0.3-0.5", "0.5-0.7", "0.7-0.9", "0.9-0.95", ">=0.95"]


def build(version: str) -> pd.DataFrame:
    df = load_table(version)
    te = df[df["split"] == "test"].reset_index(drop=True)
    pred, conf, _ = Predictor(version).scores(te["key"].tolist())
    correct = pred == te["label"].to_numpy()
    band = pd.cut(conf, bins=CONF_BINS, labels=BIN_LABELS, right=False)

    tbl = (
        pd.DataFrame({"script": te["script"], "conf_band": band, "correct": correct})
        .groupby(["script", "conf_band"], observed=True)
        .agg(support=("correct", "size"), empirical_acc=("correct", "mean"))
        .reset_index()
    )
    tbl["empirical_acc"] = tbl["empirical_acc"].round(4)
    tbl["mean_conf_lo"] = (
        tbl["conf_band"].map(dict(zip(BIN_LABELS, CONF_BINS[:-1]))).astype(float)
    )
    tbl = tbl.sort_values(["script", "mean_conf_lo"]).reset_index(drop=True)
    tbl.to_csv(version_dir(version) / RELIABILITY_FILE, index=False)
    return tbl
