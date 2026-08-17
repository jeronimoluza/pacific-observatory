"""Drive the codex CLI over the exported adjudication batches.

One ``codex exec`` per batch. Batches are already one question each, so the
model reads the definitions once and answers ~27 products against them — the
sub-chunking ``scripts/gold_v5_label_pass_a.py`` needs for 150-row batches is
unnecessary here.

Resumable in the same way as the original passes: a batch whose verdict file
already exists is skipped. Unlike those passes there is no ``--limit-rows``, so
a partial file cannot be written and then silently satisfy a later full run —
a batch is written once, complete, or not at all.

``report`` is the gate. It scores the planted controls against what the manifest
knows they are and prints the flip rate per batch *without* writing anything to
``gold/corrections/``. Read it before running the rest of a round: a control
flip means the adjudicator is moving labels nothing disputed, and the verdicts
are not worth ingesting.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from prices.enrich import coicop_taxonomy
from prices.enrich.gold_audit import BATCH_DIR, adjudicate, run_dir, score

MODEL = "gpt-5.5"
TIMEOUT = 900
MAX_ATTEMPTS = 3
VERDICTS_DIR = "verdicts"

SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gold_row_id": {"type": "string"},
                    "new_code": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["gold_row_id", "new_code", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}


def _codex(prompt: str, schema_path: Path, model: str) -> list[dict]:
    last = None
    for _ in range(MAX_ATTEMPTS):
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
                    "-m",
                    model,
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
                timeout=TIMEOUT,
            )
            txt = (
                out_path.read_text(encoding="utf-8").strip()
                if out_path.exists()
                else ""
            )
            if proc.returncode == 0 and txt:
                return json.loads(txt).get("verdicts", [])
            last = proc.stderr[-400:] or f"empty output (rc={proc.returncode})"
        except Exception as e:  # noqa: BLE001
            last = str(e)
        finally:
            out_path.unlink(missing_ok=True)
    raise RuntimeError(f"codex failed after {MAX_ATTEMPTS} attempts: {last}")


def _prompt(instructions: str, rows: list[dict]) -> str:
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    return f"{instructions}\n\n## Products\n\n{body}\n"


def _read_batch(bdir: Path, entry: dict) -> tuple[str, list[dict]]:
    rows = [
        json.loads(ln)
        for ln in (bdir / entry["file"]).read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    return (bdir / entry["prompt"]).read_text(encoding="utf-8"), rows


def run(run_id: str, only: int | None = None, model: str = MODEL) -> dict:
    """Adjudicate every exported batch that has no verdict file yet."""
    bdir = run_dir(run_id) / BATCH_DIR
    manifest = json.loads((bdir / adjudicate.MANIFEST_FILE).read_text(encoding="utf-8"))
    vdir = bdir / VERDICTS_DIR
    vdir.mkdir(parents=True, exist_ok=True)

    valid = coicop_taxonomy.load_taxonomy_index()[0]
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as sf:
        json.dump(SCHEMA, sf)
        schema_path = Path(sf.name)

    done, skipped = [], []
    try:
        for i, entry in enumerate(manifest["batches"]):
            if only is not None and i != only:
                continue
            out = vdir / f"verdict_{entry['file'].replace('.jsonl', '')}.json"
            if out.exists():
                skipped.append(out.name)
                continue

            instructions, rows = _read_batch(bdir, entry)
            wanted = [r["gold_row_id"] for r in rows]
            got = {
                v["gold_row_id"]: v
                for v in _codex(_prompt(instructions, rows), schema_path, model)
                if v.get("gold_row_id") in set(wanted)
            }

            missing = [r for r in rows if r["gold_row_id"] not in got]
            if missing:
                note = (
                    f"{instructions}\n\n## Products\n\nThese lines were omitted from "
                    "the previous response. Return a verdict for every one.\n"
                )
                for v in _codex(
                    note
                    + "\n".join(json.dumps(r, ensure_ascii=False) for r in missing),
                    schema_path,
                    model,
                ):
                    if v.get("gold_row_id") in set(wanted):
                        got[v["gold_row_id"]] = v

            verdicts = [got[k] for k in wanted if k in got]
            unknown = sorted(
                {v["new_code"] for v in verdicts if v["new_code"] not in valid}
            )
            out.write_text(
                json.dumps(
                    {
                        "batch": entry["file"],
                        "group": entry.get("group") or "|".join(entry.get("pair", [])),
                        "model": model,
                        "n_expected": len(wanted),
                        "n_returned": len(verdicts),
                        "unknown_codes": unknown,
                        "verdicts": verdicts,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            done.append(
                {
                    "batch": entry["file"],
                    "n_expected": len(wanted),
                    "n_returned": len(verdicts),
                    "unknown_codes": unknown,
                }
            )
    finally:
        schema_path.unlink(missing_ok=True)

    return {
        "run_id": run_id,
        "model": model,
        "n_adjudicated": len(done),
        "n_skipped": len(skipped),
        "batches": done,
        "verdicts_dir": str(vdir),
    }


def collect(run_id: str) -> Path:
    """Flatten every verdict file into one JSONL that ``ingest`` can read."""
    vdir = run_dir(run_id) / BATCH_DIR / VERDICTS_DIR
    out = vdir / "verdicts.jsonl"
    lines = []
    for f in sorted(vdir.glob("verdict_batch_*.json")):
        for v in json.loads(f.read_text(encoding="utf-8"))["verdicts"]:
            lines.append(json.dumps(v, ensure_ascii=False))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def report(run_id: str) -> dict:
    """Score the planted controls. Writes nothing — this is the gate."""
    bdir = run_dir(run_id) / BATCH_DIR
    manifest = json.loads((bdir / adjudicate.MANIFEST_FILE).read_text(encoding="utf-8"))
    expected = {}
    for b in manifest["batches"]:
        expected.update(b.get("control_expected", {}))

    gold = score.load(run_id).set_index("gold_row_id")["code"].to_dict()

    per_batch, flips = [], []
    n_ctrl = n_real = n_changed = 0
    for f in sorted((bdir / VERDICTS_DIR).glob("verdict_batch_*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        b_ctrl = b_flip = b_real = b_changed = 0
        for v in data["verdicts"]:
            rid, new = v["gold_row_id"], v["new_code"]
            if rid in expected:
                b_ctrl += 1
                if new != expected[rid]:
                    b_flip += 1
                    flips.append(
                        {"gold_row_id": rid, "was": expected[rid], "became": new}
                    )
            else:
                b_real += 1
                b_changed += int(new != gold.get(rid))
        n_ctrl += b_ctrl
        n_real += b_real
        n_changed += b_changed
        per_batch.append(
            {
                "batch": data["batch"],
                "group": data.get("group") or "|".join(data.get("pair", [])),
                "n_real": b_real,
                "n_overturned": b_changed,
                "overturn_rate": round(b_changed / b_real, 3) if b_real else None,
                "n_controls": b_ctrl,
                "n_control_flips": b_flip,
            }
        )

    return {
        "run_id": run_id,
        "n_real": n_real,
        "n_overturned": n_changed,
        "overturn_rate": round(n_changed / n_real, 3) if n_real else None,
        "n_controls": n_ctrl,
        "n_control_flips": len(flips),
        "control_flip_rate": (len(flips) / n_ctrl) if n_ctrl else None,
        "control_flips": flips,
        "batches": per_batch,
    }
