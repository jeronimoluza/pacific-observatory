"""Gold v5 Pass A labeling — GPT (codex CLI, gpt-5.x) as the first pass (W3.2).

Independent first labeling pass, a different model family from Pass B (Gemini).
Drives `codex exec` non-interactively with a strict `--output-schema`, reusing
`prompts/gold_labeling.md`, the 538-leaf codebook, and tier-a `extract()` for
structural context. Resumable: skips batches already labeled; validates leaf
codes against the taxonomy and re-asks once on invalid before downgrading to
ambiguous_class. Writes pass_a_batch_NNN.json in the same schema Pass B emits.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from prices.enrich.tier_b.taxonomy_index import (  # noqa: E402
    load_coicop_context,
    load_taxonomy_index,
)

from gold_v5_label_pass_b import (  # noqa: E402
    BATCH_DIR,
    LABELS_DIR,
    PROMPT_PATH,
    _payload,
)

SUB_CHUNK = 50
MODEL_TAG = "codex/gpt-5.5"
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "gold_row_id": {"type": "string"},
                    "verdict": {"type": "string"},
                    "code": {"type": "string"},
                    "division": {"type": "string"},
                    "pricing_basis_plausible": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": [
                    "gold_row_id",
                    "verdict",
                    "code",
                    "division",
                    "pricing_basis_plausible",
                    "rationale",
                ],
            },
        }
    },
    "required": ["labels"],
}
_CODEBOOK = None


def _codebook() -> str:
    global _CODEBOOK
    if _CODEBOOK is None:
        _CODEBOOK = (
            "\n\n## VALID COICOP LEAVES — a `leaf` code MUST be copied EXACTLY from "
            "this list (never invent a code):\n" + load_coicop_context()
        )
    return _CODEBOOK


def _prompt(payloads: list[dict], extra: str = "") -> str:
    base = PROMPT_PATH.read_text(encoding="utf-8") + _codebook() + extra
    return (
        base + "\n\n## ROWS TO LABEL (JSON array; return one object per row, in order, "
        'as {"labels":[...]}):\n' + json.dumps(payloads, ensure_ascii=False)
    )


def _codex(prompt: str, schema_path: Path) -> list[dict]:
    last = None
    for attempt in range(4):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as tf:
            out_path = Path(tf.name)
        try:
            proc = subprocess.run(
                [
                    "codex",
                    "exec",
                    "-",
                    "-s",
                    "read-only",
                    "--skip-git-repo-check",
                    "--output-schema",
                    str(schema_path),
                    "--output-last-message",
                    str(out_path),
                ],
                input=prompt,
                text=True,
                capture_output=True,
                timeout=600,
            )
            txt = (
                out_path.read_text(encoding="utf-8").strip()
                if out_path.exists()
                else ""
            )
            if proc.returncode == 0 and txt:
                return json.loads(txt).get("labels", [])
            last = proc.stderr[-500:] or f"empty output (rc={proc.returncode})"
        except Exception as e:  # noqa: BLE001
            last = str(e)
        finally:
            out_path.unlink(missing_ok=True)
    raise RuntimeError(f"codex failed after retries: {last}")


def _is_invalid(lb: dict, leaves: set) -> bool:
    return lb.get("verdict") == "leaf" and lb.get("code") not in leaves


def _label_chunk(payloads: list[dict], leaves: set, schema_path: Path):
    labels = _codex(_prompt(payloads), schema_path)
    by_id = {str(lb.get("gold_row_id")): lb for lb in labels}
    invalid = [
        p["gold_row_id"]
        for p in payloads
        if _is_invalid(by_id.get(p["gold_row_id"], {}), leaves)
    ]
    n_reask = 0
    if invalid:
        n_reask = len(invalid)
        note = (
            "\n\nCORRECTION: these gold_row_ids had a `code` that is NOT a valid "
            f"5-level COICOP leaf: {invalid}. Re-label ONLY these rows; if unsure of "
            "the exact leaf, use verdict `ambiguous_class` with the 4-digit class."
        )
        retry = [p for p in payloads if p["gold_row_id"] in set(invalid)]
        for lb in _codex(_prompt(retry, note), schema_path):
            by_id[str(lb.get("gold_row_id"))] = lb
    out, n_invalid = [], 0
    for p in payloads:
        lb = by_id.get(p["gold_row_id"])
        if lb is None:
            continue
        d = dict(lb)
        if _is_invalid(lb, leaves):
            n_invalid += 1
            d["verdict"] = "ambiguous_class"
            d["code"] = str(lb.get("division", "") or lb.get("code", ""))[:4]
            d["invalid_downgraded"] = True
        out.append(d)
    return out, n_invalid, n_reask


def run(only_batch, limit_rows):
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    leaves, _ = load_taxonomy_index()
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as sf:
        json.dump(SCHEMA, sf)
        schema_path = Path(sf.name)
    try:
        for bpath in sorted(BATCH_DIR.glob("gold_v5_batch_*.csv")):
            b = int(bpath.stem.split("_")[-1])
            if only_batch is not None and b != only_batch:
                continue
            out_path = LABELS_DIR / f"pass_a_batch_{b:03d}.json"
            if out_path.exists():
                print(f"batch {b:03d}: already labeled, skip", flush=True)
                continue
            df = pd.read_csv(bpath)
            if limit_rows:
                df = df.head(limit_rows)
            payloads = [_payload(r) for _, r in df.iterrows()]
            all_out, tot_inv, tot_reask = [], 0, 0
            for i in range(0, len(payloads), SUB_CHUNK):
                o, inv, reask = _label_chunk(
                    payloads[i : i + SUB_CHUNK], leaves, schema_path
                )
                all_out.extend(o)
                tot_inv += inv
                tot_reask += reask
            out_path.write_text(
                json.dumps(all_out, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            (LABELS_DIR / f"pass_a_batch_{b:03d}.meta.json").write_text(
                json.dumps(
                    {
                        "pass": "A",
                        "model": MODEL_TAG,
                        "n_rows": len(all_out),
                        "n_invalid_downgraded": tot_inv,
                        "n_reasked": tot_reask,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(
                f"batch {b:03d}: {len(all_out)} labeled "
                f"(invalid_downgraded={tot_inv}, reasked={tot_reask}) -> {out_path}",
                flush=True,
            )
    finally:
        schema_path.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=None)
    ap.add_argument("--limit-rows", type=int, default=None)
    args = ap.parse_args()
    run(args.batch, args.limit_rows)


if __name__ == "__main__":
    main()
