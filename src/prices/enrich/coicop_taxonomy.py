"""COICOP taxonomy helpers for the gold-labeling workflow.

Pure deepest-leaf derivation plus a rendered codebook of valid COICOP leaves,
sourced from the COICOP xlsx (`config.COICOP_XLSX`). Extracted from the removed
`tier_b/taxonomy_index.py`. The retired cascade sub-vocabulary (per-leaf
`sub_label_id` sets, `COICOP_SUBCATS_JSON`) is gone, so `load_taxonomy_index`
returns an empty sub-index for backward-compatible tuple unpacking.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable, Optional

import pandas as pd

from prices.enrich import config

_LEAF_BLOCKS: Optional[dict[str, str]] = None
_LEAVES: Optional[set[str]] = None


def deepest_leaves(codes: Iterable[str]) -> set[str]:
    """The deepest-available leaves: codes with no other code extending them
    by one more dotted level."""
    codes = {str(c) for c in codes}
    return {
        c for c in codes if not any(o != c and o.startswith(c + ".") for o in codes)
    }


def _compact_bullets(text: object, max_items: int = 4, max_chars: int = 220) -> str:
    """Collapse an xlsx bullet block (`* item\n* item`) into `item; item; ...`,
    truncated by item-count and total chars to keep the prompt bounded."""
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


def render_leaf_blocks(df: pd.DataFrame) -> dict[str, str]:
    """`{code: rendered_block}` for every deepest-available leaf in `df`.

    Per-leaf format:
        {code} | {title}
          : includes: a; b; c
          : also: ...
          : excludes: ...   (each line only when that column has a value)
    """
    df = df[df["code"].notna()].copy()
    df["code"] = df["code"].astype(str)
    leaves = deepest_leaves(df["code"])
    df = df[df["code"].isin(leaves)]
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
        blocks[r.code] = "\n".join(lines)
    return blocks


def _blocks() -> dict[str, str]:
    global _LEAF_BLOCKS
    if _LEAF_BLOCKS is None:
        _LEAF_BLOCKS = render_leaf_blocks(pd.read_excel(config.COICOP_XLSX))
    return _LEAF_BLOCKS


@lru_cache(maxsize=512)
def _render_scope(scope: Optional[frozenset]) -> str:
    blocks = _blocks()
    codes = sorted(blocks) if scope is None else sorted(c for c in scope if c in blocks)
    return "\n".join(blocks[c] for c in codes)


def load_coicop_context(scope: Optional[frozenset] = None) -> str:
    """Multi-line prompt block of COICOP leaves. `scope=None` → all leaves;
    `scope=frozenset({...})` → only the named leaves, in code order."""
    return _render_scope(scope)


def load_taxonomy_index() -> tuple[set[str], dict[str, set[str]]]:
    """Return `(valid_leaf_codes, {})`.

    The second element is the retired per-leaf sub-vocabulary and is now always
    empty; callers that only need the leaf set unpack as `leaves, _ = ...`.
    """
    global _LEAVES
    if _LEAVES is None:
        _LEAVES = deepest_leaves(pd.read_excel(config.COICOP_XLSX)["code"].dropna())
    return _LEAVES, {}
