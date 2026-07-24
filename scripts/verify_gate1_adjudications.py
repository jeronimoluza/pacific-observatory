"""Independent verifier for Gate-1 adjudication outputs.

Checks each adjud_out_NNN.json against its input batch: row coverage, enum
validity, leaf-code validity vs the taxonomy, and RECOMPUTES matches_candidate
from scratch (never trusting the adjudicator's self-report). Prints a per-batch
table and a global rollup; exits non-zero if any batch fails a hard check.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prices.enrich import config  # noqa: E402
from prices.enrich.coicop_taxonomy import load_taxonomy_index  # noqa: E402

GATE_DIR = config.REPO_ROOT / "data" / "prices" / "enrich" / "gold" / "gate1"
BATCH_DIR = GATE_DIR / "adjud_batches"
OUT_DIR = GATE_DIR / "adjudications"
VERDICTS = {"leaf", "exclude", "ambiguous_class"}


def _key(v, c):
    return (str(v).strip(), str(c or "").strip())


def verify():
    leaves, _ = load_taxonomy_index()
    batches = sorted(BATCH_DIR.glob("adjud_batch_*.json"))
    tot = {"rows": 0, "cand1": 0, "cand2": 0, "neither": 0, "selfreport_mismatch": 0}
    verdict_tot = {v: 0 for v in VERDICTS}
    failures = []
    present = 0

    print(
        f"{'batch':>6} {'n':>4} {'invalid':>7} {'badenum':>7} {'miss':>5} "
        f"{'c1':>4} {'c2':>4} {'neither':>7} {'selfmism':>8}"
    )
    for bpath in batches:
        b = bpath.stem.split("_")[-1]
        opath = OUT_DIR / f"adjud_out_{b}.json"
        inp = json.loads(bpath.read_text())
        by_id = {r["gold_row_id"]: r for r in inp}
        if not opath.exists():
            print(f"{b:>6} {'--':>4}  (no output yet)")
            continue
        present += 1
        out = json.loads(opath.read_text())
        seen = set()
        invalid = badenum = c1 = c2 = neither = selfmism = 0
        for o in out:
            rid = o.get("gold_row_id")
            seen.add(rid)
            v = str(o.get("verdict", "")).strip()
            code = str(o.get("code", "") or "").strip()
            if v not in VERDICTS:
                badenum += 1
            else:
                verdict_tot[v] = verdict_tot.get(v, 0) + 1
            if v == "leaf" and code not in leaves:
                invalid += 1
            src = by_id.get(rid)
            if src:
                fk = _key(v, code)
                k1 = _key(src["candidate_1"]["verdict"], src["candidate_1"]["code"])
                k2 = _key(src["candidate_2"]["verdict"], src["candidate_2"]["code"])
                match = "1" if fk == k1 else ("2" if fk == k2 else "neither")
                if match == "1":
                    c1 += 1
                elif match == "2":
                    c2 += 1
                else:
                    neither += 1
                if str(o.get("matches_candidate", "")).strip() != match:
                    selfmism += 1
        missing = set(by_id) - seen
        n = len(out)
        print(
            f"{b:>6} {n:>4} {invalid:>7} {badenum:>7} {len(missing):>5} "
            f"{c1:>4} {c2:>4} {neither:>7} {selfmism:>8}"
        )
        if invalid or badenum or missing or n != len(inp):
            failures.append(
                (
                    b,
                    {
                        "invalid": invalid,
                        "badenum": badenum,
                        "missing": len(missing),
                        "n": n,
                        "expected": len(inp),
                    },
                )
            )
        tot["rows"] += n
        tot["cand1"] += c1
        tot["cand2"] += c2
        tot["neither"] += neither
        tot["selfreport_mismatch"] += selfmism

    print("\n=== rollup ===")
    print(
        f"batches with output: {present}/{len(batches)}   rows adjudicated: {tot['rows']}"
    )
    print(f"verdicts: {verdict_tot}")
    print(
        f"matches (recomputed): candidate_1={tot['cand1']} candidate_2={tot['cand2']} "
        f"neither={tot['neither']}"
    )
    print(f"self-report mismatches: {tot['selfreport_mismatch']}")
    if failures:
        print("\nFAILURES:")
        for b, d in failures:
            print(f"  batch {b}: {d}")
        return 1
    print(
        "\nALL PRESENT BATCHES PASS hard checks (coverage + valid codes + valid enums)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(verify())
