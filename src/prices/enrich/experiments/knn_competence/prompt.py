"""Shared grounded-choice prompt — identical across every panel model.

The model chooses exactly one COICOP leaf from the KNN candidate set, each
presented with its official inclusion note. Choosing off-list is structurally
disallowed (and flagged downstream), so no model can invent a code.
"""

from __future__ import annotations

INSTRUCTIONS = (
    "You classify a grocery/retail product to ONE COICOP-2018 division-01 leaf.\n"
    "You are given a shortlist of candidate leaves (retrieved as the product's "
    "nearest neighbours), each with its official COICOP inclusion note.\n"
    "Choose the single best-fitting leaf CODE from the shortlist — you must pick "
    "one of the listed codes, never invent one. Judge strictly by the official "
    "notes (watch conventions: surimi/crab-stick=fish-prep not crustacean; "
    "yogurt=milk-product not soft-drink; RTD/flavoured milk=milk-beverage; "
    "juice=soft-drink not fresh fruit; non-dairy creamer=other-food not dairy).\n"
    "Return the chosen code, a confidence in [0,1], and a one-line reason."
)


def build_prompt(name: str, candidate_notes: list[str]) -> str:
    lines = [INSTRUCTIONS, "", f"PRODUCT: {name}", "", "CANDIDATES:"]
    for i, note in enumerate(candidate_notes, 1):
        lines.append(f"  {i}. {note}")
    return "\n".join(lines)
