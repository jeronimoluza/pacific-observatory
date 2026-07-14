"""Round-1 gold-expansion candidate sampler (div-01 F&B, reachable-only).

Leaf-TARGETED lexical mining from the 1.4M-unique corpus to fill every REACHABLE
division-01 deep leaf toward >=10 gold labels, equal-increment per round. Emits
dispatch-ready batch CSVs in the existing schema so gold_v5_label_pass_a/b,
build_gold_v5_gate1, and build_gold_v5_final run unchanged. Labelers stay blind:
the target-leaf HINT lives only in the candidates parquet + manifest, never in the
batch CSV.

Scope decisions (LOCKED 2026-07-14): reachable-only — HARD_PARK the ~18
unambiguously non-retail leaves; every other div-01 leaf is attempted. 70/30
latin/non-latin is a ROUND-level quota. Disjoint from existing gold by
normalized name key.
"""

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = ROOT / "data" / "prices" / "enrich" / "gold"
BATCH_DIR = GOLD_DIR / "batches"
CORPUS = ROOT / "data" / "prices" / "_enrich" / "products_input.parquet"
LEAVES_TXT = GOLD_DIR / "coicop_leaves.txt"
GOLD_MAIN = GOLD_DIR / "gold_v5_8k_final.parquet"
GOLD_EXTRA = GOLD_DIR / "gold_v5_fnb_extra.parquet"

CANDIDATES_PATH = GOLD_DIR / "gold_round1_candidates.parquet"
MANIFEST_PATH = GOLD_DIR / "gold_round1_manifest.json"

N_EXISTING = 8000
FIRST_NEW_BATCH = 54
BATCH_SIZE = 150
BATCH_COLS = [
    "gold_row_id",
    "product_name_original",
    "country",
    "source",
    "channel",
    "category",
    "declared_coicop_codes",
    "price",
]

TARGET_PER_LEAF = 10  # >=10 gold labels per reachable leaf
N_PER_LEAF = 6  # candidates dispatched per under-covered leaf this round
NONLATIN_FRAC = 0.30  # round-level quota
SEED = 20260714

# ~18 unambiguously non-retail div-01 leaves — hard-parked, never sampled.
HARD_PARK = {
    "01.1.2.1.1",
    "01.1.2.1.2",
    "01.1.2.1.3",
    "01.1.2.1.4",
    "01.1.2.1.5",
    "01.1.2.1.9",
    "01.3.0.0.0",
    "01.1.4.1.2",
    "01.1.4.1.3",
    "01.1.4.1.4",
    "01.1.4.1.9",
    "01.1.1.1.1",
    "01.1.1.1.3",
    "01.1.1.1.5",
    "01.1.1.1.6",
    "01.1.1.1.8",
    "01.1.1.1.9",
}

# Grammatical + non-discriminating tokens stripped before anchoring. Form words
# (canned/frozen/dried) are KEPT — they distinguish preserved-form leaves; the
# document-frequency filter already down-weights the truly generic ones.
STOP = {
    "or",
    "and",
    "of",
    "in",
    "the",
    "a",
    "n",
    "e",
    "c",
    "nec",
    "nec.",
    "other",
    "including",
    "similar",
    "products",
    "product",
    "parts",
    "all",
    "forms",
    "form",
    "by",
    "with",
    "without",
    "various",
    "etc",
    "fresh",
    "chilled",
    # generic beverage/format words that are never a div-01 leaf's ESSENTIAL
    # distinctive term (the real beverage leaves anchor on cocoa/tea/coffee/juice)
    "drinks",
    "drink",
    "bar",
    "ready",
}

# Small high-value synonym boosts: retail vocabulary -> a leaf anchor token.
SYNONYMS = {
    "peanut": "groundnuts",
    "peanuts": "groundnuts",
    "eggplant": "aubergines",
    "aubergine": "aubergines",
    "capsicum": "peppers",
    "corn": "maize",
    "cornmeal": "maize",
    "zucchini": "courgettes",
    "courgette": "courgettes",
    "prawn": "shrimps",
    "prawns": "shrimps",
    "shrimp": "shrimps",
    "mandarin": "tangerines",
    "clementine": "tangerines",
    "cilantro": "coriander",
    "garbanzo": "chickpeas",
    "yoghurt": "yogurt",
    "soya": "soy",
}

_WORD = re.compile(r"[a-z0-9]+")

# Anchors appearing in more than this fraction of unique corpus names have no
# discriminating power (e.g. "milk", "meat", "drinks", "fresh") — dropped.
CORPUS_MAX_FRAC = 0.012
# Non-human-food contexts that swamp food anchors — pet food dominates
# "canned meat"/"tuna" matches; the rest are obvious non-grocery noise.
EXCLUDE_RX = re.compile(
    r"\b(cat|dog|dogs|cats|puppy|kitten|pet|pets|feline|canine|aquarium|"
    r"diffuser|figure|figurine|nendoroid|toy|supplement|shampoo)\b"
)


def _tok(text: str) -> list[str]:
    return _WORD.findall(str(text).lower())


def _norm_key(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(name).lower())).strip()


def _is_nonlatin(name: str) -> bool:
    for ch in str(name):
        if ch.isalpha():
            try:
                if "LATIN" not in unicodedata.name(ch):
                    return True
            except ValueError:
                continue
    return False


def _load_leaves() -> dict:
    out = {}
    for line in LEAVES_TXT.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        code, name = line.split("\t", 1)
        if code.startswith("01.") and code not in HARD_PARK:
            out[code] = name
    return out


def _gold_leaf_counts() -> Counter:
    frames = [pd.read_parquet(p) for p in (GOLD_MAIN, GOLD_EXTRA) if p.exists()]
    g = pd.concat(frames, ignore_index=True)
    g["code"] = g["code"].astype(str)
    leaf = g[(g["verdict"] == "leaf") & g["code"].str.startswith("01.")]
    return Counter(leaf["code"])


def _gold_names() -> set:
    frames = [
        pd.read_parquet(p, columns=["product_name"])
        for p in (GOLD_MAIN, GOLD_EXTRA)
        if p.exists()
    ]
    g = pd.concat(frames, ignore_index=True)
    return {_norm_key(n) for n in g["product_name"].astype(str)}


def _build_anchors(leaves: dict, corpus_df: Counter, n_names: int) -> dict:
    """Per leaf, the distinctive tokens a candidate name must contain (whole-word).
    Distinctive = lowest document-frequency across leaf names, THEN gated to drop
    anchors that are hyper-common in the corpus (no discriminating power)."""
    max_corpus = CORPUS_MAX_FRAC * max(n_names, 1)
    df = Counter()
    leaf_tokens = {}
    for code, name in leaves.items():
        toks = [t for t in _tok(name) if t not in STOP and not t.isdigit()]
        leaf_tokens[code] = toks
        for t in set(toks):
            df[t] += 1
    anchors = {}
    for code, toks in leaf_tokens.items():
        if not toks:
            continue
        picked = None
        for cutoff in (1, 2, 4):
            distinctive = [t for t in toks if df[t] <= cutoff]
            gated = [t for t in distinctive if corpus_df.get(t, 0) <= max_corpus]
            if gated:
                picked = sorted(set(gated))
                break
        if picked is None:
            # keep the single most corpus-distinctive token so the leaf still mines
            picked = [min(toks, key=lambda t: corpus_df.get(t, 0))]
        anchors[code] = picked
    return anchors


def _load_corpus() -> pd.DataFrame:
    cols = [
        "product_name_original",
        "country",
        "source",
        "channel",
        "category",
        "declared_coicop_codes",
        "price",
    ]
    df = pd.read_parquet(CORPUS, columns=cols)
    df["product_name_original"] = df["product_name_original"].astype(str)
    # one representative row per unique name
    df = df.drop_duplicates("product_name_original").reset_index(drop=True)
    return df


def _corpus_token_df(corpus: pd.DataFrame) -> Counter:
    df = Counter()
    for name in corpus["product_name_original"].to_numpy():
        for t in set(_tok(name)):
            df[t] += 1
    return df


def _match_corpus(corpus: pd.DataFrame, anchors: dict, exclude: set) -> dict:
    """anchor token -> leaves wanting it; scan each unique name once, assign to the
    leaf whose anchor set the name best matches. Returns leaf -> list of row-idx."""
    token_to_leaves = defaultdict(list)
    for code, toks in anchors.items():
        for t in toks:
            token_to_leaves[t].append(code)
    anchor_set = set(token_to_leaves)

    hits = defaultdict(list)
    names = corpus["product_name_original"].to_numpy()
    for i, name in enumerate(names):
        low = name.lower()
        if EXCLUDE_RX.search(low):
            continue
        toks = set(_tok(name))
        toks |= {SYNONYMS[t] for t in toks if t in SYNONYMS}
        present = toks & anchor_set
        if not present:
            continue
        if _norm_key(name) in exclude:
            continue
        score = Counter()
        for t in present:
            for code in token_to_leaves[t]:
                score[code] += 1
        best = max(score.values())
        for code, s in score.items():
            if s == best:
                hits[code].append(i)
    return hits


def build(dry_run: bool) -> tuple:
    rng = np.random.default_rng(SEED)
    leaves = _load_leaves()
    counts = _gold_leaf_counts()
    exclude = _gold_names()
    corpus = _load_corpus()
    corpus_df = _corpus_token_df(corpus)
    anchors = _build_anchors(leaves, corpus_df, len(corpus))

    under = {c for c in leaves if counts.get(c, 0) < TARGET_PER_LEAF and c in anchors}
    hits = _match_corpus(corpus, anchors, exclude)

    names = corpus["product_name_original"].to_numpy()
    chosen_rows, chosen_leaf, chosen_script = [], [], []
    picked_keys = set()
    per_leaf_nonlatin = int(round(N_PER_LEAF * NONLATIN_FRAC))  # ~2

    for code in sorted(under):
        idxs = hits.get(code, [])
        if not idxs:
            continue
        rng.shuffle(idxs)
        lat, non = [], []
        for i in idxs:
            key = _norm_key(names[i])
            if key in picked_keys:
                continue
            (non if _is_nonlatin(names[i]) else lat).append(i)
        take = []
        take += non[:per_leaf_nonlatin]
        take += lat[: N_PER_LEAF - len(take)]
        if len(take) < N_PER_LEAF:  # backfill from whichever remains
            take += non[
                per_leaf_nonlatin : per_leaf_nonlatin + (N_PER_LEAF - len(take))
            ]
        for i in take:
            picked_keys.add(_norm_key(names[i]))
            chosen_rows.append(i)
            chosen_leaf.append(code)
            chosen_script.append("nonlatin" if _is_nonlatin(names[i]) else "latin")

    out = corpus.iloc[chosen_rows].reset_index(drop=True)
    out["target_leaf_hint"] = chosen_leaf
    out["script"] = chosen_script
    out["gold_row_id"] = [f"gv5-{N_EXISTING + i:05d}" for i in range(len(out))]

    n_non = int((out["script"] == "nonlatin").sum())
    summary = {
        "reachable_leaves": len(leaves),
        "under_covered_attempted": len(under),
        "leaves_with_candidates": out["target_leaf_hint"].nunique(),
        "n_candidates": int(len(out)),
        "nonlatin": n_non,
        "nonlatin_frac": round(n_non / max(len(out), 1), 3),
        "n_batches": (len(out) + BATCH_SIZE - 1) // BATCH_SIZE,
    }
    if dry_run:
        return out, summary

    out.to_parquet(CANDIDATES_PATH, index=False)
    for b, start in enumerate(range(0, len(out), BATCH_SIZE)):
        out.iloc[start : start + BATCH_SIZE][BATCH_COLS].to_csv(
            BATCH_DIR / f"gold_v5_batch_{FIRST_NEW_BATCH + b:03d}.csv", index=False
        )
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "round": 1,
        "seed": SEED,
        "scope": "div-01 reachable-only (hard-park 18 non-retail)",
        "target_per_leaf": TARGET_PER_LEAF,
        "n_per_leaf": N_PER_LEAF,
        "nonlatin_quota": NONLATIN_FRAC,
        "gold_row_id_range": [out["gold_row_id"].iloc[0], out["gold_row_id"].iloc[-1]],
        "batch_range": [FIRST_NEW_BATCH, FIRST_NEW_BATCH + summary["n_batches"] - 1],
        "hard_park": sorted(HARD_PARK),
        **summary,
        "per_leaf_counts": out["target_leaf_hint"].value_counts().to_dict(),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out, manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    out, info = build(args.dry_run)
    print(
        json.dumps({k: v for k, v in info.items() if k != "per_leaf_counts"}, indent=2)
    )
    if not args.dry_run:
        print(f"\nwrote {len(out)} candidates -> {CANDIDATES_PATH}")
        print(f"batches {info['batch_range']} -> {BATCH_DIR}")


if __name__ == "__main__":
    main()
