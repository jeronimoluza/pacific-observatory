"""Admit policy headlines written in a language the ASCII gate cannot read.

:mod:`policy_discovery` tokenises with ``[a-z][a-z0-9-]{2,}``. Thai, Chinese,
Japanese, Korean, Khmer, Lao and Burmese yield no tokens at all under it, and
Vietnamese fragments because a diacritic ends a run mid-word. Those articles were
never scored badly; they were invisible. They are 37% of the EAP corpus.

Nothing here re-derives vocabulary. The EPU pipeline already ships an audited
keyword pack per language and an Aho-Corasick matcher that substring-matches the
non-space-delimited scripts and boundary-matches the rest, so this module wires
the existing gate shape onto the existing packs.

The shape is the same as the English gate: a headline must name the *subject*
(fuel, food, prices) and then either an *instrument* or a *government actor*.
What differs is the last leg. English gates on hand-authored movement verbs
("capped", "scrapped", "slashed"), and no equivalent list exists in the packs;
the instrument groups carry that weight instead, which is why the actor path
here is the weaker of the two and is scored below the instrument path.

Scores from this gate are NOT comparable to the English gate's: that one sums
corpus IDF, this one counts matched groups. Candidates record which gate admitted
them so the two can be thresholded and measured apart.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import ahocorasick

from text.analysis.annotate import (
    KeywordBundle,
    _match_all_categories,
    build_combined_automaton,
)
from text.analysis.utils import (
    LANGUAGE_ALIASES,
    NON_SPACE_DELIMITED,
    _is_word_boundary,
)

# Instrument nouns and movement verbs per language. Deliberately outside
# ``keywords/``: that tree is hashed into the EPU build cache, so adding a theme
# there would force a full recompute for every language in every region.
ACTION_DIR = Path(__file__).resolve().parent / "policy_action_terms"

# Corpus language cells are not clean: South Korea carries both "ko" and
# "korean", Australia has "[en]", Vietnam has a large empty-string block.
EXTRA_ALIASES = {
    "": "unknown",
    "?": "unknown",
    "[en]": "en",
    "eng": "en",
    "english": "en",
}

# Subject. A headline must carry one of these or it is not about fuel or food,
# whatever else it says.
TOPIC_FUEL = {
    "energy",
    "oil",
    "gasoline",
    "diesel",
    "natural_gas",
    "fuel_rationing",
}
TOPIC_FOOD = {
    "food_security",
    "food_prices",
    "food_shortage_rationing",
    "hunger_malnutrition",
    "drought_water",
    "extreme_weather_disaster",
    "agricultural_inputs",
    "crop_livestock_shocks",
    "staple_crops",
    "fisheries",
    "food_trade_supply",
    "food_assistance",
    "food_reserves",
}
# Cost-of-living framing sits in both trackers' scope and is how a great many
# fuel and food measures are actually reported.
TOPIC_SHARED = {"inflation_prices"}
TOPIC_GROUPS = TOPIC_FUEL | TOPIC_FOOD | TOPIC_SHARED

# Instrument. These groups are lists of things a state does -- export bans,
# import permits, buffer stocks, reserve releases, vouchers, rationing -- rather
# than things that merely happen, which is what makes them the strong path.
INSTRUMENT_GROUPS = {
    "food_trade_supply",
    "food_reserves",
    "food_assistance",
    "fuel_rationing",
    "fiscal_policy",
    "monetary_policy",
    "trade",
}

ACTOR_GROUPS = {
    "government",
    "parliament",
    "finance_ministry",
    "central_bank",
    "state_owned_enterprises",
    "courts_judiciary",
    "agriculture_ministry",
    "food_agency",
    "disaster_meteo_agency",
}

# Topic group -> v6 Category, for the candidate's category_hint. The extraction
# pass overrides this from the article text; it only has to be close enough to
# stratify a sample.
TOPIC_CATEGORY = {
    "energy": "energy",
    "oil": "energy",
    "gasoline": "energy",
    "diesel": "energy",
    "natural_gas": "energy",
    "fuel_rationing": "energy",
    "food_prices": "agriculture",
    "staple_crops": "agriculture",
    "agricultural_inputs": "agriculture",
    "crop_livestock_shocks": "agriculture",
    "fisheries": "agriculture",
    "food_reserves": "agriculture",
    "food_trade_supply": "regulatory and trade facilitation reforms",
    "trade": "regulatory and trade facilitation reforms",
    "food_assistance": "social protection",
    "hunger_malnutrition": "social protection",
    "food_shortage_rationing": "social protection",
    "extreme_weather_disaster": "regulatory and trade facilitation reforms",
    "drought_water": "agriculture",
    "food_security": "agriculture",
    "inflation_prices": "fiscal measures",
    "fiscal_policy": "fiscal measures",
    "monetary_policy": "fiscal measures",
}


def normalize_language(raw: Any) -> str:
    """Map a corpus ``language`` cell onto a keyword-pack directory name."""
    text = str(raw or "").strip().lower()
    text = EXTRA_ALIASES.get(text, text)
    return LANGUAGE_ALIASES.get(text, text)


@lru_cache(maxsize=64)
def gate_for(language: str):
    """The combined automaton for one language, or None if it has no pack.

    ``KeywordBundle.for_language`` already falls back to English per theme, so a
    language with a partial pack still gates on what it has.
    """
    try:
        bundle = KeywordBundle.for_language(language)
    except Exception:
        return None
    if not bundle.topics and not bundle.actors:
        return None
    return build_combined_automaton(bundle)


@lru_cache(maxsize=64)
def action_gate_for(language: str):
    """Automaton over the translated instrument and movement terms, if any.

    Returns ``None`` when the language has no file, in which case :func:`admit`
    falls back to gating on a government actor alone. That is looser and noisier;
    the file is what buys the English gate's precision in another language.
    """
    path = ACTION_DIR / f"{language}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    automaton = ahocorasick.Automaton()
    by_word: Dict[str, set] = {}
    for kind in ("instrument", "movement"):
        for term in data.get(kind, []):
            if isinstance(term, str) and term.strip():
                by_word.setdefault(term.strip().lower(), set()).add(kind)
    if not by_word:
        return None
    for word, kinds in by_word.items():
        automaton.add_word(word, (tuple(sorted(kinds)), word))
    automaton.make_automaton()
    return automaton, language not in NON_SPACE_DELIMITED


def _action_hits(text: str, gate) -> Dict[str, int]:
    """Count instrument and movement matches, honouring the language's boundaries."""
    found = {"instrument": 0, "movement": 0}
    if not text or gate is None:
        return found
    automaton, check_boundaries = gate
    for end_idx, (kinds, term) in automaton.iter(text):
        start = end_idx - len(term) + 1
        if check_boundaries and not _is_word_boundary(text, start, end_idx + 1):
            continue
        for kind in kinds:
            found[kind] += 1
    return found


def _hits(counts: Dict[str, int], prefix: str, wanted: set) -> List[str]:
    return sorted(
        key.split(":", 1)[1]
        for key, n in counts.items()
        if n > 0 and key.startswith(prefix) and key.split(":", 1)[1] in wanted
    )


def admit(
    title: str,
    body: str,
    language: str,
    min_score: float = 3.0,
) -> Optional[Dict[str, Any]]:
    """Decide whether one headline reads like a government acting on fuel or food.

    Admission reads the headline only, for the same reason the English gate does:
    an instrument word in a body says the article mentions governing, not that it
    reports a measure. The body only moves the score, which ranks what a reader
    sees first.
    """
    combo = gate_for(language)
    if combo is None or not title:
        return None

    title_low = title.lower()
    head = _match_all_categories(title_low, combo)
    topic = _hits(head, "topic:", TOPIC_GROUPS)
    if not topic:
        return None
    instrument = _hits(head, "topic:", INSTRUMENT_GROUPS)
    actor = _hits(head, "actor:", ACTOR_GROUPS)

    action_gate = action_gate_for(language)
    act = _action_hits(title_low, action_gate)
    strong = bool(instrument) or act["instrument"] > 0

    if action_gate is not None:
        # With translated verbs available the gate is the English one's shape:
        # an instrument named outright, or an actor moving something.
        if not strong and not (actor and act["movement"]):
            return None
    elif not instrument and not actor:
        # No translated verbs for this language. Gating on the actor alone is
        # looser and admits more noise, which the extraction pass has to absorb.
        return None

    body_counts = _match_all_categories((body or "").lower()[:4000], combo)
    body_topic = [
        t for t in _hits(body_counts, "topic:", TOPIC_GROUPS) if t not in topic
    ]

    score = (
        2.0 * len(topic)
        + 3.0 * len(instrument)
        + 2.0 * min(act["instrument"], 3)
        + 1.0 * len(actor)
        + 0.5 * min(act["movement"], 3)
        + 0.25 * len(body_topic)
    )
    if score < min_score:
        return None

    fuel = len(set(topic) & TOPIC_FUEL)
    food = len(set(topic) & TOPIC_FOOD)
    tracker = "both" if fuel and food else ("fuel" if fuel else "food")
    hint = TOPIC_CATEGORY.get(topic[0], "agriculture")
    for group in topic:
        if group in INSTRUMENT_GROUPS and group in TOPIC_CATEGORY:
            hint = TOPIC_CATEGORY[group]
            break

    return {
        "gate": "lang",
        "language": language,
        "category_hint": hint,
        "tracker_hint": tracker,
        "title_topic": topic,
        "title_instrument": instrument,
        "title_actor": actor,
        "n_action_instrument": act["instrument"],
        "n_action_movement": act["movement"],
        "has_action_pack": action_gate is not None,
        "admitted_by": "instrument" if strong else "actor",
        "body_topic": body_topic[:20],
        "score": round(score, 2),
    }


def summarize_languages(counts: Dict[str, int]) -> List[Tuple[str, int, bool]]:
    """Report which corpus languages resolve to a usable pack, and which do not."""
    out = []
    for raw, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        lang = normalize_language(raw)
        out.append((lang, n, gate_for(lang) is not None))
    return out
