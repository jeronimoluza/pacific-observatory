"""Parse + validate a judgment agent's verdicts JSON into gazetteer rows.

A Sonnet agent reads one run folder's review.csv (the doubtful bucket) and emits
judgment-only verdicts — it never re-runs the cascade. The document shape is:

  {"item": "pineapple",
   "verdicts": [{"token": "sunnyphil", "role": "variety"},
                {"token": "juice", "role": "form", "leaf": "01.2.1.1.1"},
                {"token": "shampoo", "role": "nonfood"}]}

parse_verdicts validates that document against the target base_item and returns
the {token: (role, provenance)} map store.append_gazetteer wants, encoding a
form verdict's leaf as the "form:<leaf>" role that store.load_record decodes.
"""

from __future__ import annotations

# Roles the gazetteer flywheel (store.load_record) understands. "form" is the
# only one that carries a leaf; the rest are bare role overrides.
_ROLES = {"variety", "cultivar_quality", "nonfood", "species_veto", "form"}


def parse_verdicts(payload: dict, item: str) -> dict[str, tuple[str, str]]:
    """Validate the verdicts document and return {token: (role, provenance)}.

    Raises ValueError on any schema violation (the CLI turns it into a
    ClickException). form verdicts require a leaf and become "form:<leaf>".
    """
    if not isinstance(payload, dict):
        raise ValueError("verdicts payload must be a JSON object")
    doc_item = payload.get("item")
    if doc_item != item:
        raise ValueError(
            f"verdicts item '{doc_item}' does not match target base_item '{item}'"
        )
    verdicts = payload.get("verdicts")
    if not isinstance(verdicts, list) or not verdicts:
        raise ValueError("'verdicts' must be a non-empty list")

    out: dict[str, tuple[str, str]] = {}
    for i, v in enumerate(verdicts):
        if not isinstance(v, dict):
            raise ValueError(f"verdict #{i} must be an object")
        token = str(v.get("token", "")).strip().lower()
        role = str(v.get("role", "")).strip()
        if not token:
            raise ValueError(f"verdict #{i} missing 'token'")
        if role not in _ROLES:
            raise ValueError(f"verdict #{i} role '{role}' not in {sorted(_ROLES)}")
        if role == "form":
            leaf = str(v.get("leaf", "")).strip()
            if not leaf:
                raise ValueError(
                    f"verdict #{i} ('{token}') form role requires a 'leaf'"
                )
            role = f"form:{leaf}"
        prov = str(v.get("provenance") or "apply-verdicts")
        out[token] = (role, prov)
    return out
