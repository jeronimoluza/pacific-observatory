"""Unit tests for the (embedding -> head) classifier surface.

Covers the deterministic pieces without loading the Qwen embedder: the trap-veto
lexicon, the global-tau derivation, the predict-time gate+veto accept logic (via
a stub head and a patched embedder), and the gold-sourced dataset builder.
"""

import joblib
import numpy as np
import pytest

from prices.enrich import vetoes
from prices.enrich.classifier import MODEL_FILE, dataset, predict, train


@pytest.mark.unit
def test_vetoes_reject_processed_forms_only():
    # pear leaf: juice/canned are traps; a bare fresh pear is not
    assert vetoes.is_vetoed("01.1.6.3.2", "Dole Pear Juice 1L")
    assert not vetoes.is_vetoed("01.1.6.3.2", "Fresh Green Pears 1kg")
    # a leaf with no defined veto never fires
    assert not vetoes.is_vetoed("09.9.9.9.9", "anything canned juice")


@pytest.mark.unit
def test_global_tau_meets_target_precision():
    # confidences descending; the top-4 are correct then errors creep in
    conf = np.array([0.99, 0.95, 0.90, 0.85, 0.80, 0.70])
    correct = np.array([1, 1, 1, 1, 0, 0]).astype(bool)
    tau = train._global_tau(conf, correct, target=0.98)
    # at 0.85 cumulative precision is 4/4=1.0 (>=0.98); at 0.80 it drops to 4/5
    assert tau == pytest.approx(0.85)


class _StubHead:
    """Minimal predict_proba stand-in: two leaves, first row confident-correct,
    second row confident-but-vetoed, third row low-confidence."""

    classes_ = np.array(["01.1.6.3.2", "01.1.6.1.7"])

    def predict_proba(self, x):
        return np.array([[0.95, 0.05], [0.90, 0.10], [0.40, 0.60]])


@pytest.mark.unit
def test_predict_gate_and_veto(tmp_path, monkeypatch):
    from prices.enrich.classifier import version_dir

    monkeypatch.setattr("prices.enrich.classifier.MODELS_DIR", tmp_path)
    vdir = version_dir("v0")
    vdir.mkdir(parents=True)
    joblib.dump(
        {
            "version": "v0",
            "clf": _StubHead(),
            "classes": list(_StubHead.classes_),
            "tau": 0.626,
            "division": "01",
        },
        vdir / MODEL_FILE,
    )
    monkeypatch.setattr(
        "prices.enrich.embedding.embed_names",
        lambda names, **k: np.zeros((len(names), 3)),
    )
    predict._cached.cache_clear()

    names = ["Fresh Pears 1kg", "Pineapple Juice 1L", "Mystery item"]
    r = predict.Predictor("v0").predict(names)
    # row0: conf 0.95 >= tau, pear not vetoed -> accepted
    assert r.accepted[0]
    # row1: conf 0.90 >= tau but pineapple-juice trips the pineapple veto -> rejected
    assert not r.accepted[1]
    # row2: conf 0.60 < tau -> rejected
    assert not r.accepted[2]


@pytest.mark.unit
def test_dataset_build_filters_division_and_support(tmp_path, monkeypatch):
    monkeypatch.setattr("prices.enrich.classifier.MODELS_DIR", tmp_path)
    manifest = dataset.build("v0", division="01")
    table = dataset.load_table("v0")
    assert manifest["division"] == "01"
    assert set(table.columns) == {"name", "label", "division", "source"}
    assert (table["division"] == "01").all()
    assert table["label"].str.startswith("01.").all()
    # every retained leaf clears the support floor
    assert table["label"].value_counts().min() >= dataset.MIN_SUPPORT
