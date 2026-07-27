"""Mine bigram/trigram accept-patterns + wild-trap vetoes from a labeled round pool.

Consumes a gold-expansion round's labeled candidates (target_leaf_hint from the
sampler joined to the adjudicated final label) and the standing gold, and emits
two data-derived lexicons that sharpen the NEXT round:

  - VETOES (precision): for each target leaf L, n-grams that appear in names
    SAMPLED-for-L but LABELED not-L (wild-labeled negatives), gold-validated so a
    veto never matches a known L positive. -> veto_lexicon.parquet
  - ACCEPT patterns (coverage/ROI): for each leaf, n-grams from its TRUE positives
    (round on-target + standing gold), ranked by GREEDY SET-COVER of unlabeled
    corpus rows x leaf-purity. This is the round-2 require-list, ordered so the
    fattest labels retire the most rows first. -> accept_patterns.parquet

Patterns SELECT and VETO candidate names; they are NOT gold rows. Latin n-grams
only for now (CJK pattern mining is a later enhancement).
"""

import argparse
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = ROOT / "data" / "prices" / "enrich" / "gold"
CORPUS = ROOT / "data" / "prices" / "enrich" / "products_input.parquet"
GOLD_MAIN = GOLD_DIR / "gold_v5_8k_final.parquet"
GOLD_EXTRA = GOLD_DIR / "gold_v5_fnb_extra.parquet"

VETO_OUT = GOLD_DIR / "veto_lexicon.parquet"
ACCEPT_OUT = GOLD_DIR / "accept_patterns.parquet"


def _candidates_path(round_no: int) -> Path:
    return GOLD_DIR / f"gold_round{round_no}_candidates.parquet"


def _round_final_path(round_no: int) -> Path:
    return GOLD_DIR / f"gold_v5_round{round_no}_final.parquet"


def _latest_round() -> int:
    ns = [
        int(p.stem.split("round")[1].split("_")[0])
        for p in GOLD_DIR.glob("gold_round*_candidates.parquet")
    ]
    return max(ns) if ns else 1


_WORD = re.compile(r"[a-z0-9]+")
_UNIT = {
    "g",
    "kg",
    "mg",
    "ml",
    "l",
    "cl",
    "oz",
    "lb",
    "ct",
    "pc",
    "pcs",
    "pack",
    "packs",
    "pk",
    "x",
    "cm",
    "mm",
    "pcs",
    "gm",
    "gr",
    "kgs",
    "ltr",
    "pieces",
    "piece",
    "count",
    "s",
}
MIN_VETO_SUPPORT = 2  # off-target occurrences required to emit a veto n-gram
MIN_ACCEPT_SUPPORT = 2  # positive occurrences required to emit an accept pattern


def _content_tokens(name: str) -> list[str]:
    toks = _WORD.findall(str(name).lower())
    return [t for t in toks if not t.isdigit() and t not in _UNIT and len(t) > 1]


def _ngrams(toks: list[str]) -> list[str]:
    out = []
    for n in (2, 3):
        for i in range(len(toks) - n + 1):
            out.append(" ".join(toks[i : i + n]))
    return out


def _name_ngrams(name: str) -> set[str]:
    return set(_ngrams(_content_tokens(name)))


def _load_round(round_no: int) -> pd.DataFrame:
    cand = pd.read_parquet(_candidates_path(round_no))
    fin = pd.read_parquet(_round_final_path(round_no))[
        ["gold_row_id", "verdict", "code"]
    ]
    m = cand.merge(fin, on="gold_row_id", how="left")
    m["code"] = m["code"].astype(str)
    m["target"] = m["target_leaf_hint"].astype(str)
    m["on_target"] = (m["verdict"] == "leaf") & (m["code"] == m["target"])
    return m


def _gold_positives() -> dict:
    """leaf -> set of positive product names across ALL standing gold (main + extra
    + every prior round final), verdict==leaf. Round finals fold this round's keeps
    back in so accept patterns reflect the full current gold vocabulary."""
    rounds = sorted(GOLD_DIR.glob("gold_v5_round*_final.parquet"))
    frames = [
        pd.read_parquet(p) for p in (GOLD_MAIN, GOLD_EXTRA, *rounds) if p.exists()
    ]
    g = pd.concat(frames, ignore_index=True)
    g = g[g["verdict"] == "leaf"]
    out = defaultdict(set)
    for code, name in zip(g["code"].astype(str), g["product_name"].astype(str)):
        out[code].add(name)
    return out


def mine_vetoes(rnd: pd.DataFrame, gold_pos: dict) -> pd.DataFrame:
    rows = []
    for L, sub in rnd.groupby("target"):
        off = sub[~sub["on_target"]]["product_name_original"].tolist()
        on = sub[sub["on_target"]]["product_name_original"].tolist()
        if not off:
            continue
        # n-grams that are safe positives for L (never veto these)
        safe = set()
        for nm in on:
            safe |= _name_ngrams(nm)
        for nm in gold_pos.get(L, ()):  # standing gold positives for L
            safe |= _name_ngrams(nm)
        off_ng = Counter()
        for nm in off:
            off_ng.update(_name_ngrams(nm))
        for g, sup in off_ng.items():
            if sup >= MIN_VETO_SUPPORT and g not in safe:
                rows.append(
                    {
                        "coicop_leaf": L,
                        "pattern": g,
                        "kind": "veto",
                        "support": int(sup),
                        "source": "round1_offtarget",
                    }
                )
    return pd.DataFrame(rows)


def _validate_vetoes(vetoes: pd.DataFrame, gold_pos: dict) -> pd.DataFrame:
    """Flag any veto that would match a standing gold POSITIVE name for its leaf."""
    collisions = []
    for _, r in vetoes.iterrows():
        rx = re.compile(re.escape(r["pattern"]))
        hit = sum(
            1 for nm in gold_pos.get(r["coicop_leaf"], ()) if rx.search(nm.lower())
        )
        collisions.append(hit)
    vetoes = vetoes.copy()
    vetoes["gold_positive_collisions"] = collisions
    return vetoes


def mine_accept(rnd: pd.DataFrame, gold_pos: dict) -> pd.DataFrame:
    """Per leaf, positive-name n-grams + cross-leaf purity. Corpus coverage and
    greedy set-cover added in a single corpus pass afterwards."""
    pos_by_leaf = defaultdict(list)
    for L, sub in rnd.groupby("target"):
        for nm in sub[sub["on_target"]]["product_name_original"]:
            pos_by_leaf[L].append(nm)
    for L, names in gold_pos.items():
        pos_by_leaf[L].extend(names)

    # global document-frequency of each n-gram across leaves (for purity)
    leaf_ng = {}
    df_across = Counter()
    for L, names in pos_by_leaf.items():
        c = Counter()
        for nm in names:
            c.update(_name_ngrams(nm))
        leaf_ng[L] = c
        for g in c:
            df_across[g] += 1

    rows = []
    for L, c in leaf_ng.items():
        for g, sup in c.items():
            if sup >= MIN_ACCEPT_SUPPORT:
                purity = 1.0 / df_across[g]  # 1 leaf -> 1.0; shared -> lower
                rows.append(
                    {
                        "coicop_leaf": L,
                        "pattern": g,
                        "kind": "accept",
                        "support": int(sup),
                        "leaf_purity": round(purity, 3),
                    }
                )
    return pd.DataFrame(rows)


def _corpus_coverage(patterns: set[str]) -> Counter:
    """# unique corpus names whose content-n-grams contain each pattern."""
    cov = Counter()
    df = pd.read_parquet(CORPUS, columns=["product_name_original"])
    df = df.drop_duplicates("product_name_original")
    for nm in df["product_name_original"].astype(str).to_numpy():
        ng = _name_ngrams(nm)
        for g in ng & patterns:
            cov[g] += 1
    return cov


def build(round_no: int) -> dict:
    rnd = _load_round(round_no)
    gold_pos = _gold_positives()

    vetoes = mine_vetoes(rnd, gold_pos)
    if not vetoes.empty:
        vetoes = _validate_vetoes(vetoes, gold_pos)
        vetoes = vetoes[vetoes["gold_positive_collisions"] == 0].reset_index(drop=True)
    vetoes["mined_at"] = datetime.now(timezone.utc).isoformat()
    vetoes.to_parquet(VETO_OUT, index=False)

    accept = mine_accept(rnd, gold_pos)
    cov = _corpus_coverage(set(accept["pattern"].unique()))
    accept["corpus_coverage"] = accept["pattern"].map(lambda g: int(cov.get(g, 0)))
    accept["score"] = accept["corpus_coverage"] * accept["leaf_purity"]
    accept = accept.sort_values(["coicop_leaf", "score"], ascending=[True, False])
    accept = accept.reset_index(drop=True)
    accept["mined_at"] = datetime.now(timezone.utc).isoformat()
    accept.to_parquet(ACCEPT_OUT, index=False)

    return {
        "round_rows": int(len(rnd)),
        "on_target": int(rnd["on_target"].sum()),
        "vetoes_mined": int(len(vetoes)),
        "veto_leaves": int(vetoes["coicop_leaf"].nunique()) if len(vetoes) else 0,
        "accept_patterns": int(len(accept)),
        "accept_leaves": int(accept["coicop_leaf"].nunique()) if len(accept) else 0,
        "veto_out": str(VETO_OUT),
        "accept_out": str(ACCEPT_OUT),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--round", type=int, default=None, help="round to mine (default latest)"
    )
    ap.add_argument("--show", type=int, default=25, help="preview top rows")
    args = ap.parse_args()
    info = build(args.round if args.round is not None else _latest_round())
    import json

    print(json.dumps(info, indent=2))
    v = pd.read_parquet(VETO_OUT)
    a = pd.read_parquet(ACCEPT_OUT)
    print("\n=== top vetoes by support ===")
    print(
        v.sort_values("support", ascending=False)[["coicop_leaf", "pattern", "support"]]
        .head(args.show)
        .to_string(index=False)
    )
    print("\n=== top accept patterns by score (coverage x purity) ===")
    print(
        a[a["leaf_purity"] >= 0.5][
            [
                "coicop_leaf",
                "pattern",
                "support",
                "corpus_coverage",
                "leaf_purity",
                "score",
            ]
        ]
        .head(args.show)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
