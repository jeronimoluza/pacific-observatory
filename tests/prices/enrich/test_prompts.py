import json
import re

import pytest

from prices.enrich import config
from prices.enrich.stages.enrich import _load_coicop_context


def test_enrich_prompt_has_no_unfilled_placeholders():
    template = config.ENRICH_PROMPT_PATH.read_text()
    rendered = template.replace("{coicop_context}", _load_coicop_context())
    leftover = re.findall(r"\{[a-zA-Z_]\w*\}", rendered)
    assert not leftover, f"Unfilled placeholders: {leftover}"


def test_taxonomy_prompt_has_no_placeholders():
    # The taxonomy prompt has no Python-side template vars — the JSON payload is
    # the user message, not a substituted block. So no `{...}` shapes should leak.
    rendered = config.TAXONOMY_PROMPT_PATH.read_text()
    leftover = re.findall(r"\{[a-zA-Z_]\w*\}", rendered)
    assert not leftover, f"Unfilled placeholders: {leftover}"


def test_coicop_context_lists_all_deepest_available_leaves():
    ctx = _load_coicop_context()
    # A representative depth-5 leaf must appear (sourced from XLSX, no AI needed)
    assert "01.1.1.1.2" in ctx, "expected depth-5 'Rice' leaf in context"
    # The XLSX has 538 deepest-available leaves (269 at depth-4 + 269 at depth-5);
    # every one is a top-level (non-indented) line of the form 'NN.N.N.N(.N)? | ...'.
    leaf_lines = [
        line for line in ctx.splitlines() if re.match(r"^\d{2}(?:\.\d){3,4} \|", line)
    ]
    assert (
        len(leaf_lines) == 538
    ), f"expected 538 deepest-available leaves, got {len(leaf_lines)}"


def test_coicop_context_includes_sub_vocab_when_json_exists():
    # When the taxonomy JSON has been generated (post-Task-3.2 run), every leaf
    # in it should appear in the rendered context with its entries indented.
    if not config.COICOP_SUBCATS_JSON.exists():
        pytest.skip("coicop_subcategories.json not yet generated (run taxonomy stage)")
    subcats = json.loads(config.COICOP_SUBCATS_JSON.read_text())
    ctx = _load_coicop_context()
    for code in list(subcats.keys())[:5]:
        assert code in ctx
