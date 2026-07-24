"""Gold v5 Pass B labeling — Gemini pro via the tier-c pydantic-ai stack (W3.2).

Independent second labeling pass (different model family from Pass A / codex).
Resumable: skips batches already labeled; stops cleanly on daily quota. Reuses
`prompts/gold_labeling.md`, `rate_limit.py` (gemini-3-pro = 50 RPD), and tier-a
`extract()` for structural context. Validates leaf codes against the 538-leaf set
and re-asks once on invalid codes before downgrading to ambiguous_class.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prices.enrich import config, rate_limit  # noqa: E402
from prices.enrich.extract import extract  # noqa: E402
from prices.enrich.coicop_taxonomy import load_coicop_context, load_taxonomy_index  # noqa: E402

GOLD_DIR = config.REPO_ROOT / "data" / "prices" / "enrich" / "gold"
BATCH_DIR = GOLD_DIR / "batches"
LABELS_DIR = GOLD_DIR / "labels"
PROMPT_PATH = (
    config.REPO_ROOT / "src" / "prices" / "enrich" / "prompts" / "gold_labeling.md"
)
MODEL = config.LLM_MODEL_ESCALATE  # gemini-3-pro
SUB_CHUNK = 50
_CODEBOOK = None


def _codebook() -> str:
    global _CODEBOOK
    if _CODEBOOK is None:
        _CODEBOOK = (
            "\n\n## VALID COICOP LEAVES — a `leaf` code MUST be copied EXACTLY from this "
            "list (never invent a code):\n" + load_coicop_context()
        )
    return _CODEBOOK


class GoldLabel(BaseModel):
    gold_row_id: str
    verdict: str
    code: str
    division: str
    pricing_basis_plausible: str
    rationale: str


class GoldLabelBatch(BaseModel):
    labels: list[GoldLabel]


def _agent(extra: str = "") -> Agent:
    prompt = PROMPT_PATH.read_text(encoding="utf-8") + _codebook() + extra
    return Agent(
        f"google-gla:{MODEL}",
        output_type=GoldLabelBatch,
        system_prompt=prompt,
        output_retries=config.OUTPUT_RETRIES,
        model_settings={"temperature": 0.0},
    )


def _payload(row) -> dict:
    ta = extract(
        item_name=str(row["product_name_original"]),
        category=str(row.get("category") or "") or None,
        country=str(row.get("country") or "") or None,
        lang=None,
    )
    return {
        "gold_row_id": row["gold_row_id"],
        "product_name": str(row["product_name_original"]),
        "country": str(row.get("country") or ""),
        "source": str(row.get("source") or ""),
        "channel": str(row.get("channel") or ""),
        "retailer_category": str(row.get("category") or ""),
        "declared_coicop_codes": str(row.get("declared_coicop_codes") or ""),
        "price": None if pd.isna(row.get("price")) else float(row["price"]),
        "tier_a_extraction": {
            "pricing_basis": ta.pricing_basis,
            "amount_value": ta.amount_value,
            "standard_unit": ta.standard_unit,
            "count": ta.count,
            "multiplier": ta.multiplier,
        },
    }


async def _call(agent: Agent, payloads: list[dict]) -> list[GoldLabel]:
    # include the injected codebook in the token estimate so rate_limit paces correctly
    estimate = max(
        config.RATE_LIMIT_TOKEN_ESTIMATE_PER_CALL,
        (len(json.dumps(payloads)) + len(_codebook())) // 3 + 2000,
    )
    last = None
    for attempt in range(5):
        await rate_limit.acquire(MODEL, estimated_tokens=estimate)
        try:
            result = await agent.run(json.dumps(payloads))
            try:
                rate_limit.record_actual(MODEL, int(result.usage().total_tokens))
            except Exception:
                pass
            return result.output.labels
        except ModelHTTPError as e:
            if e.status_code not in (429, 503):
                raise
            last = e
            await asyncio.sleep(2**attempt * 5)
    raise last


async def _label_chunk(
    payloads: list[dict], leaves: set
) -> tuple[list[dict], int, int]:
    labels = await _call(_agent(), payloads)
    by_id = {lb.gold_row_id: lb for lb in labels}
    invalid = [
        p["gold_row_id"]
        for p in payloads
        if _is_invalid(by_id.get(p["gold_row_id"]), leaves)
    ]
    n_reask = 0
    if invalid:
        n_reask = len(invalid)
        note = (
            "\n\nCORRECTION: these gold_row_ids had a `code` that is NOT a valid 5-level "
            f"COICOP leaf: {invalid}. Re-label ONLY these rows; if unsure of the exact leaf, "
            "use verdict `ambiguous_class` with the 4-digit class."
        )
        retry_payloads = [p for p in payloads if p["gold_row_id"] in set(invalid)]
        redo = await _call(_agent(note), retry_payloads)
        for lb in redo:
            by_id[lb.gold_row_id] = lb
    out, n_invalid = [], 0
    for p in payloads:
        lb = by_id.get(p["gold_row_id"])
        if lb is None:
            continue
        d = lb.model_dump()
        if _is_invalid(lb, leaves):
            n_invalid += 1
            d["verdict"] = "ambiguous_class"
            d["code"] = (lb.division or d.get("code", ""))[:4]
            d["invalid_downgraded"] = True
        out.append(d)
    return out, n_invalid, n_reask


def _is_invalid(lb, leaves) -> bool:
    if lb is None:
        return False
    return lb.verdict == "leaf" and lb.code not in leaves


async def run(only_batch: int | None, limit_rows: int | None) -> None:
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    leaves, _ = load_taxonomy_index()
    batches = sorted(BATCH_DIR.glob("gold_v5_batch_*.csv"))
    for bpath in batches:
        b = int(bpath.stem.split("_")[-1])
        if only_batch is not None and b != only_batch:
            continue
        out_path = LABELS_DIR / f"pass_b_batch_{b:03d}.json"
        if out_path.exists():
            print(f"batch {b:03d}: already labeled, skip")
            continue
        df = pd.read_csv(bpath)
        if limit_rows:
            df = df.head(limit_rows)
        payloads = [_payload(r) for _, r in df.iterrows()]
        all_out, tot_inv, tot_reask = [], 0, 0
        try:
            for i in range(0, len(payloads), SUB_CHUNK):
                out, inv, reask = await _label_chunk(
                    payloads[i : i + SUB_CHUNK], leaves
                )
                all_out.extend(out)
                tot_inv += inv
                tot_reask += reask
        except rate_limit.DailyQuotaExhausted:
            print(f"batch {b:03d}: daily quota exhausted; stopping (resume tomorrow)")
            return
        out_path.write_text(
            json.dumps(all_out, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        meta = {
            "pass": "B",
            "model": MODEL,
            "n_rows": len(all_out),
            "n_invalid_downgraded": tot_inv,
            "n_reasked": tot_reask,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (LABELS_DIR / f"pass_b_batch_{b:03d}.meta.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
        print(
            f"batch {b:03d}: {len(all_out)} labeled (invalid_downgraded={tot_inv}, reasked={tot_reask}) -> {out_path}"
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--batch", type=int, default=None, help="Only label this batch index"
    )
    ap.add_argument(
        "--limit-rows",
        type=int,
        default=None,
        help="Smoke test: only first N rows of the batch",
    )
    ap.add_argument(
        "--model",
        default=config.LLM_MODEL_ESCALATE,
        help="Gemini model id (default escalate=gemini-3-pro; use gemini-3.1-flash-lite if pro is unavailable)",
    )
    args = ap.parse_args()
    global MODEL
    MODEL = args.model
    asyncio.run(run(args.batch, args.limit_rows))


if __name__ == "__main__":
    main()
