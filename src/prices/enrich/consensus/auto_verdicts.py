"""Auto-verdicts (W5.1) — batch Gemini flash-lite over ranked conflict-queue
slices to draft resolutions. HUMAN-GATED: this only writes a staging JSON in the
``resolutions`` document shape; nothing reaches the label_store until a human
runs ``prices queue apply`` on the (reviewed) file.

Reuses the tier-c stack: the hierarchical COICOP context block, ``rate_limit``
throttling + 429 backoff (via ``tier_c._run_with_retry_after``), and flash-lite
at temperature 0. The model AUDITS the witness disagreement rather than
re-solving from scratch — each queue row already carries the competing votes.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from prices.enrich import config
from prices.enrich.consensus import QUEUE_DIR
from prices.enrich.tier_b.taxonomy_index import (
    load_coicop_context as _load_coicop_context,
)

STAGING_DIR = QUEUE_DIR / "auto_verdicts"

_SYSTEM = """You adjudicate COICOP classification CONFLICTS for a price index.

Each item is a product name our witnesses (a trained model, KNN retrieval, a
lexicon, a rule cascade, source metadata) DISAGREED on. You are given the name
and the competing votes. Decide the single correct outcome:

- "leaf": the item is a real, priceable product -> return its COICOP leaf code
  (a full dotted code from the taxonomy below, e.g. 01.1.1.3.9). Prefer a leaf
  that at least one witness proposed unless all of them are clearly wrong.
- "exclude": not a consumer product we price (service, fee, gift card, bundle
  with no unit price, pure marketing text).
- "other_form": a real product but in a non-priceable form/packaging for our
  basket (e.g. a variety multipack that hides the per-unit measure).
- "ambiguous_class": the name genuinely cannot be resolved to one leaf from the
  text alone (two plausible divisions, missing the discriminating word).
- "escalate": you are guessing; send to human adjudication.

Return one verdict per input, echoing its canonical_key. Set confidence in
0..1 to how strongly you can defend the call. Keep rationale to one clause.

## COICOP taxonomy
{coicop_context}
"""


class _Verdict(BaseModel):
    canonical_key: str
    decision: Literal["leaf", "exclude", "other_form", "ambiguous_class", "escalate"]
    leaf: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    rationale: str = ""


class _VerdictBatch(BaseModel):
    verdicts: list[_Verdict]


def _build_agent() -> Agent:
    system = _SYSTEM.replace("{coicop_context}", _load_coicop_context(None))
    try:
        return Agent(
            f"google-gla:{config.LLM_MODEL_BASELINE}",
            output_type=_VerdictBatch,
            system_prompt=system,
            output_retries=config.OUTPUT_RETRIES,
            model_settings={"temperature": config.LLM_TEMPERATURE},
        )
    except TypeError:
        return Agent(
            f"google-gla:{config.LLM_MODEL_BASELINE}",
            output_type=_VerdictBatch,
            system_prompt=system,
            output_retries=config.OUTPUT_RETRIES,
        )


def _payload(row) -> dict:
    return {
        "canonical_key": str(row["canonical_key"]),
        "name": str(row.get("example_name") or row["canonical_key"]),
        "competing_votes": str(row.get("competing_votes") or ""),
        "reason": str(row.get("reason") or ""),
    }


async def _run_batches(queue_df, batch_size: int) -> list[dict]:
    from prices.enrich.stages import tier_c

    agent = _build_agent()
    payloads = [_payload(r) for _, r in queue_df.iterrows()]
    chunks = [payloads[i : i + batch_size] for i in range(0, len(payloads), batch_size)]
    verdicts: dict[str, dict] = {}

    for chunk in chunks:
        result = await tier_c._run_with_retry_after(
            agent, json.dumps(chunk), scope=None
        )
        for v in result.output.verdicts:
            verdicts[v.canonical_key] = {
                "canonical_key": v.canonical_key,
                "decision": v.decision,
                "leaf": v.leaf,
                "confidence": v.confidence,
                "rationale": v.rationale,
            }

    # keep queue order; drop names the model failed to echo back.
    return [
        verdicts[p["canonical_key"]] for p in payloads if p["canonical_key"] in verdicts
    ]


def draft_verdicts(queue_df, batch_size: int = 50) -> dict:
    """Run flash-lite over the queue slice and return a resolution document
    (the ``resolutions.py`` shape) ready to stage. Never touches the store."""
    resolutions = (
        asyncio.run(_run_batches(queue_df, batch_size)) if len(queue_df) else []
    )
    return {
        "resolver": config.LLM_MODEL_BASELINE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_requested": int(len(queue_df)),
        "resolutions": resolutions,
    }


def write_staging(doc: dict, out_path: Optional[Path] = None) -> Path:
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    if out_path is None:
        stamp = (
            doc.get("generated_at", "").replace(":", "").replace("-", "")[:15]
            or "draft"
        )
        out_path = STAGING_DIR / f"auto_verdicts_{stamp}.json"
    out_path = Path(out_path)
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
