"""Apply resolution documents (W5.2) — the write side of the verdict loop.

``prices queue apply FILE...`` funnels here. For each file we:
  1. parse + taxonomy-validate its resolutions,
  2. merge across files, escalating any canonical_key the files resolve
     differently (cross-resolver disagreement is signal, not noise),
  3. append the survivors to the label_store at tier ``T3_adjudicated``,
  4. apply any optional ``gazetteer`` role-verdict blocks to the flywheel,
  5. regenerate the lexicon so the new labels earn phrase support,
  6. dump the escalated rows to an adjudication file for a human pass.

Kept out of the CLI so the orchestration is unit-testable with tiny inputs and
an injected ``valid_leaves`` set (no COICOP xlsx read required).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from prices.enrich import label_store
from prices.enrich.consensus import QUEUE_DIR
from prices.enrich.consensus.resolutions import (
    merge_resolution_sets,
    parse_resolutions,
    to_store_rows,
)

ADJUDICATION_DIR = QUEUE_DIR / "adjudication"


def _taxonomy_leaves() -> set[str]:
    from prices.enrich.tier_b.taxonomy_index import load_taxonomy_index

    leaves, _ = load_taxonomy_index()
    return leaves


def _apply_gazetteer_blocks(blocks: list[dict]) -> int:
    """Apply optional flywheel role-verdicts. Each block is a base_items
    verdicts document ({item, verdicts:[...]}); returns net new gazetteer rows."""
    if not blocks:
        return 0
    from prices.enrich.base_items import store
    from prices.enrich.base_items import verdicts as V

    before = len(store.load_gazetteer())
    for block in blocks:
        item = block.get("item")
        vmap = V.parse_verdicts(block, item)
        store.append_gazetteer(item, vmap)
    return len(store.load_gazetteer()) - before


def _write_escalated(escalated: list[dict]) -> Path | None:
    if not escalated:
        return None
    ADJUDICATION_DIR.mkdir(parents=True, exist_ok=True)
    stamp = (
        datetime.now(timezone.utc).isoformat().replace(":", "").replace("-", "")[:15]
    )
    out = ADJUDICATION_DIR / f"escalated_{stamp}.json"
    out.write_text(
        json.dumps({"escalated": escalated}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out


def apply_resolution_files(
    paths,
    regen_lexicon: bool = True,
    valid_leaves: set[str] | None = None,
) -> dict:
    """Apply one or more resolution documents. Returns a summary dict."""
    leaves = valid_leaves if valid_leaves is not None else _taxonomy_leaves()

    sets: list[list[dict]] = []
    gazetteer_blocks: list[dict] = []
    for p in paths:
        payload = json.loads(Path(p).read_text(encoding="utf-8"))
        sets.append(parse_resolutions(payload, valid_leaves=leaves))
        gazetteer_blocks.extend(payload.get("gazetteer", []) or [])

    applicable, escalated = merge_resolution_sets(sets)
    store_rows = to_store_rows(applicable)

    written = 0
    if not store_rows.empty:
        label_store.append(store_rows)
        written = len(store_rows)

    gaz_new = _apply_gazetteer_blocks(gazetteer_blocks)

    lexicon_rebuilt = False
    if regen_lexicon and written:
        from prices.enrich.lexicon import build_lexicon

        build_lexicon()
        lexicon_rebuilt = True

    escalated_path = _write_escalated(escalated)

    return {
        "files": [str(p) for p in paths],
        "written": written,
        "escalated": len(escalated),
        "escalated_path": str(escalated_path) if escalated_path else None,
        "gazetteer_new": gaz_new,
        "lexicon_rebuilt": lexicon_rebuilt,
    }
