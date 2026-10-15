"""On a pod: check every bucket file of a range against the universe, print its sha256.

    python verify_pod.py <universe.parquet> <lo> <hi>
One line per (tag, bucket): tag bucket n_keys sha256 OK|BAD; then SUMMARY <names> bad <n>.
Keys must equal the universe's names for that bucket, once each; vectors float16,
finite, of the block's width. run_pod.sh compares the shas with what it pulled.
"""

import hashlib
import sys

import numpy as np
import pyarrow.parquet as pq

universe, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
DIMS = {"8b_bf16": 4096, "4b_bf16": 2560, "arctic_bf16": 1024}
t = pq.read_table(universe).to_pydict()
want = {}
for n, b in zip(t["product_name_original"], t["bucket"]):
    want.setdefault(int(b), set()).add(n)
bad = 0
for tag, dim in DIMS.items():
    for b in range(lo, hi + 1):
        p = f"data/prices/enrich/_embed_store/{tag}/bucket_{b:03d}.npz"
        try:
            with np.load(p, allow_pickle=False) as z:
                blob, off, mat = z["keys_blob"].tobytes(), z["keys_off"], z["mat"]
            keys = [
                blob[off[i] : off[i + 1]].decode("utf-8") for i in range(len(off) - 1)
            ]
            ok = (
                set(keys) == want.get(b, set())
                and len(keys) == len(set(keys))
                and mat.shape == (len(keys), dim)
                and mat.dtype == np.float16
                and bool(np.isfinite(mat).all())
            )
            sha = hashlib.sha256(open(p, "rb").read()).hexdigest()
            print(tag, b, len(keys), sha, "OK" if ok else "BAD")
            bad += not ok
        except Exception as e:
            print(tag, b, 0, "-", f"BAD:{type(e).__name__}")
            bad += 1
print("SUMMARY", sum(len(v) for k, v in want.items() if lo <= k <= hi), "bad", bad)
