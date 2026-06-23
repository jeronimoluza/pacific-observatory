"""Read-only harvest of per-leaf short items from the COICOP xlsx.

Parses `config.COICOP_XLSX` (sheet `COICOP_2018`) into `{leaf_code: [short_item, ...]}`,
keeping only short noun phrases grounded in each leaf's own `title`/`intro`/`includes`/
`alsoIncludes` cells (D3/SUBLAB-03 — no cross-leaf borrowing). COICOP gloss prose
(`n.e.c.`, leading `Other …`, multi-clause `includes` sentences) is purged, not hidden
(D1/SUBLAB-01).

This module reads the xlsx and writes nothing. Plan 02 consumes `harvest_leaf_items`.
"""

from __future__ import annotations

import pandas as pd

from prices.enrich import config

_SHEET = "COICOP_2018"
_TEXT_COLS = ("title", "intro", "includes", "alsoIncludes")
_CR_MARKER = "_x000D_"
_CLAUSE_MARKERS = ("including", "in the form of")
_MAX_TOKENS = 6


def _split_bullets(cell: object) -> list[str]:
    """Split an xlsx bullet block into candidate strings.

    Mirrors `taxonomy_index._compact_bullets`'s convention (replace `_x000D_`,
    split on newline, `lstrip('*-•')`) but is exhaustive (no item-count cap).
    """
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return []
    text = str(cell).replace(_CR_MARKER, "").strip()
    if not text:
        return []
    out: list[str] = []
    for raw in text.split("\n"):
        item = raw.lstrip("*-•").strip()
        if item:
            out.append(item)
    return out


def _is_prose(candidate: str) -> bool:
    """Reject COICOP gloss prose; keep short noun phrases (incl. parentheticals)."""
    s = candidate.strip()
    if not s:
        return True
    low = s.lower()
    if "n.e.c." in low:
        return True
    if low.startswith("other "):
        return True
    if any(marker in low for marker in _CLAUSE_MARKERS):
        return True
    tokens = s.split()
    n_tokens = len(tokens)
    # Multi-clause comma/semicolon run with many tokens = sentence-style prose.
    if n_tokens > _MAX_TOKENS and ("," in s or ";" in s):
        return True
    # Full-sentence gloss: ends with a period and is long.
    if s.endswith(".") and n_tokens > _MAX_TOKENS:
        return True
    return False


def _harvest_row(row: pd.Series) -> list[str]:
    """Short items for a single xlsx row, from its own cells only.

    The row `title` is always emitted (short by construction); bullets from
    `intro`/`includes`/`alsoIncludes` are split and prose-filtered. De-duplicated
    case-insensitively, first-occurrence order preserved.
    """
    candidates: list[str] = []
    title = row.get("title")
    if title is not None and not (isinstance(title, float) and pd.isna(title)):
        title_s = str(title).strip()
        if title_s:
            candidates.append(title_s)
    for col in ("intro", "includes", "alsoIncludes"):
        candidates.extend(_split_bullets(row.get(col)))

    seen: set[str] = set()
    items: list[str] = []
    for cand in candidates:
        cand = cand.strip()
        if _is_prose(cand):
            continue
        key = cand.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(cand)
    return items


def harvest_leaf_items(codes: set[str] | None = None) -> dict[str, list[str]]:
    """Return `{leaf_code: [short_item, ...]}` grounded in each leaf's own xlsx cells.

    `codes=None` harvests every non-NaN-code row in the sheet. Otherwise only the
    requested codes are harvested. Reads `config.COICOP_XLSX`; writes nothing.
    """
    df = pd.read_excel(config.COICOP_XLSX, sheet_name=_SHEET)
    df = df[df["code"].notna()].copy()
    df["code"] = df["code"].astype(str)

    out: dict[str, list[str]] = {}
    for _, row in df.iterrows():
        code = row["code"]
        if codes is not None and code not in codes:
            continue
        out[code] = _harvest_row(row)
    return out
