import json

import pytest

from prices.enrich.consensus import apply as apply_mod
from prices.enrich.consensus import resolutions as R

LEAVES = {"01.1.1.3.9", "02.1.1.3.9", "01.2.1.1.1"}


# --------------------------------------------------------------------------- #
# resolutions parsing / validation
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_parse_resolutions_normalizes_and_validates():
    payload = {
        "resolver": "gemini-3.1-flash-lite",
        "resolutions": [
            {
                "canonical_key": "Coca Cola 1.5L",
                "decision": "leaf",
                "leaf": "02.1.1.3.9",
            },
            {"canonical_key": "gift card 50", "decision": "exclude", "confidence": 0.9},
            {"canonical_key": "hamper", "decision": "escalate"},
        ],
    }
    out = R.parse_resolutions(payload, valid_leaves=LEAVES)
    assert [r["decision"] for r in out] == ["leaf", "exclude", "escalate"]
    # canonical_key is norm_key'd; exclude/escalate carry no leaf; resolver inherited
    assert out[1]["leaf"] is None and out[1]["resolver"] == "gemini-3.1-flash-lite"
    assert out[0]["canonical_key"] == "coca cola 1 5l"  # norm_key strips punctuation


@pytest.mark.unit
def test_parse_rejects_bad_decision_and_unknown_leaf():
    with pytest.raises(ValueError):
        R.parse_resolutions(
            {"resolutions": [{"canonical_key": "x", "decision": "nope"}]}
        )
    with pytest.raises(ValueError):
        R.parse_resolutions(
            {
                "resolutions": [
                    {"canonical_key": "x", "decision": "leaf", "leaf": "99.9.9.9.9"}
                ]
            },
            valid_leaves=LEAVES,
        )
    with pytest.raises(ValueError):
        R.parse_resolutions(
            {"resolutions": [{"canonical_key": "x", "decision": "leaf"}]}
        )


# --------------------------------------------------------------------------- #
# merge across resolver files -> disagreement escalates
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_merge_escalates_cross_resolver_disagreement():
    a = R.parse_resolutions(
        {
            "resolver": "A",
            "resolutions": [
                {"canonical_key": "agree", "decision": "leaf", "leaf": "01.1.1.3.9"},
                {"canonical_key": "clash", "decision": "leaf", "leaf": "01.1.1.3.9"},
            ],
        },
        valid_leaves=LEAVES,
    )
    b = R.parse_resolutions(
        {
            "resolver": "B",
            "resolutions": [
                {"canonical_key": "agree", "decision": "leaf", "leaf": "01.1.1.3.9"},
                {"canonical_key": "clash", "decision": "exclude"},
            ],
        },
        valid_leaves=LEAVES,
    )
    applicable, escalated = R.merge_resolution_sets([a, b])
    assert {r["canonical_key"] for r in applicable} == {"agree"}
    assert {r["canonical_key"] for r in escalated} == {"clash"}
    assert escalated[0]["reason"] == "cross-resolver-disagreement"


@pytest.mark.unit
def test_explicit_escalate_row_routes_out():
    rows = R.parse_resolutions(
        {"resolutions": [{"canonical_key": "k", "decision": "escalate"}]}
    )
    applicable, escalated = R.merge_resolution_sets([rows])
    assert not applicable and len(escalated) == 1


# --------------------------------------------------------------------------- #
# to_store_rows shape is label_store-appendable
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_to_store_rows_shape_and_roundtrip(tmp_path):
    from prices.enrich import label_store

    rows = R.parse_resolutions(
        {
            "resolver": "opus",
            "resolutions": [
                {"canonical_key": "milk 1l", "decision": "leaf", "leaf": "01.1.1.3.9"},
                {"canonical_key": "gift card", "decision": "exclude"},
                {"canonical_key": "toss", "decision": "escalate"},
            ],
        },
        valid_leaves=LEAVES,
    )
    frame = R.to_store_rows(rows)
    assert list(frame["tier"].unique()) == ["T3_adjudicated"]
    assert len(frame) == 2  # escalate dropped
    # label_store accepts it (validates decision/tier), writes to a temp store
    written = label_store.append(frame, path=tmp_path / "ls.parquet")
    assert len(written) == 2
    act = label_store.active(path=tmp_path / "ls.parquet")
    assert set(act["decision"]) == {"leaf", "exclude"}
    assert act[act["decision"] == "leaf"].iloc[0]["provenance"] == "apply:opus"


# --------------------------------------------------------------------------- #
# apply_resolution_files orchestration (store.append + escalation, no lexicon)
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_apply_resolution_files_writes_and_escalates(tmp_path, monkeypatch):
    captured = {}

    def fake_append(df):
        captured["rows"] = df
        return df

    monkeypatch.setattr(apply_mod.label_store, "append", fake_append)
    monkeypatch.setattr(apply_mod, "ADJUDICATION_DIR", tmp_path / "adj")

    f1 = tmp_path / "a.json"
    f2 = tmp_path / "b.json"
    f1.write_text(
        json.dumps(
            {
                "resolver": "A",
                "resolutions": [
                    {"canonical_key": "keep", "decision": "leaf", "leaf": "01.1.1.3.9"},
                    {
                        "canonical_key": "clash",
                        "decision": "leaf",
                        "leaf": "01.1.1.3.9",
                    },
                ],
            }
        )
    )
    f2.write_text(
        json.dumps(
            {
                "resolver": "B",
                "resolutions": [
                    {"canonical_key": "clash", "decision": "exclude"},
                ],
            }
        )
    )

    summary = apply_mod.apply_resolution_files(
        [f1, f2], regen_lexicon=False, valid_leaves=LEAVES
    )
    assert summary["written"] == 1 and summary["escalated"] == 1
    assert list(captured["rows"]["canonical_key"]) == ["keep"]
    assert summary["escalated_path"] and (tmp_path / "adj").exists()
    assert summary["lexicon_rebuilt"] is False


# --------------------------------------------------------------------------- #
# gazetteer keep-first fossilization fix: repeats increment n
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_gazetteer_repeat_increments_n_same_role(tmp_path):
    from prices.enrich.base_items import store

    store.set_data_dir(tmp_path)
    store.append_gazetteer("pineapple", {"juice": ("form:01.2.1.1.1", "run1")})
    store.append_gazetteer("pineapple", {"juice": ("form:01.2.1.1.1", "run2")})
    gaz = store.load_gazetteer()
    row = gaz[(gaz["base_item"] == "pineapple") & (gaz["token"] == "juice")].iloc[0]
    assert int(row["n"]) == 2
    assert row["provenance"] == "run1;run2"


@pytest.mark.unit
def test_gazetteer_repeat_different_role_keeps_first(tmp_path):
    from prices.enrich.base_items import store

    store.set_data_dir(tmp_path)
    store.append_gazetteer("mango", {"green": ("variety", "run1")})
    store.append_gazetteer("mango", {"green": ("nonfood", "run2")})
    gaz = store.load_gazetteer()
    row = gaz[(gaz["base_item"] == "mango") & (gaz["token"] == "green")].iloc[0]
    assert row["role"] == "variety" and int(row["n"]) == 1
