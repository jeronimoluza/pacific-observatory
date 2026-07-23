import pandas as pd
import pytest

from prices.enrich import config
from prices.enrich.audit import load_denylist
from prices.enrich.cross_check import lookup_allowed_bases

pytestmark = pytest.mark.unit


def test_authoring_invariant_action_matches_semantic_and_evidence():
    df = pd.read_parquet(config.BASIS_DENYLIST_PARQUET)
    failures = []
    for row in df.itertuples(index=False):
        should_reject = row.semantic == "HIGH" and row.evidence_state == "CONFIRMED"
        expected_action = "reject" if should_reject else "flag"
        if row.action != expected_action:
            failures.append(
                f"{row.code}: action={row.action!r}, semantic={row.semantic!r}, "
                f"evidence_state={row.evidence_state!r} (expected action={expected_action!r})"
            )
    assert not failures, "authoring invariant violated:\n" + "\n".join(failures)


def test_denylist_disjoint_from_taxonomy_allowed_bases():
    denylist = load_denylist(config.BASIS_DENYLIST_PARQUET)
    failures = []
    for leaf, entry in denylist.items():
        allowed, _level = lookup_allowed_bases(leaf, None)
        if allowed is None:
            continue
        overlap = entry["excluded"] & allowed
        if overlap:
            failures.append(
                f"{leaf}: excluded={overlap} also in taxonomy allowed_bases={allowed}"
            )
    assert not failures, "concept-duplication guard violated:\n" + "\n".join(failures)
