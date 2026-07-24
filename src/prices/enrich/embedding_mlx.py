"""mlx_embeddings encoder — the subprocess worker `embedding.py` shells out to.

Runs under the sibling `.venv_mlx` (py3.12 + mlx_embeddings), NOT the main venv.
It is invoked as a script — never imported by the pipeline — so the heavy `mlx`
imports live inside `main()` and importing this module elsewhere is a no-op.

Contract (stdin/stdout-free, file-based so large batches never hit argv limits):

    python embedding_mlx.py <payload.json>

    payload.json = {"model": <hf id>, "prompt": <str>, "names": [<str>...],
                    "out": <path to write>}

Writes an `.npz` at `out` with `keys` (the names, order-preserved) and `mat`
(one row per name, per-row L2-normalized float32). This is the faithful backend
that reproduced the prod cov@98 exactly (cos 0.9998 vs sentence-transformers) and
is the only one that fits the 8B in 16GB (via the q8 build).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(payload_path: str) -> None:
    import mlx.core as mx
    import numpy as np
    from mlx_embeddings import generate, load

    payload = json.loads(Path(payload_path).read_text())
    model_id = payload["model"]
    prompt = payload["prompt"]
    names = list(dict.fromkeys(payload["names"]))  # de-dup, order-preserved
    out = Path(payload["out"])
    chunk = int(payload.get("chunk", 32))
    seq = int(payload.get("seq", 512))

    model, tok = load(model_id)
    rows: list = []
    for start in range(0, len(names), chunk):
        batch = names[start : start + chunk]
        emb = generate(model, tok, [prompt + n for n in batch], max_length=seq)
        vecs = emb.text_embeds if hasattr(emb, "text_embeds") else emb
        v = np.array(vecs.astype(mx.float32))
        v = v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12)
        rows.append(v.astype(np.float32))
        print(f"  embedded {start + len(batch)}/{len(names)}", flush=True)

    mat = np.vstack(rows) if rows else np.empty((0, 0), dtype="float32")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".npz.tmp")
    with open(tmp, "wb") as f:  # file handle => numpy won't append ".npz"
        np.savez(f, keys=np.array(names), mat=mat)
    tmp.replace(out)
    print(f"DONE {len(names)} -> {out}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
