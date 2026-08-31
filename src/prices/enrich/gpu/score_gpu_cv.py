"""Score the gold div-01 CV using GPU-produced vectors, in isolation.

Points `CLASSIFIER_EMBED_CACHE_DIR` at the downloaded pod output and swaps
`CLASSIFIER_EMBED_ENSEMBLE` for a GPU block list, so the canonical Mac caches
are neither read nor written. Aborts if any gold name is missing from the
downloaded cache rather than silently falling back to encoding locally, which
would mix backends inside one run.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

from prices.enrich import config  # noqa: E402

GPU_BLOCKS: dict[str, dict] = {
    "0p6b_gpu": {
        "tag": "0p6b_gpu",
        "backend": "st",
        "model": "Qwen/Qwen3-Embedding-0.6B",
        "seq": 48,
    },
    "4b_gpu": {
        "tag": "4b_gpu",
        "backend": "st",
        "model": "Qwen/Qwen3-Embedding-4B",
        "seq": 176,
    },
    "8b_bf16": {
        "tag": "8b_bf16",
        "backend": "st",
        "model": "Qwen/Qwen3-Embedding-8B",
        "seq": 176,
    },
    "arctic_gpu": {
        "tag": "arctic_gpu",
        "backend": "st",
        "model": "Snowflake/snowflake-arctic-embed-l-v2.0",
        "seq": 48,
        "prompt": "",
    },
}

MAC_BLOCKS: dict[str, dict] = {
    b["tag"]: b for b in config.CLASSIFIER_EMBED_PRESETS["qwen3_concat"]
}
MAC_BLOCKS["arctic_l_v2"] = config.CLASSIFIER_EMBED_PRESETS["arctic_l_v2"][0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--tags", required=True, help="comma-separated block tags")
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    cache = Path(a.cache_dir)
    tags = [t.strip() for t in a.tags.split(",")]
    blocks = []
    for t in tags:
        if t in GPU_BLOCKS:
            blocks.append(GPU_BLOCKS[t])
        elif t in MAC_BLOCKS:
            blocks.append(MAC_BLOCKS[t])
        else:
            raise SystemExit(f"unknown tag {t!r}")

    config.CLASSIFIER_EMBED_CACHE_DIR = cache
    config.CLASSIFIER_EMBED_ENSEMBLE = blocks

    from prices.enrich.classifier.dataset import MIN_SUPPORT, _load_gold
    from prices.enrich.eval import head_eval

    g = _load_gold()
    g = g[(g["verdict"] == "leaf") & (g["division"] == "01")]
    vc = g["code"].value_counts()
    g = g[g["code"].isin(set(vc[vc >= MIN_SUPPORT].index))]
    names = set(g["product_name"].astype(str))

    for t in tags:
        p = cache / f"block_{t}.npz"
        if not p.exists():
            raise SystemExit(f"missing cache file {p}")
        with np.load(p, allow_pickle=False) as z:
            have = {str(k) for k in z["keys"]}
            dim = int(z["mat"].shape[1])
        miss = len(names - have)
        print(f"  {t:<12} dim={dim:<5} covers {len(names) - miss}/{len(names)}")
        if miss:
            raise SystemExit(
                f"{t}: {miss} gold names absent from the downloaded cache — "
                "refusing to encode locally and mix backends"
            )

    print(f"\n=== {a.label} :: {'+'.join(tags)} ===", flush=True)
    t0 = time.time()
    r = head_eval.run()
    r["wall_s"] = round(time.time() - t0, 1)
    r["label"] = a.label
    r["tags"] = tags
    if a.out:
        Path(a.out).write_text(json.dumps(r, indent=1))
    print(
        f"\n{a.label}: precision={r['precision']:.4f} coverage={r['coverage']:.4f} "
        f"tau={r['tau']} rows={r['n_rows']} leaves={r['n_leaves']}"
    )


if __name__ == "__main__":
    main()
