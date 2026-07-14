"""Round-N gold-expansion candidate sampler (div-01 F&B, reachable-only).

Generalizes build_gold_round1_candidates.py to any round >= 2 and wires in the
mined lexicons from mine_ngram_patterns.py:

  - ACCEPT patterns (require-list): for leaves that earned true positives, a
    candidate name must contain one of the leaf's high-purity accept n-grams.
    This lifts on-target rate far above single-token anchoring (round 1 was only
    ~14% exact-leaf on-target). Leaves without accept patterns fall back to the
    round-1 anchor-token lexical miner.
  - VETO patterns (exclude): a name carrying a leaf's wild-labeled trap n-gram is
    disqualified for that leaf (e.g. "ball bearing" off 01.1.7.2.9).

Prior-round gold (main + extra + every gold_v5_round*_final) drives the
under-covered set and the disjoint-name exclusion, so each round fills what the
previous ones left thin. IDs continue past the last candidate; batches continue
past the last batch on disk. Labelers stay blind — the target-leaf hint lives
only in the candidates parquet + manifest, never in the batch CSV.

Lexicons are gated to div-01, purity>=0.5, no digit tokens (drops pack junk like
"rice 5kg" and the non-food rental/watsons patterns the miner pulled from
standing all-division gold).
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
ACCEPT_PATH = GOLD_DIR / "accept_patterns.parquet"
VETO_PATH = GOLD_DIR / "veto_lexicon.parquet"

BASE_N_EXISTING = 8000
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
MAX_PER_BRAND = 2  # cap same-brand (digit-stripped) near-dupes per leaf
NONLATIN_FRAC = 0.30  # round-level quota
SEED = 20260715

ACCEPT_MIN_PURITY = 0.5  # a require-list n-gram must point to <=2 leaves
ACCEPT_WEIGHT = 100  # accept-ngram hit dominates anchor-token hit in assignment

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
    "drinks",
    "drink",
    "bar",
    "ready",
}

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
_DIGIT = re.compile(r"\d")
# n-gram unit tokens stripped identically to mine_ngram_patterns._content_tokens
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
    "gm",
    "gr",
    "kgs",
    "ltr",
    "pieces",
    "piece",
    "count",
    "s",
}
CORPUS_MAX_FRAC = 0.012
EXCLUDE_RX = re.compile(
    r"\b(cat|dog|dogs|cats|puppy|kitten|pet|pets|feline|canine|aquarium|"
    r"diffuser|figure|figurine|nendoroid|toy|supplement|shampoo)\b"
)


def _tok(text: str) -> list[str]:
    return _WORD.findall(str(text).lower())


def _content_tokens(name: str) -> list[str]:
    toks = _tok(name)
    return [t for t in toks if not t.isdigit() and t not in _UNIT and len(t) > 1]


def _name_ngrams(name: str) -> set[str]:
    toks = _content_tokens(name)
    out = set()
    for n in (2, 3):
        for i in range(len(toks) - n + 1):
            out.add(" ".join(toks[i : i + n]))
    return out


def _norm_key(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(name).lower())).strip()


def _brand_key(name: str) -> str:
    """Norm-key with digits stripped, so size/pack variants of the same product
    ("so good almond milk 1l" / "... 2l") collapse to one brand-key. Caps how many
    near-duplicate SKUs a single fat pattern (usually a brand) can contribute."""
    return re.sub(r"\s+", " ", re.sub(r"\d+", "", _norm_key(name))).strip()


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


def _prior_gold_frames() -> list[pd.DataFrame]:
    rounds = sorted(GOLD_DIR.glob("gold_v5_round*_final.parquet"))
    return [pd.read_parquet(p) for p in (GOLD_MAIN, GOLD_EXTRA, *rounds) if p.exists()]


def _gold_leaf_counts() -> Counter:
    g = pd.concat(_prior_gold_frames(), ignore_index=True)
    g["code"] = g["code"].astype(str)
    leaf = g[(g["verdict"] == "leaf") & g["code"].str.startswith("01.")]
    return Counter(leaf["code"])


def _gold_names() -> set:
    frames = [f[["product_name"]] for f in _prior_gold_frames()]
    g = pd.concat(frames, ignore_index=True)
    return {_norm_key(n) for n in g["product_name"].astype(str)}


def _load_accept() -> dict:
    """leaf -> set of require-list n-grams (div-01, pure, no-digit)."""
    if not ACCEPT_PATH.exists():
        return {}
    a = pd.read_parquet(ACCEPT_PATH)
    a = a[
        a["coicop_leaf"].str.startswith("01.")
        & (a["leaf_purity"] >= ACCEPT_MIN_PURITY)
        & (~a["pattern"].str.contains(_DIGIT))
    ]
    out = defaultdict(set)
    for code, pat in zip(a["coicop_leaf"], a["pattern"]):
        out[code].add(pat)
    return dict(out)


def _load_veto() -> dict:
    """leaf -> set of trap n-grams (div-01)."""
    if not VETO_PATH.exists():
        return {}
    v = pd.read_parquet(VETO_PATH)
    v = v[v["coicop_leaf"].str.startswith("01.")]
    out = defaultdict(set)
    for code, pat in zip(v["coicop_leaf"], v["pattern"]):
        out[code].add(pat)
    return dict(out)


def _build_anchors(leaves: dict, corpus_df: Counter, n_names: int) -> dict:
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
    df = df.drop_duplicates("product_name_original").reset_index(drop=True)
    return df


def _corpus_token_df(corpus: pd.DataFrame) -> Counter:
    df = Counter()
    for name in corpus["product_name_original"].to_numpy():
        for t in set(_tok(name)):
            df[t] += 1
    return df


def _match_corpus(corpus, anchors, accept, veto, want, exclude) -> dict:
    """Scan each unique name once. A leaf that HAS a require-list matches only via
    its accept n-grams (hard require, weight ACCEPT_WEIGHT); a leaf without one
    falls back to anchor tokens. This keeps a bare anchor ("almond") from leaking
    almond-meal/cereal/cosmetics into a require-listed leaf. Any L whose veto n-gram
    appears is disqualified. Assign to the best-scoring wanted leaf. Returns
    leaf -> list of corpus row-idx."""
    tok_to_leaves = defaultdict(list)
    for code, toks in anchors.items():
        if code in want and code not in accept:  # anchor-mode leaves only
            for t in toks:
                tok_to_leaves[t].append(code)
    ng_to_leaves = defaultdict(list)
    for code, ngs in accept.items():
        if code in want:
            for g in ngs:
                ng_to_leaves[g].append(code)
    anchor_set = set(tok_to_leaves)
    accept_set = set(ng_to_leaves)

    hits = defaultdict(list)
    names = corpus["product_name_original"].to_numpy()
    for i, name in enumerate(names):
        low = name.lower()
        if EXCLUDE_RX.search(low):
            continue
        toks = set(_tok(low))
        toks |= {SYNONYMS[t] for t in toks if t in SYNONYMS}
        ngs = _name_ngrams(name)
        present_ng = ngs & accept_set
        present_tok = toks & anchor_set
        if not present_ng and not present_tok:
            continue
        if _norm_key(name) in exclude:
            continue
        score = Counter()
        for g in present_ng:
            for code in ng_to_leaves[g]:
                score[code] += ACCEPT_WEIGHT
        for t in present_tok:
            for code in tok_to_leaves[t]:
                score[code] += 1
        # veto: drop any leaf whose trap n-gram is in this name
        for code in list(score):
            if ngs & veto.get(code, frozenset()):
                del score[code]
        if not score:
            continue
        best = max(score.values())
        for code, s in score.items():
            if s == best:
                hits[code].append(i)
    return hits


def _next_ids() -> tuple:
    cand = sorted(GOLD_DIR.glob("gold_round*_candidates.parquet"))
    last = BASE_N_EXISTING - 1
    for p in cand:
        ids = pd.read_parquet(p, columns=["gold_row_id"])["gold_row_id"]
        m = ids.str.extract(r"gv5-(\d+)")[0].astype(int).max()
        last = max(last, int(m))
    n_existing = last + 1
    batches = [
        int(p.stem.split("_")[-1]) for p in BATCH_DIR.glob("gold_v5_batch_*.csv")
    ]
    first_batch = (max(batches) + 1) if batches else 0
    return n_existing, first_batch


def build(round_no: int, dry_run: bool) -> tuple:
    rng = np.random.default_rng(SEED + round_no)
    n_existing, first_batch = _next_ids()
    leaves = _load_leaves()
    counts = _gold_leaf_counts()
    exclude = _gold_names()
    accept = _load_accept()
    veto = _load_veto()
    corpus = _load_corpus()
    corpus_df = _corpus_token_df(corpus)
    anchors = _build_anchors(leaves, corpus_df, len(corpus))

    want = {c for c in leaves if counts.get(c, 0) < TARGET_PER_LEAF}
    want &= set(anchors) | set(accept)
    hits = _match_corpus(corpus, anchors, accept, veto, want, exclude)

    names = corpus["product_name_original"].to_numpy()
    chosen_rows, chosen_leaf, chosen_script, chosen_mode = [], [], [], []
    picked_keys = set()
    per_leaf_nonlatin = int(round(N_PER_LEAF * NONLATIN_FRAC))

    for code in sorted(want):
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
        # fill respecting a per-brand cap so one fat brand pattern cannot supply
        # more than MAX_PER_BRAND size-variant near-duplicates for this leaf
        take = []
        brand_ct = Counter()

        def _fill(pool, limit):
            for i in pool:
                if len(take) >= limit:
                    break
                bk = _brand_key(names[i])
                if brand_ct[bk] >= MAX_PER_BRAND:
                    continue
                brand_ct[bk] += 1
                take.append(i)

        _fill(non, per_leaf_nonlatin)
        _fill(lat, N_PER_LEAF)
        _fill(non, N_PER_LEAF)  # backfill from remaining non-latin
        mode = "accept" if code in accept else "anchor"
        for i in take:
            picked_keys.add(_norm_key(names[i]))
            chosen_rows.append(i)
            chosen_leaf.append(code)
            chosen_script.append("nonlatin" if _is_nonlatin(names[i]) else "latin")
            chosen_mode.append(mode)

    out = corpus.iloc[chosen_rows].reset_index(drop=True)
    out["target_leaf_hint"] = chosen_leaf
    out["script"] = chosen_script
    out["match_mode"] = chosen_mode
    out["gold_row_id"] = [f"gv5-{n_existing + i:05d}" for i in range(len(out))]

    n_non = int((out["script"] == "nonlatin").sum())
    n_acc = int((out["match_mode"] == "accept").sum())
    n_batches = (len(out) + BATCH_SIZE - 1) // BATCH_SIZE
    summary = {
        "round": round_no,
        "reachable_leaves": len(leaves),
        "under_covered_wanted": len(want),
        "leaves_with_candidates": int(out["target_leaf_hint"].nunique())
        if len(out)
        else 0,
        "n_candidates": int(len(out)),
        "via_accept_requirelist": n_acc,
        "via_anchor_fallback": int(len(out) - n_acc),
        "nonlatin": n_non,
        "nonlatin_frac": round(n_non / max(len(out), 1), 3),
        "n_batches": n_batches,
        "gold_row_id_start": n_existing,
        "first_batch": first_batch,
    }
    if dry_run:
        return out, summary

    cand_path = GOLD_DIR / f"gold_round{round_no}_candidates.parquet"
    out.to_parquet(cand_path, index=False)
    for b, start in enumerate(range(0, len(out), BATCH_SIZE)):
        out.iloc[start : start + BATCH_SIZE][BATCH_COLS].to_csv(
            BATCH_DIR / f"gold_v5_batch_{first_batch + b:03d}.csv", index=False
        )
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED + round_no,
        "scope": "div-01 reachable-only (hard-park 18 non-retail)",
        "target_per_leaf": TARGET_PER_LEAF,
        "n_per_leaf": N_PER_LEAF,
        "nonlatin_quota": NONLATIN_FRAC,
        "accept_min_purity": ACCEPT_MIN_PURITY,
        "gold_row_id_range": [out["gold_row_id"].iloc[0], out["gold_row_id"].iloc[-1]],
        "batch_range": [first_batch, first_batch + n_batches - 1],
        "hard_park": sorted(HARD_PARK),
        **summary,
        "per_leaf_counts": out["target_leaf_hint"].value_counts().to_dict(),
    }
    (GOLD_DIR / f"gold_round{round_no}_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return out, manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    out, info = build(args.round, args.dry_run)
    print(
        json.dumps({k: v for k, v in info.items() if k != "per_leaf_counts"}, indent=2)
    )
    if not args.dry_run:
        print(
            f"\nwrote {len(out)} candidates -> gold_round{args.round}_candidates.parquet"
        )
        print(f"batches {info['batch_range']} -> {BATCH_DIR}")


if __name__ == "__main__":
    main()
