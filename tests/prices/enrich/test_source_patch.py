"""Source layer (regex_patterns/source/<source>/patch.py): the two seams a
source-local fix depends on.

1. Composition: a patch edits only its own source's buckets -- removal drops,
   replacement keeps precedence, addition goes first -- and a source without a
   patch sees exactly the shared buckets.
2. Freshness: a patch edit moves that source's hash and not the global code
   fingerprint, so it cannot restale the other 48M rows.
"""

from __future__ import annotations

import dataclasses
import re

import pytest

from prices.enrich.regex_patterns import dict_view as dv
from prices.enrich.regex_patterns._registry import _INDEX
from prices.enrich.regex_patterns.types import Intent, SourcePatch
from prices.enrich.stages import extraction

pytestmark = pytest.mark.unit

_I = Intent(why="t", expect="item -> count", rows=1, examples=("x",))


def _ids(kind, patch):
    return [p.id for p in dv._apply(kind, patch)]


def test_a_source_without_a_patch_sees_the_shared_buckets():
    ps = dv.pattern_set("no_such_source_anywhere")
    _, eu, ec, mp, _, _, pbm = dv.regex_units_for_extract()
    assert ps.pack == dv.pack_patterns_for_normalize()
    assert (ps.extra_units, ps.extra_count, ps.multi_pack, ps.pricing_basis_markers) == (
        eu, ec, mp, pbm,
    )
    assert ps.flags == frozenset()


def test_patch_ops_apply_to_their_bucket_only():
    shared = [p.id for p in dv._shared_patterns("extra_count")]
    removed, replaced = shared[0], shared[2]
    new = dataclasses.replace(_INDEX[shared[1]][0], id="SRC_TEST_ADD")
    repl = dataclasses.replace(_INDEX[replaced][0], regex=re.compile(r"zzz(?P<count>\d+)"))
    patch = SourcePatch(
        additions=(new,),
        removals=(removed,),
        replacements=(repl,),
        intent={"SRC_TEST_ADD": _I, removed: _I, replaced: _I},
    )
    dv._validate("t", patch)
    got = _ids("extra_count", patch)
    assert got[0] == "SRC_TEST_ADD"  # additions win: first-match-wins buckets
    assert removed not in got
    assert got[1:] == [i for i in shared if i != removed]  # precedence kept
    assert dv._apply("extra_count", patch)[got.index(replaced)] is repl
    for kind in ("canon", "extra_unit", "multi_pack", "pricing_basis_marker"):
        assert _ids(kind, patch) == [p.id for p in dv._shared_patterns(kind)]


def test_every_patch_entry_needs_its_intent():
    with pytest.raises(RuntimeError, match="intent missing"):
        dv._validate("t", SourcePatch(flags=frozenset({"piece_is_case"})))


def test_a_patch_edit_moves_only_its_own_source(tmp_path, monkeypatch):
    rp = tmp_path / "regex_patterns"
    (rp / "source" / "tiki").mkdir(parents=True)
    (rp / "shared.py").write_text("A = 1\n")
    (rp / "source" / "__init__.py").write_text("")
    patch = rp / "source" / "tiki" / "patch.py"
    patch.write_text("PATCH = 1\n")
    monkeypatch.setattr(extraction, "_ENRICH_DIR", tmp_path)
    monkeypatch.setattr(extraction, "_SOURCE_PATCH_DIR", rp / "source")

    fp, hashes = extraction.code_fingerprint(), extraction.source_patch_hashes()
    patch.write_text("PATCH = 2\n")
    assert extraction.code_fingerprint() == fp
    assert extraction.source_patch_hashes()["tiki"] != hashes["tiki"]

    (rp / "shared.py").write_text("A = 2\n")
    assert extraction.code_fingerprint() != fp
