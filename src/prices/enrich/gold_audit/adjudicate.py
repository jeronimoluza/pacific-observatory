"""Export suspect rows for re-adjudication, and ingest the verdicts.

No LLM is called here. ``export`` writes JSONL batches, an out-of-band labeler
(codex / gemini / opus, same as the original gold rounds) fills in a verdict per
line, and ``ingest`` turns the returned file into a corrections CSV.

Batches are grouped by dispute pair (see ``batching.py``), so every line in a
file asks the same binary question and the COICOP definitions load once instead
of once per row.

**The payload is blind.** It carries the product, the two candidate codes in a
shuffled order, their definitions, and trusted examples of each — and nothing
that identifies which candidate is the current gold label. The current label,
the head's prediction, the neighbourhood majority and the suspicion score are
all withheld, because any one of them lets the adjudicator infer the model's
answer and agree with it. That would launder the classifier's own opinion into
gold and make the retrain look like an improvement it isn't. The verdicts are
compared against gold at ingest time, where the adjudicator cannot see it.

A verdict may name a code outside the two candidates; ingest accepts it. Forced
binary choice would hide the case where gold and the head are *both* wrong.

Ingest never replaces a label on its own. Verdicts land in
``gold/corrections/{run_id}.csv`` with ``status="review"``, and
``classifier.dataset._apply_corrections`` only overlays rows a human has
promoted to ``status="apply"``. Deleting the CSV undoes the round; the
``gold_v5_*`` parquets are never touched.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from prices.enrich import coicop_taxonomy
from prices.enrich.gold_audit import (
    BATCH_DIR,
    CORRECTIONS_DIR,
    batching,
    ensure_run_dir,
    run_dir,
    score,
)

DEFAULT_BATCH_SIZE = batching.DEFAULT_BATCH_SIZE
N_EXAMPLES = 5
MANIFEST_FILE = "manifest.json"

# Rows the adjudicator sees as trusted exemplars: unanimous originally, and the
# head agrees with them out of fold. Circular if it included suspects.
TRUSTED_MAX_SCORE = 0.0


def _trusted_examples(pool: pd.DataFrame, codes: list[str]) -> dict[str, list[str]]:
    """A few unambiguous gold product names per candidate code."""
    out: dict[str, list[str]] = {}
    for code in codes:
        names = pool.loc[pool["code"] == code, "product_name"].head(N_EXAMPLES)
        out[code] = [str(n) for n in names]
    return out


def _payload(row: pd.Series, pair: list[str], rng: np.random.Generator) -> dict:
    """One blind line: the product and the candidates, in a shuffled order.

    Definitions and examples live in the batch's prompt file, not here — every
    line in a batch asks the same question, so repeating the reference material
    forty times is exactly the cost pair-grouping exists to remove."""
    codes = [pair[i] for i in rng.permutation(len(pair))]
    return {
        "gold_row_id": row["gold_row_id"],
        "product_name": str(row["product_name"]),
        "country": row.get("country"),
        "candidate_codes": codes,
    }


def _prompt(pair: list[str], definitions: str, examples: dict[str, list[str]]) -> str:
    """The batch's instruction block: one question, stated once."""
    lines = [
        f"# Adjudicate: {pair[0]} vs {pair[1]}",
        "",
        "Every product below has been assigned one of two COICOP leaves, and two",
        "independent checks disagree about which. For each line, decide which leaf",
        "the product belongs to. You are not told the current label — judge the",
        "product on its own merits.",
        "",
        "If neither candidate is right, answer with the correct COICOP code instead;",
        "a forced choice between two wrong options is worse than a third answer.",
        "",
        "## Candidate definitions",
        "",
        definitions,
        "",
        "## Confirmed examples of each leaf",
        "",
    ]
    for code in pair:
        lines.append(f"**{code}**")
        lines += [f"- {n}" for n in examples.get(code, [])] or ["- (none available)"]
        lines.append("")
    lines += [
        "## Output",
        "",
        "A single JSON object with one entry per input line, in the same order:",
        '`{"verdicts": [{"gold_row_id": "...", "new_code": "...", '
        '"reason": "..."}, ...]}`',
        "",
        "Keep `reason` to one short clause. Return every input line — a missing",
        "`gold_row_id` is re-asked, which costs a second pass over the same batch.",
    ]
    return "\n".join(lines)


def export(
    run_id: str,
    n: int,
    division: str | None = None,
    subset: str | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_pairs: int | None = None,
    control_share: float = batching.CONTROL_SHARE,
) -> dict:
    """Write pair-grouped, control-seeded JSONL batches under the run's ``batches/``.

    `n <= 0` exports every row in the subset; `max_pairs` keeps only the largest
    dispute groups, which is how a calibration slice is cut."""
    suspects = score.load(run_id)
    trusted = suspects[suspects["suspicion_score"] <= TRUSTED_MAX_SCORE]
    pool = batching.control_pool(suspects)
    picked = score.top(run_id, n, division=division, subset=subset)

    plans = batching.plan(
        picked,
        pool,
        batch_size=batch_size,
        control_share=control_share,
        max_pairs=max_pairs,
    )

    bdir = ensure_run_dir(run_id) / BATCH_DIR
    bdir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(batching.SEED)

    manifest = []
    for i, batch in enumerate(plans):
        pair = batch["pair"]
        definitions = coicop_taxonomy.load_coicop_context(frozenset(pair))
        examples = _trusted_examples(trusted, pair)

        name = f"batch_{i:03d}.jsonl"
        (bdir / name).write_text(
            "\n".join(
                json.dumps(_payload(r, pair, rng), ensure_ascii=False)
                for _, r in batch["rows"].iterrows()
            )
            + "\n",
            encoding="utf-8",
        )
        prompt_name = f"batch_{i:03d}.md"
        (bdir / prompt_name).write_text(
            _prompt(pair, definitions, examples), encoding="utf-8"
        )
        manifest.append(
            {
                "file": name,
                "prompt": prompt_name,
                "pair": pair,
                "n_lines": int(len(batch["rows"])),
                "n_real": batch["n_real"],
                "n_controls": len(batch["control_row_ids"]),
                "control_expected": batch["control_expected"],
            }
        )

    (bdir / MANIFEST_FILE).write_text(
        json.dumps({"run_id": run_id, "batches": manifest}, indent=2, default=str),
        encoding="utf-8",
    )

    ungated = [m["file"] for m in manifest if m["n_controls"] == 0]
    return {
        "run_id": run_id,
        "division": division,
        "subset": subset,
        "n_selected": int(len(picked)),
        "n_real_exported": sum(m["n_real"] for m in manifest),
        "n_controls": sum(m["n_controls"] for m in manifest),
        "n_batches": len(manifest),
        "n_pairs": len({tuple(m["pair"]) for m in manifest}),
        "batch_dir": str(bdir),
        "batches_without_controls": ungated,
    }


VERDICT_COLS = {"gold_row_id", "new_code"}


def _load_manifest(run_id: str) -> dict:
    path = run_dir(run_id) / BATCH_DIR / MANIFEST_FILE
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for b in data.get("batches", []):
        out.update(b.get("control_expected", {}))
    return out


def ingest(run_id: str, verdicts_path: str) -> dict:
    """Turn returned verdicts into ``gold/corrections/{run_id}.csv``.

    Accepts JSONL or CSV with at least ``gold_row_id`` and ``new_code``. Rows
    whose verdict matches the current gold are recorded as ``status="agree"``
    so the round's confirm rate is measurable; only genuine changes are written
    as ``status="review"``, awaiting a human flip to ``apply``.

    Planted controls are scored separately and excluded from the corrections
    file. A non-zero control flip rate means the adjudicator moved labels that
    nothing disputed — read the round as unreliable before promoting any row."""
    path = str(verdicts_path)
    if path.endswith(".jsonl"):
        v = pd.DataFrame([json.loads(ln) for ln in open(path) if ln.strip()])
    else:
        v = pd.read_csv(path, dtype=str)

    missing = VERDICT_COLS - set(v.columns)
    if missing:
        raise ValueError(f"verdicts file missing columns: {sorted(missing)}")

    current = score.load(run_id)[["gold_row_id", "code", "product_name"]]
    m = v.merge(current, on="gold_row_id", how="left")

    controls = _load_manifest(run_id)
    is_control = m["gold_row_id"].astype(str).isin(controls)
    ctrl, m = m[is_control], m[~is_control].copy()
    ctrl_flipped = int((ctrl["new_code"].astype(str) != ctrl["code"].astype(str)).sum())

    # A verdict may name a code outside the two candidates — that is the escape
    # hatch for "both are wrong" — but the adjudicator sometimes lands on an
    # intermediate node rather than a leaf (`01.1.8.9` for `01.1.8.9.x`). Those
    # get their own status so a bulk promotion of `review` can never sweep an
    # unclassifiable code into gold.
    valid = coicop_taxonomy.load_taxonomy_index()[0]
    unusable = ~m["new_code"].astype(str).isin(valid)

    changed = m["new_code"].astype(str) != m["code"].astype(str)
    m["status"] = "agree"
    m.loc[changed, "status"] = "review"
    m.loc[unusable, "status"] = "invalid"
    m["old_code"] = m["code"]
    m["run_id"] = run_id

    CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    out = CORRECTIONS_DIR / f"{run_id}.csv"
    cols = ["gold_row_id", "product_name", "old_code", "new_code", "status", "run_id"]
    m[cols].to_csv(out, index=False)

    return {
        "run_id": run_id,
        "out": str(out),
        "n_verdicts": int(len(m)),
        "n_changed": int((changed & ~unusable).sum()),
        "n_agreed": int((~changed).sum()),
        "n_invalid_code": int(unusable.sum()),
        "confirm_rate": float((~changed).mean()) if len(m) else 0.0,
        "n_controls": int(len(ctrl)),
        "n_control_flips": ctrl_flipped,
        "control_flip_rate": float(ctrl_flipped / len(ctrl)) if len(ctrl) else None,
        "note": "status='review' — flip to 'apply' by hand before retraining",
    }
