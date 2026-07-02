"""Tier-1 deterministic cascade — whole-name scan + earn-GREEN (zero LLM).

Faithful port of ao_rice_cascade.decide (which folds tier0_gazetteer_replay +
tier1_earn_fresh_replay + tier1_derive_replay) with two production changes:

  * bucket FRESH -> GREEN, NOT_FRESH -> OTHER_FORM, EXCLUDED -> EXCLUDE
    (pure relabel; decision logic is byte-identical on apple+orange+rice).
  * the hard-coded `basis == "volume"` branch is generalized to the record's
    allowed_basis set (default {mass, count, item, None} => only volume routes),
    so a base_item priced by volume can opt in without touching this file.

Locked principles preserved: memoize role-not-string (tier-0 roles feed in),
GREEN must be EARNED via bare-item evidence, basis is NOT a positive cue, read
the WHOLE name, faithfulness/provenance (every reason string is traceable).
"""

from __future__ import annotations

import re

from .roles import decisive_tokens, role_of
from .static import (
    BOILER_BLOCK,
    CANDIDATE,
    CONTAM,
    DEFAULT_PLAUSIBLE_BASIS,
    DIGIT,
    EXCLUDE,
    LEAK,
    OTHER_FORM,
    POISON,
    REVIEW,
)


def whole_name_guard(name: str):
    low = name.lower()
    if LEAK.search(low):
        return EXCLUDE, "leak-wholename"
    if POISON.search(low):
        return OTHER_FORM, "flavour"
    if CONTAM.search(low):
        return OTHER_FORM, "contam-wholename"
    return None, None


def whole_item_scan(name: str, rec: dict):
    """Per-base_item form / species / nonfood scan on the RAW name before the
    earn-gate. The mined boiler strips frequent nouns (cracker/noodle/spoon) and
    ADJ species words (wild) never reach residual lemmas, so a residual-only
    check leaks them into GREEN. Word-boundary on the raw name catches them
    first. No-op when the base_item has empty form/nonfood/species lists."""
    words = set(re.findall(r"[a-z]+", name.lower()))
    for w in rec["nonfood"]:
        if w in words:
            return EXCLUDE, f"nonfood:{w}"
    for w in rec["species_veto"]:
        if w in words:
            return REVIEW, f"species-trap:{w}"
    for w in rec["form"]:
        if w in words:
            return OTHER_FORM, f"form:{w}->{rec['form'][w]}"
    return None, None


def only_in_parens(name: str, tokens) -> bool:
    outside = re.sub(r"\([^)]*\)", " ", name).lower()
    inside = " ".join(re.findall(r"\(([^)]*)\)", name)).lower()
    in_has = any(re.search(rf"\b{t}\b", inside) for t in tokens)
    out_has = any(re.search(rf"\b{t}\b", outside) for t in tokens)
    return in_has and not out_has


def residual_lemmas(doc, tokens, boiler, benign):
    return [
        x.lemma_.lower()
        for x in doc
        if x.pos_ in {"NOUN", "PROPN"}
        and x.lower_ not in tokens
        and (x.lower_ not in boiler or x.lower_ in BOILER_BLOCK)
        and x.is_alpha
        and len(x) > 1
        and not DIGIT.search(x.text)
        and x.lower_ not in benign
        and x.lemma_.lower() not in benign
    ]


def derived_fallback(resid, rec, form_lex, neg_lex):
    """Residual lemmas -> bucket via per-item then shared xlsx-derived lexicons,
    else REVIEW (the irreducible brand/origin residue the flywheel must learn)."""
    for lem in resid:
        if lem in rec["species_veto"]:
            return REVIEW, f"species-trap:{lem}"
    for lem in resid:
        if lem in rec["form"]:
            return OTHER_FORM, f"form:{lem}->{rec['form'][lem]}"
    for lem in resid:
        if lem in form_lex:
            return OTHER_FORM, f"form:{lem}->{form_lex[lem]}"
    for lem in resid:
        if lem in neg_lex:
            return EXCLUDE, f"neg:{lem}->{neg_lex[lem]}"
    return REVIEW, f"brand-residue:{resid[0]}"


def decide(name, doc, roles_set, rec, boiler, basis, form_lex, neg_lex):
    tokens = rec["tokens"]
    wd, wr = whole_name_guard(name)
    if wd:
        return wd, wr
    sd, sr = whole_item_scan(name, rec)
    if sd:
        return sd, sr
    if any(r == "nonfood" for r in roles_set):
        return EXCLUDE, "gaz:nonfood"
    if any(r.startswith("form_mover") for r in roles_set):
        return OTHER_FORM, "gaz:form_mover"
    plausible = rec.get("plausible_basis") or DEFAULT_PLAUSIBLE_BASIS
    if basis not in plausible:
        return OTHER_FORM, f"not-plausible:basis:{basis}"
    if "unknown" in roles_set:
        return REVIEW, "gaz:unknown"
    if only_in_parens(name, tokens):
        return REVIEW, "base-in-parens"
    resid = residual_lemmas(doc, tokens, boiler, rec["benign"])
    if not resid:
        return CANDIDATE, "earned:bare-item"
    return derived_fallback(resid, rec, form_lex, neg_lex)


def classify_names(names, langs, rec, nlp, boiler, sub_idx, form_lex, neg_lex):
    """Batch-classify a base_item's raw names. Returns list of
    (bucket, reason, pricing_basis). Cleaning + spaCy batching happen here so a
    caller only supplies the record and the shared lexicons."""
    from prices.enrich.extract import extract

    from .text_clean import clean_for_parse

    tokens = rec["tokens"]
    fresh_prefix = rec["fresh_prefix"]
    benign = rec["benign"]
    names = [str(n) for n in names]
    bases = [
        extract(item_name=n, category=None, country=None, lang=None).pricing_basis
        for n in names
    ]
    cleaned = [clean_for_parse(n, lg) for n, lg in zip(names, langs)]
    docs = list(nlp.pipe(cleaned, batch_size=256))

    out = []
    for i, name in enumerate(names):
        low = name.lower()
        mode, mods = decisive_tokens(docs[i], tokens, boiler)
        roles = ["nonfood"] if LEAK.search(low) else []
        for lemma, pos, dep, parent in mods:
            if mode == "modhead" and lemma in benign:
                continue
            roles.append(role_of(lemma, pos, mode, name, sub_idx, fresh_prefix)[0])
        bucket, reason = decide(
            name, docs[i], set(roles), rec, boiler, bases[i], form_lex, neg_lex
        )
        out.append((bucket, reason, bases[i]))
    return out
