"""COICOP taxonomy index utilities — leaf set + per-leaf sub_label_id set.

Pulled out of `stages/tier_c.py` so the LLM module stays under the 500-LoC
cap. Pure functions, lazy module-level cache. No I/O at call time after
first use.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Optional

import pandas as pd

from prices.enrich import config


_TAXONOMY_INDEX: Optional[tuple[set[str], dict[str, set[str]]]] = None
_LEAF_BLOCKS: Optional[dict[str, str]] = None


def _compact_bullets(text: object, max_items: int = 4, max_chars: int = 220) -> str:
    """Convert an xlsx bullet block (`* item\n* item\n...`) into a single-line
    `item; item; ...` string. Truncated by item-count and total chars to keep
    the prompt bounded."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    s = str(text).replace("_x000D_", "").strip()
    if not s:
        return ""
    items: list[str] = []
    for raw in s.split("\n"):
        item = raw.lstrip("*-•").strip()
        if item:
            items.append(item)
        if len(items) >= max_items:
            break
    out = "; ".join(items)
    if len(out) > max_chars:
        out = out[: max_chars - 1].rsplit(" ", 1)[0] + "…"
    return out


def _load_leaf_blocks() -> dict[str, str]:
    """Return `{coicop_code: rendered_block}` for every deepest-available leaf.
    Lazy module cache — built once from the xlsx + sub-vocab JSON.

    Per-leaf format:
        {code} | {title}
          : includes: a; b; c   (truncated)
          : excludes: x; y     (only if present)
          - sub_label_id | label | synonyms: ...
    """
    global _LEAF_BLOCKS
    if _LEAF_BLOCKS is not None:
        return _LEAF_BLOCKS
    subcats: dict[str, list[dict]] = {}
    if config.COICOP_SUBCATS_JSON.exists():
        subcats = json.loads(config.COICOP_SUBCATS_JSON.read_text())
    df = pd.read_excel(config.COICOP_XLSX)
    df = df[df["code"].notna()].copy()
    df["code"] = df["code"].astype(str)
    codes = set(df["code"])
    df = df[
        df["code"].apply(
            lambda c: not any(
                other != c and other.startswith(c + ".") for other in codes
            )
        )
    ]
    blocks: dict[str, str] = {}
    for r in df.itertuples():
        title = str(r.title).replace("_x000D_", "").strip()
        lines = [f"{r.code} | {title}"]
        includes = _compact_bullets(getattr(r, "includes", None))
        also = _compact_bullets(getattr(r, "alsoIncludes", None))
        excludes = _compact_bullets(getattr(r, "excludes", None))
        if includes:
            lines.append(f"  : includes: {includes}")
        if also:
            lines.append(f"  : also: {also}")
        if excludes:
            lines.append(f"  : excludes: {excludes}")
        for entry in subcats.get(r.code, []):
            syns = ", ".join(entry.get("synonyms", [])[:4])
            lines.append(f"  - {entry['id']} | {entry['label']} | synonyms: {syns}")
        blocks[r.code] = "\n".join(lines)
    _LEAF_BLOCKS = blocks
    return _LEAF_BLOCKS


@lru_cache(maxsize=512)
def _render_scope(scope: Optional[frozenset]) -> str:
    """Render the COICOP block for a scope set. `None` → full taxonomy.

    Cache-keyed on `frozenset(scope)` so repeat scopes are zero-cost.
    """
    blocks = _load_leaf_blocks()
    if scope is None:
        codes = sorted(blocks.keys())
    else:
        codes = sorted(c for c in scope if c in blocks)
    return "\n".join(blocks[c] for c in codes)


def load_coicop_context(scope: Optional[frozenset] = None) -> str:
    """Return the multi-line prompt block of COICOP leaves.

    `scope=None` → full 538-leaf block (legacy behavior).
    `scope=frozenset({...})` → only the named leaves, rendered in code order.

    Backed by an LRU cache (`_render_scope`) keyed on the frozenset, so the
    same scope reused across calls is free."""
    return _render_scope(scope)


_CLEAN_ANCHOR_MAX_ID_LEN = 30


def load_taxonomy_index() -> tuple[set[str], dict[str, set[str]]]:
    """Return (valid_coicop_codes, {coicop_code: {valid_sub_label_ids}}).

    `valid_coicop_codes` is the set of deepest-available xlsx leaves.
    Sub-label vocabularies are sourced from `_sub_labels.parquet`, filtered to
    curated kebab ids: `role='synonym'` (JSON-curated + harvested) plus
    `role='anchor'` rows whose id length is at most _CLEAN_ANCHOR_MAX_ID_LEN
    (catches single-concept depth-5 anchors like `rice`, drops semicolon-list
    catch-all anchors like `garden-tractors-chain-saws-...`). `_other` is
    added to every sub-vocabulary as the taxonomy-valid fallback."""
    global _TAXONOMY_INDEX
    if _TAXONOMY_INDEX is not None:
        return _TAXONOMY_INDEX
    df = pd.read_excel(config.COICOP_XLSX)
    df = df[df["code"].notna()].copy()
    df["code"] = df["code"].astype(str)
    codes = set(df["code"])
    leaves = {
        c
        for c in codes
        if not any(other != c and other.startswith(c + ".") for other in codes)
    }
    sub_parquet = (
        config.COICOP_KEYWORDS_DIR / "_sub_labels.parquet"
        if hasattr(config, "COICOP_KEYWORDS_DIR")
        else None
    )
    if sub_parquet is None or not sub_parquet.exists():
        from pathlib import Path

        sub_parquet = (
            Path(__file__).resolve().parent
            / "keywords"
            / "coicop"
            / "_sub_labels.parquet"
        )
    sub_df = pd.read_parquet(sub_parquet)
    sub_df["id_len"] = sub_df["id"].astype(str).str.len()
    clean = sub_df[
        (sub_df["role"] == "synonym")
        | (
            (sub_df["role"] == "anchor")
            & (sub_df["id_len"] <= _CLEAN_ANCHOR_MAX_ID_LEN)
        )
    ]
    sub_index: dict[str, set[str]] = {}
    for code, group in clean.groupby("coicop_code"):
        ids = set(group["id"].astype(str).unique())
        ids.add("_other")
        sub_index[str(code)] = ids
    for code in leaves:
        sub_index.setdefault(code, {"_other"})
    _TAXONOMY_INDEX = (leaves, sub_index)
    return _TAXONOMY_INDEX


def closest_codes(invalid: str, valid: set[str], n: int = 5) -> list[str]:
    """Pick up to n valid leaf codes that share the longest dotted prefix
    with `invalid`. Cheap; no edit distance required."""
    parts = invalid.split(".")
    for k in range(len(parts), 0, -1):
        prefix = ".".join(parts[:k]) + "."
        matches = sorted(c for c in valid if c.startswith(prefix))
        if matches:
            return matches[:n]
    return sorted(valid)[:n]
