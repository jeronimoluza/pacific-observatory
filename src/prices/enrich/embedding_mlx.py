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

Two entry points:

  - one-shot ``python embedding_mlx.py <payload.json>`` (loads the model, embeds
    one payload, exits) — used for gold/small batches;
  - persistent ``python embedding_mlx.py --serve <model_id>`` — loads the model
    ONCE, then reads payload paths (one per line) on stdin and prints ``OK`` on
    stdout after writing each; used by the full-corpus block-outer driver so the
    7.5 GB 8B weights load once instead of per chunk. Progress goes to stderr so
    stdout carries only the ``READY``/``OK`` handshake.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _embed(generate, model, tok, names, prompt, chunk, seq, mx, np):
    n = len(names)
    if n == 0:
        return np.empty((0, 0), dtype="float32")
    # Length-sort before batching: HF pads each batch to its longest row, so
    # uniform-length batches slash padding waste (~2.3x fewer padded tokens on
    # this corpus). Pad tokens are attention-masked, so this changes only speed,
    # not the vectors. Scatter each batch back to its original position so row i
    # still maps to names[i].
    order = np.argsort(
        [len(tok(prompt + x)["input_ids"]) for x in names], kind="stable"
    )
    out = None
    done = 0
    for start in range(0, n, chunk):
        idx = order[start : start + chunk]
        batch = [names[i] for i in idx]
        emb = generate(model, tok, [prompt + x for x in batch], max_length=seq)
        vecs = emb.text_embeds if hasattr(emb, "text_embeds") else emb
        v = np.array(vecs.astype(mx.float32))
        v = v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12)
        if out is None:
            out = np.empty((n, v.shape[1]), dtype="float32")
        out[idx] = v.astype(np.float32)
        done += len(idx)
        print(f"  embedded {done}/{n}", file=sys.stderr, flush=True)
    return out


def _write(out, names, mat, np) -> None:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".npz.tmp")
    with open(tmp, "wb") as f:  # file handle => numpy won't append ".npz"
        np.savez(f, keys=np.array(names), mat=mat)
    tmp.replace(out)


def _run_payload(generate, model, tok, np, mx, payload: dict) -> int:
    names = list(dict.fromkeys(payload["names"]))  # de-dup, order-preserved
    mat = _embed(
        generate,
        model,
        tok,
        names,
        payload["prompt"],
        int(payload.get("chunk", 32)),
        int(payload.get("seq", 512)),
        mx,
        np,
    )
    _write(payload["out"], names, mat, np)
    return len(names)


def main(payload_path: str) -> None:
    import mlx.core as mx
    import numpy as np
    from mlx_embeddings import generate, load

    payload = json.loads(Path(payload_path).read_text())
    model, tok = load(payload["model"])
    n = _run_payload(generate, model, tok, np, mx, payload)
    print(f"DONE {n} -> {payload['out']}", flush=True)


def serve(model_id: str) -> None:
    import mlx.core as mx
    import numpy as np
    from mlx_embeddings import generate, load

    model, tok = load(model_id)
    print("READY", flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line or line == "__STOP__":
            break
        payload = json.loads(Path(line).read_text())
        _run_payload(generate, model, tok, np, mx, payload)
        print("OK", flush=True)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--serve":
        serve(sys.argv[2])
    else:
        main(sys.argv[1])
