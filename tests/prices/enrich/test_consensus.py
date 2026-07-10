import pandas as pd
import pytest

from prices.enrich.consensus import gate, queue, witnesses
from prices.enrich.consensus.witnesses import Vote


@pytest.fixture
def policy():
    return gate.load_policy()


# --------------------------------------------------------------------------- #
# gate tiers
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_memo_is_authoritative_over_disagreeing_model(policy):
    votes = [
        Vote("memo", "05.6.1.1", "leaf", 1.0, {}),
        Vote("model", "01.1.1.1", "leaf", 0.99, {}),
    ]
    r = gate.decide(votes, "latin_other", policy)
    assert (r.status, r.tier, r.label) == ("accept", "T0_memo", "05.6.1.1")


@pytest.mark.unit
def test_t1_consensus_needs_two_agreeing_incl_anchor(policy):
    # model + knn agree -> T1
    r = gate.decide(
        [
            Vote("model", "01.1.1.1", "leaf", 0.8, {}),
            Vote("knn", "01.1.1.1", "leaf", 0.9, {}),
        ],
        "latin_other",
        policy,
    )
    assert r.tier == "T1_consensus" and r.decision == "leaf"
    # lexicon + source(division) is NOT two *primary* anchors -> not T1
    r2 = gate.decide(
        [
            Vote("lexicon", "01.1.1.1", "leaf", 0.6, {}),
            Vote("source", "01", "division", 0.3, {}),
        ],
        "latin_other",
        policy,
    )
    assert r2.tier == "T0_lexicon"


@pytest.mark.unit
def test_t2_model_only_and_cjk_override(policy):
    hi = [Vote("model", "01.1.1.1", "leaf", 0.97, {})]
    assert gate.decide(hi, "latin_other", policy).tier == "T2_model"
    # CJK disables model-only accepts
    assert gate.decide(hi, "cjk_han", policy).status == "conflict"


@pytest.mark.unit
def test_disagreement_and_abstain(policy):
    conflict = gate.decide(
        [
            Vote("model", "01.1.1.1", "leaf", 0.8, {}),
            Vote("knn", "02.1.1.1", "leaf", 0.8, {}),
        ],
        "latin_other",
        policy,
    )
    assert conflict.status == "conflict" and conflict.reason == "witness-disagreement"
    # only corroborators, no primary -> abstain
    assert (
        gate.decide(
            [Vote("source", "01", "division", 0.3, {})], "latin_other", policy
        ).status
        == "abstain"
    )


@pytest.mark.unit
def test_reject_consensus_queued_by_default_but_maps_when_accepting(policy):
    votes = [Vote("model", "__EXCLUDE__", "reject", 0.98, {})]
    # calibrated default: non-memo reject-consensus is routed to the queue
    r = gate.decide(votes, "latin_other", policy)
    assert r.status == "conflict" and r.reason == "reject-consensus-queued"
    # opting back into reject accepts still maps label -> decision
    accepting = {**policy, "reject_consensus": "accept"}
    r2 = gate.decide(votes, "latin_other", accepting)
    assert (
        r2.status == "accept" and r2.decision == "exclude" and r2.label == "__EXCLUDE__"
    )


@pytest.mark.unit
def test_memo_reject_stays_authoritative_under_queue(policy):
    # a human/adjudicated reject in the store must survive the queue stance
    votes = [
        Vote("memo", "__EXCLUDE__", "reject", 1.0, {}),
        Vote("model", "01.1.1.1", "leaf", 0.9, {}),
    ]
    r = gate.decide(votes, "latin_other", policy)
    assert r.status == "accept" and r.tier == "T0_memo" and r.decision == "exclude"


@pytest.mark.unit
def test_reject_queue_lets_surviving_leaf_win(policy):
    # model rejects but knn proposes a leaf -> dropping the reject lets the leaf through
    votes = [
        Vote("model", "__EXCLUDE__", "reject", 0.9, {}),
        Vote("knn", "01.1.1.1", "leaf", 0.9, {}),
        Vote("cascade", "01.1.1.1", "leaf", 0.9, {}),
    ]
    r = gate.decide(votes, "latin_other", policy)
    assert r.status == "accept" and r.decision == "leaf" and r.label == "01.1.1.1"


# --------------------------------------------------------------------------- #
# witnesses (backend-free)
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_lexicon_witness_picks_highest_support():
    lex = pd.DataFrame(
        {"phrase": ["apple", "gala"], "label": ["01.1.1.1", "01.1.1.9"], "n": [200, 30]}
    )
    out = witnesses.w_lexicon(["Fresh Gala Apple"], lex=lex)
    v = out["fresh gala apple"]
    assert v.label == "01.1.1.1" and v.kind == "leaf" and v.strength > 0.5


@pytest.mark.unit
def test_source_witness_votes_single_division_only():
    rows = pd.DataFrame(
        {
            "first_name": ["milk a", "mixed b"],
            "declared_coicop_codes": ["01.1.4.1, 01.1.4.2", "01.1.1.1, 05.6.1.1"],
        }
    )
    out = witnesses.w_source(rows, "first_name")
    assert out["milk a"].label == "01" and out["milk a"].kind == "division"
    assert "mixed b" not in out  # two divisions -> no vote


@pytest.mark.unit
def test_price_plausibility(monkeypatch):
    bands = pd.DataFrame(
        {
            "leaf": ["01.1.1.1"],
            "country": ["sg"],
            "pricing_basis": ["per_kg"],
            "band_lo": [1.0],
            "band_hi": [5.0],
        }
    )
    monkeypatch.setitem(witnesses._BANDS_CACHE, "df", bands)
    assert (
        witnesses.price_plausibility("01.1.1.1", "sg", "per_kg", 3.0).detail["verdict"]
        == "plausible"
    )
    assert (
        witnesses.price_plausibility("01.1.1.1", "sg", "per_kg", 99.0).detail["verdict"]
        == "implausible"
    )
    assert (
        witnesses.price_plausibility("09.9.9.9", "sg", "per_kg", 3.0).detail["verdict"]
        == "unknown"
    )


# --------------------------------------------------------------------------- #
# queue ranking
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_queue_ranks_cross_division_and_obs_higher(tmp_path, policy):
    conflicts = pd.DataFrame(
        {
            "canonical_key": ["cross div", "same div"],
            "witness_votes": [
                '[{"w":"model","label":"01.1.1.1","kind":"leaf","strength":0.7},'
                ' {"w":"knn","label":"05.6.1.1","kind":"leaf","strength":0.7}]',
                '[{"w":"model","label":"01.1.1.1","kind":"leaf","strength":0.7},'
                ' {"w":"knn","label":"01.1.1.9","kind":"leaf","strength":0.7}]',
            ],
            "reason": ["witness-disagreement", "witness-disagreement"],
        }
    )
    corpus = pd.DataFrame(
        {"first_name": ["cross div", "same div"], "n_observations": [10, 10]}
    )
    q = queue.build_queue(conflicts, corpus, "first_name", path=tmp_path / "q.parquet")
    assert list(q["canonical_key"]) == [
        "cross div",
        "same div",
    ]  # cross-division ranks first
    assert q.iloc[0]["leaf_gap"] == 2 and q.iloc[1]["leaf_gap"] == 1


@pytest.mark.unit
def test_result_frame_split(policy):
    rows = [
        (
            "k1",
            gate.decide(
                [Vote("model", "01.1.1.1", "leaf", 0.97, {})], "latin_other", policy
            ),
        ),
        (
            "k2",
            gate.decide(
                [
                    Vote("model", "01.1.1.1", "leaf", 0.7, {}),
                    Vote("knn", "02.1.1.1", "leaf", 0.7, {}),
                ],
                "latin_other",
                policy,
            ),
        ),
    ]
    acc, con = gate.result_frame(rows)
    assert list(acc["canonical_key"]) == ["k1"] and acc.iloc[0]["decision"] == "leaf"
    assert list(con["canonical_key"]) == ["k2"]
