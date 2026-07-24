from datetime import datetime

import pandas as pd
import pytest

from prices.enrich import label_store


def _store(tmp_path):
    return tmp_path / "label_store.parquet"


@pytest.mark.unit
def test_append_normalizes_key_and_stamps(tmp_path):
    p = _store(tmp_path)
    written = label_store.append(
        pd.DataFrame(
            [
                {
                    "canonical_key": "Coca-Cola  ZERO",
                    "decision": "exclude",
                    "tier": "T0_lexicon",
                    "provenance": "test",
                }
            ]
        ),
        path=p,
    )
    assert written.iloc[0]["canonical_key"] == "coca cola zero"
    assert written.iloc[0]["row_id"]
    assert written.iloc[0]["created_at"].endswith("+00:00")
    assert written.iloc[0]["witness_votes"] == "{}"


@pytest.mark.unit
def test_append_rejects_bad_enums(tmp_path):
    p = _store(tmp_path)
    with pytest.raises(ValueError):
        label_store.append(
            pd.DataFrame(
                [
                    {
                        "canonical_key": "x y",
                        "decision": "nope",
                        "tier": "T0_memo",
                        "provenance": "t",
                    }
                ]
            ),
            path=p,
        )
    with pytest.raises(ValueError):
        label_store.append(
            pd.DataFrame(
                [
                    {
                        "canonical_key": "x y",
                        "decision": "leaf",
                        "tier": "T9",
                        "provenance": "t",
                    }
                ]
            ),
            path=p,
        )


@pytest.mark.unit
def test_append_rejects_naive_created_at(tmp_path):
    p = _store(tmp_path)
    with pytest.raises(ValueError):
        label_store.append(
            pd.DataFrame(
                [
                    {
                        "canonical_key": "x y",
                        "decision": "leaf",
                        "tier": "T2_model",
                        "provenance": "t",
                        "created_at": datetime(2026, 7, 7, 12, 0, 0),
                    }
                ]
            ),
            path=p,
        )


@pytest.mark.unit
def test_append_is_row_conserving(tmp_path):
    p = _store(tmp_path)
    label_store.append(
        pd.DataFrame(
            [
                {
                    "canonical_key": "apple",
                    "decision": "leaf",
                    "leaf": "01.1.6.1.1",
                    "tier": "T1_consensus",
                    "provenance": "a",
                }
            ]
        ),
        path=p,
    )
    label_store.append(
        pd.DataFrame(
            [
                {
                    "canonical_key": "banana",
                    "decision": "leaf",
                    "leaf": "01.1.6.1.2",
                    "tier": "T1_consensus",
                    "provenance": "a",
                }
            ]
        ),
        path=p,
    )
    assert len(label_store.load(p)) == 2


@pytest.mark.unit
def test_active_returns_latest_non_superseded(tmp_path):
    p = _store(tmp_path)
    first = label_store.append(
        pd.DataFrame(
            [
                {
                    "canonical_key": "apple",
                    "decision": "leaf",
                    "leaf": "01.1.6.1.1",
                    "tier": "T2_model",
                    "provenance": "model",
                }
            ]
        ),
        path=p,
    )
    second = label_store.append(
        pd.DataFrame(
            [
                {
                    "canonical_key": "apple",
                    "decision": "leaf",
                    "leaf": "01.1.6.1.9",
                    "tier": "T3_adjudicated",
                    "provenance": "human",
                    "created_at": "2027-01-01T00:00:00+00:00",
                }
            ]
        ),
        path=p,
    )
    n = label_store.supersede(
        [first.iloc[0]["row_id"]], by=second.iloc[0]["row_id"], path=p
    )
    assert n == 1

    act = label_store.active(p)
    assert len(act) == 1
    assert act.iloc[0]["leaf"] == "01.1.6.1.9"
    assert act.iloc[0]["tier"] == "T3_adjudicated"
    # supersede conserves rows (no deletion)
    assert len(label_store.load(p)) == 2


@pytest.mark.unit
def test_lookup_filters_to_keys(tmp_path):
    p = _store(tmp_path)
    label_store.append(
        pd.DataFrame(
            [
                {
                    "canonical_key": "apple",
                    "decision": "leaf",
                    "leaf": "01.1.6.1.1",
                    "tier": "T1_consensus",
                    "provenance": "a",
                },
                {
                    "canonical_key": "lip gloss",
                    "decision": "exclude",
                    "tier": "T0_lexicon",
                    "provenance": "a",
                },
            ]
        ),
        path=p,
    )
    hit = label_store.lookup(["Apple", "unknown thing"], path=p)
    assert list(hit["canonical_key"]) == ["apple"]


@pytest.mark.unit
def test_witness_votes_json_roundtrip(tmp_path):
    p = _store(tmp_path)
    label_store.append(
        pd.DataFrame(
            [
                {
                    "canonical_key": "apple",
                    "decision": "leaf",
                    "leaf": "01.1.6.1.1",
                    "tier": "T1_consensus",
                    "provenance": "a",
                    "witness_votes": {"model": "01.1.6.1.1", "knn": "01.1.6.1.1"},
                }
            ]
        ),
        path=p,
    )
    stored = label_store.active(p).iloc[0]["witness_votes"]
    assert '"model"' in stored
