"""Persistent stores for the base-item cascade + record assembly.

Three parquets under data/prices/:
  base_items.parquet       xlsx-derived candidate base_items / varieties / forms
                           / vetos (taxonomy.py). Columns:
                           base_item, base_name, language, role, coicop_code,
                           coicop2digit_title, allowed_basis, form_leaf,
                           provenance, created_at.
  gazetteer.parquet        mined + oracle-learned (base_item, token) -> role
                           overrides (the flywheel). Columns:
                           base_item, token, role, provenance, first_seen, n.
  source_boilerplate.parquet   per-source mined boilerplate. Columns:
                           source, language, text.

Plus two shared xlsx-derived lexicons (data/prices/):
  derived_form_lexicon.parquet  term -> leaf_code (processed edible forms)
  derived_neg_lexicon.parquet   term -> source_code (health/household/care)

load_record() merges base_items + gazetteer into the rec dict the cascade wants.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from prices.enrich.config import REPO_ROOT

from .static import ORIGIN, QUALITY

# Override the store root for tests / dry runs (avoids writing into the user's
# data/ during development). Production leaves it unset -> data/prices/.
DATA = Path(os.environ.get("BASE_ITEMS_DATA_DIR") or (REPO_ROOT / "data" / "prices"))
BASE_ITEMS_PARQUET = DATA / "base_items.parquet"
GAZETTEER_PARQUET = DATA / "gazetteer.parquet"
SOURCE_BOILERPLATE_PARQUET = DATA / "source_boilerplate.parquet"
FORM_LEXICON_PARQUET = DATA / "derived_form_lexicon.parquet"
NEG_LEXICON_PARQUET = DATA / "derived_neg_lexicon.parquet"


def set_data_dir(path) -> None:
    """Repoint every store parquet at `path` (tests / dry runs)."""
    global DATA, BASE_ITEMS_PARQUET, GAZETTEER_PARQUET
    global SOURCE_BOILERPLATE_PARQUET, FORM_LEXICON_PARQUET, NEG_LEXICON_PARQUET
    DATA = Path(path)
    BASE_ITEMS_PARQUET = DATA / "base_items.parquet"
    GAZETTEER_PARQUET = DATA / "gazetteer.parquet"
    SOURCE_BOILERPLATE_PARQUET = DATA / "source_boilerplate.parquet"
    FORM_LEXICON_PARQUET = DATA / "derived_form_lexicon.parquet"
    NEG_LEXICON_PARQUET = DATA / "derived_neg_lexicon.parquet"


BASE_ITEM_COLS = [
    "base_item",
    "base_name",
    "language",
    "role",
    "coicop_code",
    "coicop2digit_title",
    "allowed_basis",
    "plausible_basis",
    "form_leaf",
    "provenance",
    "created_at",
]
GAZETTEER_COLS = ["base_item", "token", "role", "provenance", "first_seen", "n"]
BOILERPLATE_COLS = ["source", "language", "text"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- base_items ----------------------------------------------------------------
def load_base_items() -> pd.DataFrame:
    if BASE_ITEMS_PARQUET.exists():
        return pd.read_parquet(BASE_ITEMS_PARQUET)
    return pd.DataFrame(columns=BASE_ITEM_COLS)


def write_base_items(df: pd.DataFrame) -> None:
    BASE_ITEMS_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df[BASE_ITEM_COLS].to_parquet(BASE_ITEMS_PARQUET, index=False)


def upsert_base_items(rows: pd.DataFrame) -> pd.DataFrame:
    """Add rows (dedup on base_item+base_name+role), keeping existing on clash."""
    cur = load_base_items()
    both = pd.concat([cur, rows], ignore_index=True)
    both = both.drop_duplicates(subset=["base_item", "base_name", "role"], keep="first")
    write_base_items(both)
    return both


# --- gazetteer -----------------------------------------------------------------
def load_gazetteer() -> pd.DataFrame:
    if GAZETTEER_PARQUET.exists():
        return pd.read_parquet(GAZETTEER_PARQUET)
    return pd.DataFrame(columns=GAZETTEER_COLS)


def append_gazetteer(base_item: str, verdicts: dict[str, tuple[str, str]]) -> None:
    """verdicts: {token: (role, provenance)}. Increments n on repeats."""
    cur = load_gazetteer()
    seen = {(r.base_item, r.token): r for r in cur.itertuples()}
    rows = []
    for token, (role, prov) in verdicts.items():
        key = (base_item, token)
        if key in seen:
            continue
        rows.append(
            {
                "base_item": base_item,
                "token": token,
                "role": role,
                "provenance": prov,
                "first_seen": _now(),
                "n": 1,
            }
        )
    if rows:
        out = pd.concat([cur, pd.DataFrame(rows)], ignore_index=True)
        GAZETTEER_PARQUET.parent.mkdir(parents=True, exist_ok=True)
        out[GAZETTEER_COLS].to_parquet(GAZETTEER_PARQUET, index=False)


# --- source boilerplate --------------------------------------------------------
def write_source_boilerplate(df: pd.DataFrame) -> None:
    SOURCE_BOILERPLATE_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df[BOILERPLATE_COLS].to_parquet(SOURCE_BOILERPLATE_PARQUET, index=False)


def load_boilerplate(sources: set[str] | None = None) -> set[str]:
    """Union of mined boilerplate tokens, optionally scoped to given sources."""
    if not SOURCE_BOILERPLATE_PARQUET.exists():
        return set()
    df = pd.read_parquet(SOURCE_BOILERPLATE_PARQUET)
    if sources is not None:
        df = df[df["source"].isin(sources)]
    return set(df["text"].astype(str))


# --- shared derived lexicons ---------------------------------------------------
def load_form_lexicon() -> dict[str, str]:
    if not FORM_LEXICON_PARQUET.exists():
        return {}
    d = pd.read_parquet(FORM_LEXICON_PARQUET)
    return dict(zip(d["term"], d["leaf_code"]))


def load_neg_lexicon() -> dict[str, str]:
    if not NEG_LEXICON_PARQUET.exists():
        return {}
    d = pd.read_parquet(NEG_LEXICON_PARQUET)
    return dict(zip(d["term"], d["source_code"]))


# --- record assembly -----------------------------------------------------------
def _parse_basis(cell) -> set | None:
    if cell is None or (isinstance(cell, float) and pd.isna(cell)) or cell == "":
        return None
    parts = {p.strip() or None for p in str(cell).split(",")}
    return {None if p in (None, "none") else p for p in parts}


def load_record(base_item: str) -> dict:
    """Assemble the cascade rec for one base_item from base_items + gazetteer."""
    bi = load_base_items()
    rows = bi[bi["base_item"] == base_item]
    if rows.empty:
        raise KeyError(f"base_item '{base_item}' not in base_items.parquet")

    alias = rows[rows["role"] == "alias"]
    tokens = set(alias["base_name"].astype(str).str.lower())
    default_leaf = str(alias["coicop_code"].iloc[0])
    coicop2digit_title = str(alias["coicop2digit_title"].iloc[0])
    allowed_basis = _parse_basis(alias["allowed_basis"].iloc[0])
    plausible_basis = (
        _parse_basis(alias["plausible_basis"].iloc[0])
        if "plausible_basis" in alias.columns
        else None
    )

    variety = set(rows[rows["role"] == "variety"]["base_name"].astype(str).str.lower())
    nonfood = set(rows[rows["role"] == "nonfood"]["base_name"].astype(str).str.lower())
    species = set(
        rows[rows["role"] == "species_veto"]["base_name"].astype(str).str.lower()
    )
    form = {
        str(r.base_name).lower(): str(r.form_leaf)
        for r in rows[rows["role"] == "form"].itertuples()
    }

    # flywheel: merge gazetteer (base_item, token) -> role overrides
    gaz = load_gazetteer()
    gaz = gaz[gaz["base_item"] == base_item]
    for r in gaz.itertuples():
        tok, role = str(r.token).lower(), str(r.role)
        if role in ("variety", "cultivar_quality"):
            variety.add(tok)
        elif role == "nonfood":
            nonfood.add(tok)
        elif role == "species_veto":
            species.add(tok)
        elif role.startswith("form"):
            leaf = role.split(":", 1)[1] if ":" in role else ""
            form[tok] = leaf

    return {
        "name": base_item,
        "tokens": tokens,
        "fresh_leaf": default_leaf,
        "fresh_prefix": default_leaf[:7],
        "variety": variety,
        "benign": variety | QUALITY | ORIGIN,
        "form": form,
        "nonfood": nonfood,
        "species_veto": species,
        "allowed_basis": allowed_basis,
        "plausible_basis": plausible_basis,
        "coicop2digit_title": coicop2digit_title,
    }
