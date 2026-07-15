"""Unit tests for the MEAS_x_N (measure-then-count operator) grammar shape.

`VALUE_UNIT_X_NUM` (grammar.py) previously required the operator to be one of
`x`/`X`/`×` with a plain `\\b` after the trailing count, so a `*` separator, a
`by` word-operator, or a count glued directly to a count-noun abbreviation
(`2s`, `15s`, `5P`, `12PCS`) fell through to a bare mass/volume match (or no
match at all) with the outer count silently dropped. These tests cover the
extension: `*` and `by` as accepted operators, plus a narrow trailing
count-noun suffix (`pcs?`/`p`/`'s`/`s`) consumed as part of the count so the
`\\b` boundary no longer rejects it.
"""

from __future__ import annotations

import pytest

from prices.enrich.extract import extract


def _ex(name, lang=None, country=""):
    return extract(name, None, country, lang)


@pytest.mark.parametrize(
    "name, expected_basis, expected_av, expected_mult",
    [
        # `By N` word operator (previously dropped entirely: count=1, mult=1).
        ("Onion Rings Snacks 50g By 20", "mass", 0.05, 20),
        # `*N` separator (previously not in the separator char class).
        ("MACKEREL IN TOMATO SAUCE 170G *4", "mass", 0.17, 4),
        ("HEALTHY CHEF SOYBEAN OIL 1000ML*12/CTN", "volume", 1.0, 12),
        # count glued to a trailing `PCS`/`s` count-noun abbreviation
        # (`\b` after the bare digit previously failed since the following
        # char is a word char, e.g. "2s" or "12PCS").
        ("Twisties Snacks 250g x 5pcs", "mass", 0.25, 5),
        ("SIMILAC Formula Twin Pack 1.7kg x 2s", "mass", 1.7, 2),
        ("ESTAMP Nutri Grain Plus 30g X 15s", "mass", 0.03, 15),
        ("TVBP NOODLE (SALT) 94G X 5P", "mass", 0.094, 5),
        ("Royal-D Original Electrolyte Drink 400MLx12PCS", "volume", 0.4, 12),
    ],
)
def test_measure_x_n_operator_count_captured(
    name, expected_basis, expected_av, expected_mult
):
    sf = _ex(name, lang="en")
    assert sf.pricing_basis == expected_basis
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-6)
    assert sf.count == 1
    assert sf.multiplier == expected_mult
    assert sf.is_multipack is True


def test_measure_x_n_still_requires_a_real_trailing_suffix():
    """The glued-suffix allowance is narrow (pcs?/p/'s/s only) — an unrelated
    glued word (a second measure unit) after the count must not be swallowed,
    same as before this change (the plain `\\b` boundary still rejects it)."""
    sf = _ex("Widget 50g x 4kg", lang="en")
    assert sf.multiplier == 1
    assert sf.count == 1
