"""w_cascade — the deterministic base-item cascade as a batch witness.

Faithful reuse of ``base_items.cascade.classify_names``: for each registered
base_item we grep the provided corpus by its aliases and run the same cascade
the base-item pipeline runs, then map the verdict to a Vote. CANDIDATE binds to
the base_item's default (fresh) leaf; EXCLUDE / OTHER_FORM are reject votes;
REVIEW abstains. The whole witness abstains (returns ``{}``) when spaCy, the
en_core_web_sm model, or the base_items registry is unavailable — this is the
heavy witness, deliberately best-effort so `make ci` never needs the model.
"""

from __future__ import annotations

import re

import pandas as pd

from prices.enrich.consensus.witnesses import Vote
from prices.enrich.keys import norm_key


def _bucket_to_vote(bucket: str, reason: str, rec: dict) -> Vote | None:
    detail = {"reason": reason, "base_item": rec.get("name")}
    if bucket == "CANDIDATE":
        return Vote("cascade", str(rec["fresh_leaf"]), "leaf", 0.9, detail)
    if bucket == "EXCLUDE":
        return Vote("cascade", "__EXCLUDE__", "reject", 0.8, detail)
    if bucket == "OTHER_FORM":
        return Vote("cascade", "__OTHER_FORM__", "reject", 0.8, detail)
    return None  # REVIEW -> abstain


def cascade_votes(
    corpus: pd.DataFrame, name_col: str, lang_col: str | None = None
) -> dict[str, Vote]:
    try:
        import spacy

        from prices.enrich.base_items import store
        from prices.enrich.base_items.cascade import classify_names
        from prices.enrich.base_items.phrase_index import food_phrase_index
    except Exception:
        return {}

    try:
        registry = store.load_base_items()
    except Exception:
        return {}
    if registry.empty:
        return {}
    try:
        nlp = spacy.load("en_core_web_sm", disable=["ner"])
    except Exception:
        return {}

    sub_idx = food_phrase_index()
    form_lex, neg_lex = store.load_form_lexicon(), store.load_neg_lexicon()
    boiler: set = set()  # per-source mining skipped for the witness pass

    names = corpus[name_col].astype(str)
    has_lang = bool(lang_col) and lang_col in corpus.columns
    out: dict[str, Vote] = {}

    for base_item in sorted(set(registry["base_item"].astype(str))):
        try:
            rec = store.load_record(base_item)
        except Exception:
            continue
        aliases = sorted(
            {str(t) for t in rec["tokens"] if str(t)}, key=len, reverse=True
        )
        if not aliases:
            continue
        pat = re.compile(
            r"\b(?:" + "|".join(re.escape(a) for a in aliases) + r")\b", re.I
        )
        mask = names.str.contains(pat)
        if not mask.any():
            continue
        sl = corpus[mask]
        sl_names = sl[name_col].astype(str).tolist()
        sl_langs = sl[lang_col].tolist() if has_lang else [None] * len(sl_names)
        try:
            got = classify_names(
                sl_names, sl_langs, rec, nlp, boiler, sub_idx, form_lex, neg_lex
            )
        except Exception:
            continue
        for nm, triple in zip(sl_names, got):
            vote = _bucket_to_vote(triple[0], triple[1], rec)
            if vote is not None:
                # keep-first: earliest base_item to bind a name wins (REVIEW
                # abstains leave the name open for a later item's CANDIDATE).
                out.setdefault(norm_key(nm), vote)
    return out
