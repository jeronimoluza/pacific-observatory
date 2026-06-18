"""Mutual-information backbone for the Layer-1 F1-F6 diagnostics.

The estimator itself is NOT hand-rolled: categorical-vs-categorical MI is
`sklearn.metrics.mutual_info_score` and continuous-vs-categorical MI is
`sklearn.feature_selection.mutual_info_classif`. sklearn returns MI in *nats*;
everything here is converted to *bits* via `log2(e)` so the report speaks one
unit. Only the bits conversion, the entropy/conditional-entropy identities, and
the small-sample-bias floor are local additions.

Small-sample-bias caveat (RESEARCH MI section + Pitfall 3): on the 313-row
working gold, plug-in MI is upward-biased and the bias grows with the
component's cardinality, so brand / identity-noun tokens look inflated relative
to low-cardinality dimension / pack. `normalized_info_gain` (MI / H(target))
and `mi_with_null` (the permutation-null mean as the bias floor) surface this so
a raw MI is never read in isolation.

This module reads no files. It operates on label arrays handed in by the
F-report module, which reads only the 313-row working gold — never the sealed
held-out cert set.
"""

from __future__ import annotations

import numpy as np
from numpy.random import Generator
from sklearn.feature_selection import mutual_info_classif
from sklearn.metrics import mutual_info_score

_NAT_TO_BIT = float(np.log2(np.e))


def mi_bits(x_labels, y_labels) -> float:
    """Mutual information of two categorical label vectors, in bits.

    Wraps `sklearn.metrics.mutual_info_score` (nats) and converts to bits. The
    estimate is non-negative (sklearn clips negatives to 0).
    """
    return float(mutual_info_score(x_labels, y_labels) * _NAT_TO_BIT)


def entropy_bits(labels) -> float:
    """Shannon entropy of a categorical label vector, in bits.

    A label is perfectly predictive of itself, so H(labels) == I(labels;labels);
    routing entropy through `mutual_info_score(labels, labels)` keeps the
    estimator consistent with `mi_bits` (same nats->bits conversion). A constant
    vector returns 0.0.
    """
    return mi_bits(labels, labels)


def conditional_entropy_bits(target, component) -> float:
    """Conditional entropy H(target | component), in bits.

    Identity: H(target | component) == H(target) - I(component; target).
    """
    return entropy_bits(target) - mi_bits(component, target)


def normalized_info_gain(component, target) -> float:
    """Normalized info-gain MI(component; target) / H(target), in [0, 1].

    This is the uncertainty-coefficient U(target | component): the fraction of
    the target's entropy explained by the component. Reporting it alongside raw
    MI tempers the high-cardinality upward bias. A zero-entropy (constant)
    target returns 0.0 (nothing to explain).
    """
    h_target = entropy_bits(target)
    if h_target <= 0.0:
        return 0.0
    return mi_bits(component, target) / h_target


def mi_classif_bits(
    magnitude_array,
    target_labels,
    *,
    random_state: int = 0,
) -> float:
    """MI of a continuous magnitude feature vs a categorical target, in bits.

    Uses `sklearn.feature_selection.mutual_info_classif` with
    `discrete_features=False` (kNN entropy estimator) and a fixed
    `random_state` so the estimate is deterministic. sklearn returns nats per
    feature; this returns the single feature's MI converted to bits.
    """
    x = np.asarray(magnitude_array, dtype=float).reshape(-1, 1)
    y = np.asarray(target_labels)
    mi_nats = mutual_info_classif(
        x,
        y,
        discrete_features=False,
        random_state=random_state,
    )
    return float(mi_nats[0] * _NAT_TO_BIT)


def mi_with_null(
    x_labels,
    y_labels,
    rng: Generator,
    n: int = 500,
) -> tuple[float, float, float]:
    """Observed MI plus a permutation-null floor, all in bits.

    Returns `(observed_bits, null_mean_bits, null_p95_bits)`. The null shuffles
    the *target* only (`rng.permutation(y)`) and recomputes MI `n` times; its
    mean is the upward-bias floor for the 313-row gold and its 95th percentile
    is a rough significance threshold. Pass a seeded numpy Generator for
    reproducible nulls. `null_mean >= 0` since MI is non-negative.
    """
    observed = mi_bits(x_labels, y_labels)
    y = np.asarray(y_labels)
    null = [mi_bits(x_labels, rng.permutation(y)) for _ in range(n)]
    return observed, float(np.mean(null)), float(np.percentile(null, 95))
