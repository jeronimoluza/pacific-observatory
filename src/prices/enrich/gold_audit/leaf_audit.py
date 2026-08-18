"""Audit whole COICOP leaves against their definition, not row against row.

The dispute-pair audit (``adjudicate.py``) can only see labels something
disagreed about. A *systematic* convention error leaves no disagreement at all:
both labelers applied the same wrong rule, the head learned that rule from
consistent training data, and the neighbourhood is pure because every neighbour
is mislabeled the same way. High purity, zero suspicion, entirely wrong.

The only way to see that is to compare a leaf against an external truth — the
COICOP definition itself. That is a per-leaf question, so the corpus collapses
from ~24k rows to ~260 questions, and one question costs the same whether the
leaf holds 26 rows or 1,372.

**Sampling is deliberately prototype-weighted.** Members are drawn mostly from
the rows the head is *most* confident about, because those are what the leaf
means in practice. If a leaf's most typical members do not match its definition,
every row in it is wrong. A random sample would dilute that signal with edge
cases that are ambiguous everywhere.

**Controls are planted foreign products** drawn from a confusable leaf. A leaf
audit cannot hide the label — the label is the question — so blindness is not
available here. Instead the gate asks whether the adjudicator *discriminates*:
if it waves through products that provably belong somewhere else, it is
rubber-stamping and the round is void. ``report`` scores this and writes nothing.

Detection power is a design choice, not an oversight: 20 samples catch an error
touching 20% of a leaf ~99% of the time and one touching 1% only ~18% of the
time. Scattered single-row errors are already known to be worth ~0.06% accuracy;
systematic ones are worth orders of magnitude more.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from prices.enrich import coicop_taxonomy
from prices.enrich.gold_audit import ensure_run_dir, run_dir

LEAF_DIR = "leaf_batches"
MANIFEST_FILE = "manifest.json"
VERDICTS_DIR = "verdicts"

SAMPLE_SIZE = 20
N_PROTOTYPE = 14
N_CONTROLS = 3
N_CONFUSABLE = 5
MIN_LEAF_ROWS = 8
SEED = 20260818

SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gold_row_id": {"type": "string"},
                    "belongs": {"type": "boolean"},
                    "correct_code": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["gold_row_id", "belongs", "correct_code", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}


def _confusable(oof: pd.DataFrame, leaf: str, k: int = N_CONFUSABLE) -> list[str]:
    """Leaves the head actually mistakes this one for, most frequent first.

    Data-driven rather than taxonomic: crackers migrate to bread (a sibling) but
    chocolate biscuits migrate to confectionery (a different branch entirely), so
    sibling leaves alone would miss half the realistic alternatives."""
    rows = oof[(oof["code"] == leaf) & (oof["oof_pred"] != leaf)]
    return [c for c in rows["oof_pred"].value_counts().head(k).index if c != leaf]


def _sample(rows: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Prototypes first, then a random tail so a second cluster can still show."""
    ranked = rows.sort_values("oof_conf", ascending=False)
    proto = ranked.head(min(N_PROTOTYPE, len(ranked)))
    rest = ranked.iloc[len(proto) :]
    n_rand = min(SAMPLE_SIZE - len(proto), len(rest))
    if n_rand > 0:
        rest = rest.iloc[rng.permutation(len(rest))[:n_rand]]
        return pd.concat([proto, rest], ignore_index=True)
    return proto.reset_index(drop=True)


def plan(run_id: str, division: str = "01") -> list[dict]:
    """One batch per leaf: its sample, its planted foreigners, its alternatives."""
    oof = pd.read_parquet(run_dir(run_id) / "oof.parquet")
    oof = oof[(oof["division"] == division) & (oof["oof_status"] == "ok")].copy()
    rng = np.random.default_rng(SEED)

    sizes = oof["code"].value_counts()
    leaves = [c for c in sizes.index if sizes[c] >= MIN_LEAF_ROWS]

    out = []
    for leaf in leaves:
        alts = _confusable(oof, leaf)
        members = _sample(oof[oof["code"] == leaf], rng)

        pool = oof[oof["code"].isin(alts)] if alts else oof[oof["code"] != leaf]
        n_ctrl = min(N_CONTROLS, len(pool))
        ctrl = (
            pool.iloc[rng.permutation(len(pool))[:n_ctrl]] if n_ctrl else pool.head(0)
        )

        rows = pd.concat([members, ctrl], ignore_index=True)
        rows = rows.iloc[rng.permutation(len(rows))].reset_index(drop=True)
        out.append(
            {
                "leaf": leaf,
                "alternatives": alts,
                "rows": rows,
                "n_members": int(len(members)),
                "leaf_size": int(sizes[leaf]),
                "control_expected": dict(
                    zip(ctrl["gold_row_id"], ctrl["code"], strict=False)
                ),
            }
        )
    return out


def _prompt(leaf: str, alts: list[str]) -> str:
    context = coicop_taxonomy.load_coicop_context(frozenset([leaf, *alts]))
    return "\n".join(
        [
            f"# Does COICOP {leaf} cover these products?",
            "",
            f"Every product below is currently filed under **{leaf}**. Some may not",
            "belong there. Judge each product against the definition, one at a time.",
            "",
            "## Definitions",
            "",
            context,
            "",
            "## Task",
            "",
            f"For each product: does it belong under {leaf}?",
            "",
            f"- `belongs: true` -> set `correct_code` to {leaf}.",
            "- `belongs: false` -> set `correct_code` to the leaf it *should* be in.",
            "  Prefer one of the alternatives above, but any COICOP leaf is allowed.",
            "  Answer with a leaf code, never an intermediate node.",
            "",
            "Judge the product, not the leaf. Do not assume the current filing is",
            "right, and do not assume it is wrong — some batches are entirely",
            "correct and some are not.",
            "",
            "## Output",
            "",
            'A single JSON object: `{"verdicts": [{"gold_row_id": "...", '
            '"belongs": true, "correct_code": "...", "reason": "..."}, ...]}`',
            "",
            "Keep `reason` to one short clause. Return every input line.",
        ]
    )


def export(run_id: str, division: str = "01") -> dict:
    """Write one JSONL + prompt per leaf under the run's ``leaf_batches/``."""
    plans = plan(run_id, division=division)
    bdir = ensure_run_dir(run_id) / LEAF_DIR
    bdir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for i, b in enumerate(plans):
        name = f"leaf_{i:03d}.jsonl"
        lines = [
            json.dumps(
                {
                    "gold_row_id": r["gold_row_id"],
                    "product_name": str(r["product_name"]),
                    "country": r.get("country"),
                },
                ensure_ascii=False,
            )
            for _, r in b["rows"].iterrows()
        ]
        (bdir / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        prompt_name = f"leaf_{i:03d}.md"
        (bdir / prompt_name).write_text(
            _prompt(b["leaf"], b["alternatives"]), encoding="utf-8"
        )
        manifest.append(
            {
                "file": name,
                "prompt": prompt_name,
                "leaf": b["leaf"],
                "alternatives": b["alternatives"],
                "leaf_size": b["leaf_size"],
                "n_lines": int(len(b["rows"])),
                "n_members": b["n_members"],
                "control_expected": b["control_expected"],
            }
        )

    (bdir / MANIFEST_FILE).write_text(
        json.dumps({"run_id": run_id, "batches": manifest}, indent=2, default=str),
        encoding="utf-8",
    )
    return {
        "run_id": run_id,
        "division": division,
        "n_leaves": len(manifest),
        "n_rows": sum(m["n_lines"] for m in manifest),
        "n_controls": sum(len(m["control_expected"]) for m in manifest),
        "rows_represented": sum(m["leaf_size"] for m in manifest),
        "batch_dir": str(bdir),
    }


def _one(bdir: Path, entry: dict, schema_path: Path, model: str) -> dict:
    from prices.enrich.gold_audit import codex_pass

    out = bdir / VERDICTS_DIR / f"verdict_{entry['file'].replace('.jsonl', '')}.json"
    if out.exists():
        prior = json.loads(out.read_text(encoding="utf-8")).get("verdicts", [])
        if prior:
            return {"file": entry["file"], "skipped": True}

    rows = [
        json.loads(ln)
        for ln in (bdir / entry["file"]).read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    instructions = (bdir / entry["prompt"]).read_text(encoding="utf-8")
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    raw = codex_pass._codex(
        f"{instructions}\n\n## Products\n\n{body}\n", schema_path, model
    )
    wanted = {r["gold_row_id"] for r in rows}
    verdicts = [v for v in raw if v.get("gold_row_id") in wanted]
    out.write_text(
        json.dumps(
            {
                "batch": entry["file"],
                "leaf": entry["leaf"],
                "model": model,
                "n_expected": len(rows),
                "n_returned": len(verdicts),
                "verdicts": verdicts,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"file": entry["file"], "leaf": entry["leaf"], "n_returned": len(verdicts)}


def run(run_id: str, jobs: int = 4, model: str | None = None, limit: int | None = None):
    """Adjudicate every exported leaf, `jobs` codex processes at a time.

    Each batch is an independent subprocess, so the pool is pure wall-clock win;
    a batch whose verdict file exists is skipped, so a killed run resumes."""
    import tempfile

    from prices.enrich.gold_audit import codex_pass

    model = model or codex_pass.MODEL
    bdir = run_dir(run_id) / LEAF_DIR
    manifest = json.loads((bdir / MANIFEST_FILE).read_text(encoding="utf-8"))["batches"]
    if limit:
        manifest = manifest[:limit]
    (bdir / VERDICTS_DIR).mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as sf:
        json.dump(SCHEMA, sf)
        schema_path = Path(sf.name)

    done, failed = [], []
    try:
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            futs = {
                ex.submit(_one, bdir, e, schema_path, model): e["file"]
                for e in manifest
            }
            for f, name in futs.items():
                try:
                    done.append(f.result())
                except Exception as exc:  # noqa: BLE001
                    failed.append({"file": name, "error": str(exc)[:200]})
    finally:
        schema_path.unlink(missing_ok=True)

    return {
        "run_id": run_id,
        "model": model,
        "jobs": jobs,
        "n_done": len([d for d in done if not d.get("skipped")]),
        "n_skipped": len([d for d in done if d.get("skipped")]),
        "n_failed": len(failed),
        "failures": failed[:10],
    }


def report(run_id: str) -> dict:
    """Score the planted foreigners, then rank leaves by rejection rate.

    Writes nothing. A control that the adjudicator says `belongs` is a product
    provably filed elsewhere being waved through — the signal that it is
    rubber-stamping rather than reading. Read this before trusting any leaf."""
    bdir = run_dir(run_id) / LEAF_DIR
    manifest = json.loads((bdir / MANIFEST_FILE).read_text(encoding="utf-8"))["batches"]
    meta = {m["file"]: m for m in manifest}

    leaves, n_ctrl, n_waved = [], 0, 0
    for f in sorted((bdir / VERDICTS_DIR).glob("verdict_leaf_*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        m = meta.get(data["batch"], {})
        # Controls are scored per batch: a row planted as a foreigner in one leaf
        # is an ordinary member of its own, and a global id set conflates the two.
        controls = m.get("control_expected", {})
        rejected = members = 0
        for p in data["verdicts"]:
            rid = str(p["gold_row_id"])
            if rid in controls:
                n_ctrl += 1
                n_waved += int(bool(p["belongs"]))
                continue
            members += 1
            rejected += int(not p["belongs"])
        if members:
            leaves.append(
                {
                    "leaf": data["leaf"],
                    "leaf_size": m.get("leaf_size"),
                    "n_judged": members,
                    "n_rejected": rejected,
                    "reject_rate": round(rejected / members, 3),
                }
            )

    leaves.sort(key=lambda x: (-x["reject_rate"], -(x["leaf_size"] or 0)))
    suspect = [x for x in leaves if x["reject_rate"] >= 0.5]
    return {
        "run_id": run_id,
        "n_leaves": len(leaves),
        "n_controls": n_ctrl,
        "n_controls_waved_through": n_waved,
        "control_wave_rate": round(n_waved / n_ctrl, 3) if n_ctrl else None,
        "n_leaves_majority_rejected": len(suspect),
        "rows_in_those_leaves": sum(x["leaf_size"] or 0 for x in suspect),
        "worst_leaves": leaves[:25],
    }
