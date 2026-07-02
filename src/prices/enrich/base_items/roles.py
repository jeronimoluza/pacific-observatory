"""Tier-0 gazetteer roles — assign each decisive token a role, once, per entity.

Faithful port of decisive_tokens / role_of from tier0_gazetteer_replay.py. The
unit of memoization is the ROLE of a token given the entity ("granny"->cultivar
for apple), not the whole string, which is why the oracle spend converges
Zipfian. Roles: nonfood, form_mover:<leaf>, cultivar_quality, unknown.
"""

from __future__ import annotations

from .phrase_index import sub_ngram
from .static import CONTAM, DIGIT, HEAD_POS, LEAK, MOD_CHILD_DEPS, MOD_DEPS


def decisive_tokens(doc, tokens, boiler):
    """Return (mode, [(lemma, pos, dep, parent_lemma), ...]).

    mode 'head'    -> base_item is the product head; tokens are its modifiers.
    mode 'modhead' -> base_item modifies another noun; token is that head noun.
    mode 'bare'    -> base_item head with no usable modifiers.
    """
    fts = [t for t in doc if t.lower_ in tokens]
    if not fts:
        return "none", []
    t = fts[0]
    h = t.head
    # base_item-is-modifier: "apple JUICE", "green apple GUMMIES"
    if (
        h is not t
        and h.pos_ in HEAD_POS
        and h.lower_ not in tokens
        and t.dep_ in MOD_DEPS
        and h.lower_ not in boiler
    ):
        return "modhead", [(h.lemma_.lower(), h.pos_, t.dep_, t.lower_)]
    # base_item-is-head: collect its modifier children
    mods = []
    for c in t.children:
        if (
            c.dep_ in MOD_CHILD_DEPS
            and c.pos_ in {"ADJ", "PROPN", "NOUN"}
            and c.is_alpha
            and len(c) >= 3
            and c.lower_ not in tokens
            and c.lower_ not in boiler
            and not DIGIT.search(c.text)
        ):
            mods.append((c.lemma_.lower(), c.pos_, c.dep_, t.lower_))
    return ("head" if mods else "bare"), mods


def role_of(lemma, pos, mode, name, sub_idx, fresh_prefix):
    """(role, provenance) for one decisive token. No per-row LLM."""
    low = lemma.lower()
    if LEAK.search(low):
        return "nonfood", "LEAK"
    hit = sub_ngram(f"{lemma}", sub_idx)
    if hit and not str(hit[2]).startswith(fresh_prefix):
        return f"form_mover:{hit[2]}", f"sub_ngram:{hit[0]}"
    if CONTAM.search(low):
        return "form_mover:contam", "xlsx-contam"
    if mode == "modhead":
        # the product's head noun is not the base_item and attests to nothing
        # green: one oracle verdict decides, then memoized forever.
        return "unknown", "oracle:head-noun"
    if pos in {"ADJ", "PROPN"}:
        return "cultivar_quality", "dep-derivation:amod/compound->base"
    return "unknown", "oracle:noun-modifier"
