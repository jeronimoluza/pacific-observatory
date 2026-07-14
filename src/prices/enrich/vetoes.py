"""Trap-word vetoes for the (embedding -> head) COICOP classifier.

A head prediction into a target food/bev leaf is REJECTED (demoted to no-decision)
when the raw product name matches that leaf's trap regex -- a processed or adjacent
form the embedding confuses for the fresh/base leaf (canned, juiced, dried,
flavoured, paste, oil, ...). Layered on a single global confidence gate, these
vetoes lift precision from ~95% to 98-99% at flat coverage on wild data.

The vocabulary is mined from WILD LLM-labeled negatives (the OTHER partition of
the deep-leaf labeling runs); gold vocabulary alone gives zero lift because it is
too narrow to contain the trap forms. Frozen from the 14-leaf (meat/fruit/veg/
juice/soda) and 15-leaf (dairy/cereals/fish/oils/coffee/tea/water) runs.
"""

from __future__ import annotations

import re

# COICOP leaf code -> trap regex matched against the lowercased raw product name.
_VETO_SRC = {
    # --- meat (fresh, chilled or frozen) ---
    "01.1.2.2.1": r"\b(jerky|caldereta|kaldereta|corned|stock|cube|instant|noodle|chips?|flavou?r|snack)\b",
    "01.1.2.2.2": r"\b(bacon|ham|floss|jerky|canned|flavou?r|luncheon|spam)\b",
    "01.1.2.2.4": r"\b(nugget|chips?|instant|noodle|stock|cube|fried|popcorn|flavou?r|karaage)\b",
    "01.1.2.5.1": r"\b(vegetarian|vegan|plant.?based|meat.?free)\b",
    # --- fruit, fresh ---
    "01.1.6.3.1": r"\b(juice|cider|sauce|pie|vinegar|dried|chips?|candy|flavou?r|jam|puree|1l|750ml|500ml)\b",
    "01.1.6.3.2": r"\b(juice|nectar|canned|dried|flavou?r|puree|century)\b",
    "01.1.6.1.7": r"\b(juice|canned|dried|flavou?r|jam|tart|bun|biscuit|cake|pieces?|slices?|syrup|a10|bum|chunk)\b",
    "01.1.6.9.4": r"\b(milk|drink|butter|oil|flour|choco|chocolate|coated)\b",
    # --- vegetables, fresh ---
    "01.1.7.9.3": r"\boil\b",
    "01.1.7.4.8": r"(flakes?|cereal|\boil\b|flour|starch|chips?|pop ?corn|syrup|canned|cream|kernels?|snacks?|tools?|\bcan\b|425|340|butter)",
    "01.1.7.4.1": r"\b(juice|cake|canned|flavou?r|soup)\b",
    "01.1.7.2.4": r"\b(ketchup|sauce|paste|passata|canned|sun.?dried|soup|ketsup|peeled)\b",
    # --- beverages ---
    "01.2.1.0.0": r"\b(candy|flavou?red water|milk)\b",
    "01.2.6.0.0": r"\b(candy|gummy|sweets?|bread|jelly|condom)\b",
    # --- cereals / oils (batch B) ---
    "01.1.1.4.0": r"\bgerber\b",
    "01.1.1.5.0": r"\bpaste\b",
    "01.1.5.1.3": r"\b(argan|moroccan)\b",
}

VETOES = {code: re.compile(pattern) for code, pattern in _VETO_SRC.items()}


def is_vetoed(leaf: str, name: str) -> bool:
    """True if predicting `leaf` for `name` hits a trap word and must be rejected."""
    rx = VETOES.get(leaf)
    return bool(rx and rx.search(str(name).lower()))
