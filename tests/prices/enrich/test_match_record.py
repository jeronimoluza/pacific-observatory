"""Permanent regression net for the opt-in §9 match-event recorder.

Three standing guarantees:

1. **OFF ≡ baseline** — with the recorder disabled (the production default),
   ``extract()`` returns the frozen Phase-1.5 ``StructuralFields`` tuples
   field-for-field and the sink buffers nothing (recording is observation,
   never mutation).
2. **Default-off** — a fresh ``reset()``/``disable()`` leaves ``is_recording()``
   False and ``begin_row()`` a no-op (no active row, no buffered events).
3. **ON log-shape** — armed, the three §9 parquets carry pattern_id / char span /
   capture groups / accepted+suppressed verdicts / a non-null suppression_reason
   from the fixed vocabulary / priority_rank / per-row residual_text, and every
   suppression has a non-null reason (the always-None promo_reason defect closed).

All output lands only under ``tmp_path``; the real ``data/`` dir is never touched.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from prices.enrich import match_record as mr
from prices.enrich.extract import extract

_FIELDS = (
    "pricing_basis",
    "amount_value",
    "standard_unit",
    "count",
    "multiplier",
    "is_promotion",
    "is_bundle",
    "is_multipack",
    "promo_reason",
)

# (id, name, lang, country, expected 9-field StructuralFields tuple) — baked
# verbatim from the frozen pre-refactor oracle (see test_extract_equivalence.py).
_OFF_ROWS = [
    (
        "apos",
        "Centrum 20'S X 2g",
        "en",
        "",
        ("mass", 0.002, "kg", 1, 20, False, False, True, None),
    ),
    (
        "pharma",
        "Paracetamol 100mg (per Tablet)",
        "en",
        "",
        ("count", None, "unit", 1, 1, False, False, False, None),
    ),
    (
        "pack_mass",
        "Sugar 2KG",
        "en",
        "",
        ("mass", 2.0, "kg", 1, 1, False, False, False, None),
    ),
    (
        "appliance",
        "Classic 2 Rice Cooker 3L",
        "en",
        "",
        ("item", None, "item", 1, 1, False, False, False, None),
    ),
    (
        "marketing",
        "ウェットティッシュ 953枚突破 4枚セット",
        "ja",
        "",
        ("item", None, "item", 1, 1, False, False, False, None),
    ),
    (
        "servings",
        "即席スープ [50杯分] 200g×1袋 お徳用",
        "ja",
        "",
        ("mass", 0.2, "kg", 1, 1, True, False, False, None),
    ),
    (
        "count_only",
        "Pencils 12 PCS",
        "en",
        "",
        ("count", None, "unit", 12, 1, False, False, True, None),
    ),
    (
        "multipack",
        "Plain Crackers 4x20g",
        "en",
        "",
        ("mass", 0.02, "kg", 1, 4, False, False, True, None),
    ),
    (
        "plain",
        "Generic Brand Raincoat XL",
        "en",
        "",
        ("item", None, "item", 1, 1, False, False, False, None),
    ),
]

# Probe rows for the ON tests: covers apos (rung 1), pharma (2), pack_unit (3),
# count-only (7), item fallback (9), appliance/servings/total-breakdown
# suppressions, and a multipack whose accepted span is stripped from the residual.
_PROBE = [
    ("apos", "Centrum 20'S X 2g", "en", ""),
    ("pharma", "Paracetamol 100mg (per Tablet)", "en", ""),
    ("pack", "Sugar 2KG", "en", ""),
    ("count", "Pencils 12 PCS", "en", ""),
    ("plain", "Generic Brand Raincoat XL", "en", ""),
    ("appliance", "Classic 2 Rice Cooker 3L", "en", ""),
    ("servings", "即席スープ [50杯分] 200g×1袋 お徳用", "ja", ""),
    ("total_bd", "コシヒカリ 白米 10kg（5kg×2袋）令和7年産", "ja", ""),
    ("multipack", "Frozen Mackerel 500g x10 can", "en", ""),
]


@pytest.fixture(autouse=True)
def _clean_recorder():
    """Keep tests from leaking armed state in either direction."""
    mr.disable()
    yield
    mr.disable()


def _record_probe(out_dir):
    mr.enable(sample_rate=1.0, out_dir=out_dir)
    for rid, name, lang, country in _PROBE:
        mr.begin_row(
            row_id=rid, raw_name=name, working_name=name, country=country, source="test"
        )
        extract(name, None, country, lang)
        mr.end_row(None)
    paths = mr.flush(out_dir)
    return (
        pd.read_parquet(paths["match"]),
        pd.read_parquet(paths["suppression"]),
        pd.read_parquet(paths["residual"]),
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "name, lang, country, expected",
    [(n, lg, c, e) for _id, n, lg, c, e in _OFF_ROWS],
    ids=[r[0] for r in _OFF_ROWS],
)
def test_recording_off_is_byte_identical(name, lang, country, expected):
    mr.disable()
    sf = extract(name, None, country, lang)
    got = tuple(getattr(sf, f) for f in _FIELDS)
    for field, want, have in zip(_FIELDS, expected, got):
        if field == "amount_value" and want is not None:
            assert have == pytest.approx(
                want, rel=1e-9
            ), f"{field}: {have!r} != {want!r}"
        else:
            assert have == want, f"{field}: {have!r} != {want!r}"
    # Observation, never mutation: nothing buffered when off.
    assert mr.is_recording() is False
    assert mr._SINK is None
    assert mr._CURRENT is None


@pytest.mark.unit
def test_default_off():
    mr.disable()
    assert mr.is_recording() is False
    # begin_row without enable() opens no active row -> every record_* drops.
    mr.begin_row(
        row_id="x",
        raw_name="Sugar 2KG",
        working_name="Sugar 2KG",
        country="",
        source="",
    )
    assert mr._CURRENT is None
    extract("Sugar 2KG", None, "", "en")
    assert mr._SINK is None


@pytest.mark.unit
def test_recording_on_emits_three_logs(tmp_path):
    m, s, r = _record_probe(tmp_path)

    expected_cols = {
        "row_id",
        "regex_id",
        "matched_text",
        "start_char",
        "end_char",
        "capture_groups_json",
        "candidate_amount",
        "candidate_unit",
        "candidate_multiplier",
        "candidate_basis",
        "accepted",
        "suppressed",
        "suppression_reason",
        "priority_rank",
    }
    assert expected_cols <= set(m.columns)

    # At most one accepted candidate per row (item-rung rows have none — the
    # item fallback is not an enumerated candidate).
    per_row_accepted = m.groupby("row_id")["accepted"].sum()
    assert (per_row_accepted <= 1).all()

    # The winning rung lands as priority_rank on the accepted candidate.
    acc = m[m["accepted"]].set_index("row_id")
    assert acc["priority_rank"].between(1, 9).all()
    assert int(acc.loc["apos", "priority_rank"]) == 1
    assert int(acc.loc["pharma", "priority_rank"]) == 2
    assert int(acc.loc["pack", "priority_rank"]) == 3
    assert int(acc.loc["count", "priority_rank"]) == 7
    assert int(acc.loc["multipack", "priority_rank"]) == 3

    # capture_groups_json is always a JSON object; spans are threaded out.
    for raw in m["capture_groups_json"]:
        assert isinstance(json.loads(raw), dict)
    assert m["start_char"].notna().any()
    assert m["end_char"].notna().any()

    # Suppression log: non-null reason from the vocabulary, with a char span on
    # the appliance-capacity cue.
    appl = s[s["row_id"] == "appliance"]
    assert (appl["suppression_reason"] == "appliance_capacity").any()
    assert appl["start_char"].notna().any()
    assert appl["end_char"].notna().any()
    assert (
        s[s["row_id"] == "servings"]["suppression_reason"] == "servings_portion"
    ).any()
    assert (
        s[s["row_id"] == "total_bd"]["suppression_reason"] == "total_breakdown"
    ).any()

    # Residual log: exactly one row per processed row; accepted spans removed.
    assert len(r) == len(_PROBE)
    assert r["row_id"].nunique() == len(_PROBE)
    res = r.set_index("row_id")["residual_text"]
    assert "Mackerel" in res.loc["multipack"]
    assert "500g" not in res.loc["multipack"]
    assert "x10" not in res.loc["multipack"]
    assert res.loc["pack"].strip() == "Sugar"
    assert res.loc["plain"] == "Generic Brand Raincoat XL"


@pytest.mark.unit
def test_every_suppression_has_reason(tmp_path):
    _m, s, _r = _record_probe(tmp_path)
    assert len(s) >= 1
    assert s["suppression_reason"].notna().all()
    assert (s["suppression_reason"].astype(str).str.len() > 0).all()
    assert set(s["suppression_reason"]) <= mr.REASON_TOKENS


@pytest.mark.unit
@pytest.mark.parametrize(
    "name, lang, country, expected",
    [(n, lg, c, e) for _id, n, lg, c, e in _OFF_ROWS],
    ids=[r[0] for r in _OFF_ROWS],
)
def test_recording_on_does_not_perturb_byte_identical(
    name, lang, country, expected, tmp_path
):
    # The shape labeler runs inside end_row when recording is ON; arming the
    # recorder (and invoking classify) must leave the StructuralFields returned
    # by extract() field-for-field identical to the OFF baseline.
    mr.enable(sample_rate=1.0, out_dir=tmp_path)
    mr.begin_row(
        row_id="probe",
        raw_name=name,
        working_name=name,
        country=country,
        source="test",
    )
    sf = extract(name, None, country, lang)
    mr.end_row(sf)
    got = tuple(getattr(sf, f) for f in _FIELDS)
    for field, want, have in zip(_FIELDS, expected, got):
        if field == "amount_value" and want is not None:
            assert have == pytest.approx(
                want, rel=1e-9
            ), f"{field}: {have!r} != {want!r}"
        else:
            assert have == want, f"{field}: {have!r} != {want!r}"


@pytest.mark.unit
def test_recording_on_persists_shape_and_modifiers(tmp_path):
    from prices.enrich.shape_label import SHAPES

    mr.enable(sample_rate=1.0, out_dir=tmp_path)
    for rid, name, lang, country in _PROBE:
        mr.begin_row(
            row_id=rid, raw_name=name, working_name=name, country=country, source="test"
        )
        sf = extract(name, None, country, lang)
        mr.end_row(sf)
    paths = mr.flush(tmp_path)
    r = pd.read_parquet(paths["residual"])

    assert "shape" in r.columns
    assert "modifiers" in r.columns
    # One row per processed row; every shape is a member of the SHAPES vocabulary.
    assert len(r) == len(_PROBE)
    assert r["row_id"].nunique() == len(_PROBE)
    assert set(r["shape"]) <= SHAPES
    # modifiers serializes parquet-safe as a JSON list per row.
    for raw in r["modifiers"]:
        assert isinstance(json.loads(raw), list)
