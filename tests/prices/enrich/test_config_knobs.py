"""Value-parity guard for the consolidated cascade knobs.

Phase 0.5 / Plan 03 moved the four KNN cascade tunables out of inline literals
in `config.py` into a single YAML tuning surface (`static/enrich_knobs.yaml`),
mirroring the existing `static/channel_coicop_priors.yaml` pattern. The move is
behavior-preserving: values are byte-identical, only their location changed.

This test is the drift guard. It asserts:
  * the YAML tuning surface exists under static/, and
  * the four module-level constants config.py exports still equal their exact
    historical literals (150, 0.90, 0.90, 3).

If a future YAML edit silently changes a knob, this test fails before the eval
parity gate would catch the downstream accuracy drift.
"""

from __future__ import annotations

import pytest
import yaml

from prices.enrich import config

pytestmark = pytest.mark.unit


def test_enrich_knobs_yaml_exists() -> None:
    assert (
        config.ENRICH_KNOBS_PATH.exists()
    ), f"missing tuning surface: {config.ENRICH_KNOBS_PATH}"
    assert config.ENRICH_KNOBS_PATH.parent.name == "static"


def test_config_constants_equal_historical_literals() -> None:
    # Exact historical literals — the byte-identical before-values (D-05).
    assert config.KNN_BOOTSTRAP_CLUSTER_FLOOR == 150
    assert config.KNN_CLUSTER_AGREEMENT_MIN == 0.90
    assert config.KNN_SUB_LABEL_AGREEMENT_MIN == 0.90
    assert config.MIN_SAME_CHANNEL_KNN == 3


def test_yaml_values_match_exported_constants() -> None:
    # The YAML is the authoritative source; the constants must echo it exactly.
    with open(config.ENRICH_KNOBS_PATH, encoding="utf-8") as f:
        knobs = yaml.safe_load(f)
    assert knobs["knn_bootstrap_cluster_floor"] == config.KNN_BOOTSTRAP_CLUSTER_FLOOR
    assert knobs["knn_cluster_agreement_min"] == config.KNN_CLUSTER_AGREEMENT_MIN
    assert knobs["knn_sub_label_agreement_min"] == config.KNN_SUB_LABEL_AGREEMENT_MIN
    assert knobs["min_same_channel_knn"] == config.MIN_SAME_CHANNEL_KNN
