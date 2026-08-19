"""Stage 2a — non-Claude panel: codex (gpt-5.5) + gemini (flash-lite).

Runs the external-process models over eval_items.jsonl as grounded multiple
choice and writes one labels_<model>.jsonl per model ({name, code, confidence,
reason, valid}). Claude models (Opus/Sonnet) are produced separately by
dispatched agents into labels_opus.jsonl / labels_sonnet.jsonl (same schema);
analyze.py merges whatever labels_*.jsonl exist. Resumable: already-labelled
names are skipped per model.

Run: python -m prices.enrich.experiments.knn_competence.panel \
        --models gemini codex [--limit N]

CODEX PIN: the `codex` CLI now defaults to sol-5.6 — we pass `-m gpt-5.5`.
GEMINI PIN: gemini-3-pro hangs — we pin gemini-3.1-flash-lite.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field

from prices.enrich import config, rate_limit
from prices.enrich.experiments.knn_competence.prompt import build_prompt

OUT_DIR = (
    config.REPO_ROOT / "data" / "prices" / "enrich" / "_experiments" / "knn_competence"
)
CODEX_MODEL = "gpt-5.5"
GEMINI_MODEL = "gemini-3.1-flash-lite"

_CHOICE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["code", "confidence", "reason"],
    "properties": {
        "code": {"type": "string"},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
}


class Choice(BaseModel):
    code: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


def _label_codex(prompt: str) -> Choice | None:
    with tempfile.TemporaryDirectory() as td:
        schema = Path(td) / "schema.json"
        out = Path(td) / "out.json"
        schema.write_text(json.dumps(_CHOICE_SCHEMA))
        proc = subprocess.run(
            [
                "codex",
                "exec",
                "-",
                "-m",
                CODEX_MODEL,
                "-s",
                "read-only",
                "--skip-git-repo-check",
                "--output-schema",
                str(schema),
                "--output-last-message",
                str(out),
            ],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode != 0 or not out.exists():
            return None
        try:
            return Choice(**json.loads(out.read_text()))
        except Exception:
            return None


def _write(f, it: dict, c: Choice | None) -> None:
    rec = {
        "name": it["name"],
        "code": c.code if c else None,
        "confidence": c.confidence if c else None,
        "reason": c.reason if c else "ADAPTER_FAILED",
        "valid": bool(c and c.code in it["candidates"]),
    }
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    f.flush()


def _done_names(model: str) -> set[str]:
    """Names already labelled with a non-null code (failed rows are retried)."""
    p = OUT_DIR / f"labels_{model}.jsonl"
    if not p.exists():
        return set()
    done = set()
    for x in p.read_text().splitlines():
        if not x:
            continue
        r = json.loads(x)
        if r.get("code") is not None:
            done.add(r["name"])
    return done


def _run_codex(items: list[dict]) -> None:
    todo = [it for it in items if it["name"] not in _done_names("codex")]
    print(f"[codex] {len(todo)} to label")
    with open(OUT_DIR / "labels_codex.jsonl", "a") as f:
        for i, it in enumerate(todo, 1):
            _write(f, it, _label_codex(build_prompt(it["name"], it["candidate_notes"])))
            if i % 25 == 0:
                print(f"  [codex] {i}/{len(todo)}")


async def _run_gemini(items: list[dict]) -> None:
    """Rate-limited (rpm/tpm/rpd via rate_limit.acquire) + retry on transient error."""
    from pydantic_ai import Agent

    agent = Agent(
        f"google-gla:{GEMINI_MODEL}",
        output_type=Choice,
        model_settings={"temperature": 0.0},
    )
    todo = [it for it in items if it["name"] not in _done_names("gemini")]
    print(f"[gemini] {len(todo)} to label (rpm-paced)")
    with open(OUT_DIR / "labels_gemini.jsonl", "a") as f:
        for i, it in enumerate(todo, 1):
            prompt = build_prompt(it["name"], it["candidate_notes"])
            c = None
            for attempt in range(4):
                try:
                    await rate_limit.acquire(GEMINI_MODEL, 1500)
                    res = await agent.run(prompt)
                    rate_limit.record_actual(GEMINI_MODEL, 1500)
                    c = res.output
                    break
                except rate_limit.DailyQuotaExhausted:
                    print(
                        f"[gemini] daily quota exhausted at {i}/{len(todo)} — stopping"
                    )
                    _write(f, it, None)
                    return
                except Exception:
                    await asyncio.sleep(5 * (attempt + 1))
            _write(f, it, c)
            if i % 25 == 0:
                print(f"  [gemini] {i}/{len(todo)}")


def run(models: list[str], limit: int | None = None) -> None:
    items = [
        json.loads(x)
        for x in (OUT_DIR / "eval_items.jsonl").read_text().splitlines()
        if x
    ]
    if limit:
        items = items[:limit]
    for model in models:
        if model == "codex":
            _run_codex(items)
        elif model == "gemini":
            asyncio.run(_run_gemini(items))
        print(f"[{model}] done -> {OUT_DIR / f'labels_{model}.jsonl'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["gemini", "codex"])
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    run(args.models, limit=args.limit)


if __name__ == "__main__":
    main()
