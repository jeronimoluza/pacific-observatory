"""Known-answer tests for the mutual-information backbone (mi.py).

Deterministic contingency tables give exact bits; entropy / conditional-entropy
/ normalized-info-gain identities hold; the permutation null is non-negative and
reproducible with a seeded numpy Generator.
"""

from __future__ import annotations

import numpy as np
import pytest

from prices.enrich.text_mining.mi import (
    conditional_entropy_bits,
    entropy_bits,
    mi_bits,
    mi_classif_bits,
    mi_with_null,
    normalized_info_gain,
)

TOL = 1e-9


def test_mi_bits_perfectly_correlated_binary_is_one_bit():
    x = ["a", "a", "b", "b"]
    y = ["a", "a", "b", "b"]
    assert mi_bits(x, y) == pytest.approx(1.0, abs=TOL)


def test_mi_bits_independent_is_zero():
    x = ["a", "b", "a", "b"]
    y = ["a", "a", "b", "b"]
    assert mi_bits(x, y) == pytest.approx(0.0, abs=TOL)


def test_mi_bits_non_negative():
    rng = np.random.default_rng(7)
    x = rng.integers(0, 5, size=200)
    y = rng.integers(0, 5, size=200)
    assert mi_bits(x, y) >= 0.0


def test_entropy_bits_balanced_binary_is_one():
    assert entropy_bits(["a", "a", "b", "b"]) == pytest.approx(1.0, abs=TOL)


def test_entropy_bits_constant_is_zero():
    assert entropy_bits(["a", "a", "a"]) == pytest.approx(0.0, abs=TOL)


def test_conditional_entropy_identity():
    target = ["x", "x", "y", "y", "z", "z"]
    component = ["a", "a", "b", "c", "b", "c"]
    expected = entropy_bits(target) - mi_bits(component, target)
    assert conditional_entropy_bits(target, component) == pytest.approx(
        expected, abs=TOL
    )


def test_conditional_entropy_perfect_predictor_is_zero():
    target = ["x", "x", "y", "y"]
    component = ["x", "x", "y", "y"]
    assert conditional_entropy_bits(target, component) == pytest.approx(0.0, abs=TOL)


def test_normalized_info_gain_in_unit_interval():
    target = ["x", "x", "y", "y", "z", "z"]
    component = ["a", "a", "b", "c", "b", "c"]
    nig = normalized_info_gain(component, target)
    assert 0.0 - TOL <= nig <= 1.0 + TOL


def test_normalized_info_gain_perfect_is_one():
    target = ["x", "x", "y", "y"]
    component = ["x", "x", "y", "y"]
    assert normalized_info_gain(component, target) == pytest.approx(1.0, abs=TOL)


def test_normalized_info_gain_zero_entropy_target_is_zero():
    target = ["x", "x", "x", "x"]
    component = ["a", "b", "c", "d"]
    assert normalized_info_gain(component, target) == 0.0


def test_mi_classif_bits_deterministic_and_non_negative():
    rng = np.random.default_rng(0)
    target = np.array([0, 0, 1, 1, 2, 2] * 10)
    magnitude = target.astype(float) + rng.normal(0, 0.01, size=target.size)
    a = mi_classif_bits(magnitude, target)
    b = mi_classif_bits(magnitude, target)
    assert a == pytest.approx(b, abs=TOL)
    assert a >= 0.0


def test_mi_with_null_deterministic_and_non_negative():
    x = ["a", "a", "b", "b", "c", "c"]
    y = ["x", "x", "y", "y", "z", "z"]
    obs1, mean1, p95_1 = mi_with_null(x, y, np.random.default_rng(42), n=200)
    obs2, mean2, p95_2 = mi_with_null(x, y, np.random.default_rng(42), n=200)
    assert obs1 == pytest.approx(obs2, abs=TOL)
    assert mean1 == pytest.approx(mean2, abs=TOL)
    assert p95_1 == pytest.approx(p95_2, abs=TOL)
    assert mean1 >= 0.0


def test_mi_with_null_observed_matches_mi_bits():
    x = ["a", "a", "b", "b"]
    y = ["a", "a", "b", "b"]
    obs, _mean, _p95 = mi_with_null(x, y, np.random.default_rng(1), n=50)
    assert obs == pytest.approx(mi_bits(x, y), abs=TOL)
