"""(embedding → head) COICOP classifier — versioned model bundles.

A logistic-regression head over Qwen3-Embedding vectors of the RAW product
name, predicting the COICOP leaf (see ``train.py`` / ``predict.py``). Trained on
the canonical gold set (``dataset.py``); each bundle is one ``model.joblib``
carrying {clf, classes, tau, division, embed_model}.

Artifacts are versioned under
``data/prices/_enrich/_models/classifier/{version}/`` with a ``latest.txt``
pointer promoted only by ``prices train-classifier --bless``.
"""

from __future__ import annotations

from pathlib import Path

from prices.enrich import config

MODELS_DIR = config.ENRICH_DIR / "_models" / "classifier"
LATEST_POINTER = MODELS_DIR / "latest.txt"

MODEL_FILE = "model.joblib"
TRAIN_FILE = "train.parquet"
MANIFEST_FILE = "training_manifest.json"
EVAL_METRICS_FILE = "eval_metrics.json"


def version_dir(version: str) -> Path:
    return MODELS_DIR / version


def list_versions() -> list[str]:
    if not MODELS_DIR.exists():
        return []
    vs = [
        p.name
        for p in MODELS_DIR.iterdir()
        if p.is_dir() and p.name.startswith("v") and p.name[1:].isdigit()
    ]
    return sorted(vs, key=lambda v: int(v[1:]))


def next_version() -> str:
    vs = list_versions()
    return "v0" if not vs else f"v{int(vs[-1][1:]) + 1}"


def read_latest() -> str | None:
    if not LATEST_POINTER.exists():
        return None
    v = LATEST_POINTER.read_text().strip()
    return v or None


def write_latest(version: str) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_POINTER.write_text(version + "\n", encoding="utf-8")
