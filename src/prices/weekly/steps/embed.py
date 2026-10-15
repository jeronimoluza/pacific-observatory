"""Step `embed` (W42 runbook step 10, was ~/scratch/w42_embed/{part,need,verify,build_kit}.py).

What it does, read-only on every store:
1. part: distinct (name, source, country) of the prepared parquets in scope, 2M rows
   at a time, bucketed with `embed_store.bucket_of`, spilled into 16 bucket groups.
2. need: per bucket, names minus those held in ALL of the configured tags by the
   UNION of the configured stores (`embed_stores.yaml`, or PRICES_EMBED_STORES),
   plus this week's delta store if it already exists.
3. verify: the 20 sampled need names are in no store, the 20 sampled covered names
   are in all tags of some store, looked up through `embed_store.keys_of`.
4. universe (need minus garbage names) and a per-pod plan from fleet/plan.py.

It rents nothing. The fleet is started by hand from the printed commands
(`src/prices/enrich/gpu/fleet/`), because pods cost money.

Outputs: data/prices/enrich/_embed_need/<week>/{need.parquet, samples.parquet,
need_summary.json, universe.parquet, pods.plan}. Refuses to run over an existing need.

`--phase assemble --names <parquet with name,bucket> --dst <new store>` copies those
names' vectors from the configured stores into a new store (the panel's local store).
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from prices.weekly import embed_stores
from prices.weekly.status import Status
from prices.weekly.step import REPO_ROOT
from prices.weekly.steps import _common

MODULE = "prices.weekly.steps.embed"
GROUPS = 16
BATCH_ROWS = 2_000_000
PODS = 3
FLEET = REPO_ROOT / "src/prices/enrich/gpu/fleet"


def out_dir(week: str) -> Path:
    from prices.enrich import config

    return config.ENRICH_DIR / "_embed_need" / week


def garbage(n: str) -> str:
    if n == "":
        return "empty"
    if "\x00" in n:
        return "nul"
    if n == "None":
        return "None_from_null"
    if not n.strip():
        return "whitespace"
    if len(n) > 500:
        return "too_long"
    if not any(c.isalnum() for c in n):
        return "no_alnum"
    return ""


def part(files: list[Path], parts: Path) -> dict:
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    from prices.enrich.classifier.embed_store import bucket_of

    stats = {"files": len(files), "rows": 0, "null_names": 0, "pairs": 0}
    cols = ["product_name_original", "source", "country"]
    for f in files:
        pf = pq.ParquetFile(f)
        for i, rb in enumerate(pf.iter_batches(batch_size=BATCH_ROWS, columns=cols)):
            t = pa.Table.from_batches([rb])
            stats["rows"] += t.num_rows
            stats["null_names"] += t["product_name_original"].null_count
            g = t.group_by(cols).aggregate([([], "count_all")])
            # key exactly as embed_store does: str(name); a null would become "None"
            names = [str(n) for n in g["product_name_original"].to_pylist()]
            bk = pa.array([bucket_of(n) for n in names], pa.int16())
            out = pa.table(
                {
                    "name": names,
                    "source": g["source"],
                    "country": g["country"],
                    "rows": g["count_all"],
                    "bucket": bk,
                }
            )
            stats["pairs"] += out.num_rows
            grp = pc.divide(out["bucket"], pa.scalar(GROUPS, pa.int16()))
            for k in range(GROUPS):
                d = parts / f"g{k:02d}"
                d.mkdir(parents=True, exist_ok=True)
                pq.write_table(
                    out.filter(pc.equal(grp, k)), d / f"{f.stem}.{i:04d}.parquet"
                )
            print(f.stem, i, t.num_rows, out.num_rows, flush=True)
            del t, g, out, names
    print("PART_DONE", json.dumps(stats), flush=True)
    return stats


def _keys(root: Path, tag: str, b: int) -> set[str]:
    import numpy as np

    from prices.enrich.classifier.embed_store import decode_keys

    p = root / tag / f"bucket_{b:03d}.npz"
    if not p.exists():
        return set()
    with np.load(p, allow_pickle=False) as z:
        return set(decode_keys(z))


def need(
    parts: Path, out: Path, stores: list[tuple[str, Path]], tags: list[str]
) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq

    first = stores[0][0]
    rng = random.Random(42)
    store_counts = {s: {t: 0 for t in tags} for s, _ in stores}
    tot = defaultdict(int)
    need_cols = defaultdict(list)
    cov_extra = defaultdict(int)  # covered by the union but not by the first store
    cov_res, need_res = [], []
    nseen_cov = nseen_need = 0
    for g in range(GROUPS):
        gdir = parts / f"g{g:02d}"
        if not gdir.exists():
            continue
        t = pq.read_table(gdir)
        cols = {
            c: t[c].to_pylist() for c in ["name", "source", "country", "rows", "bucket"]
        }
        per = defaultdict(dict)  # bucket -> name -> [rows, countries, sources]
        for n, s, c, r, b in zip(
            cols["name"], cols["source"], cols["country"], cols["rows"], cols["bucket"]
        ):
            d = per[b].get(n)
            if d is None:
                d = per[b][n] = [0, set(), set()]
            d[0] += r
            d[1].add(c)
            d[2].add(s)
        del t, cols
        for b in range(g * GROUPS, g * GROUPS + GROUPS):
            names = per.get(b, {})
            nameset = set(names)
            tot["distinct"] += len(nameset)
            have = {}
            for s, root in stores:
                for tg in tags:
                    k = _keys(root, tg, b)
                    store_counts[s][tg] += len(k)
                    have[(s, tg)] = nameset & k
                    del k
            union = {
                tg: set().union(*(have[(s, tg)] for s, _ in stores)) for tg in tags
            }
            first_all = set.intersection(*(have[(first, tg)] for tg in tags))
            covered = set.intersection(*(union[tg] for tg in tags))
            tot["covered"] += len(covered)
            tot[f"covered_by_{first}"] += len(first_all)
            for n in covered - first_all:
                full = [s for s, _ in stores if all(n in have[(s, tg)] for tg in tags)]
                cov_extra[
                    ",".join(full) if full else "MIXED(no single store holds all tags)"
                ] += 1
            for n in covered:
                nseen_cov += 1
                if len(cov_res) < 20:
                    cov_res.append(n)
                elif rng.random() < 20 / nseen_cov:
                    cov_res[rng.randrange(20)] = n
            for n in nameset - covered:
                r, cs, ss = names[n]
                need_cols["product_name_original"].append(n)
                need_cols["bucket"].append(b)
                for tg in tags:
                    need_cols[f"miss_{tg}"].append(n not in union[tg])
                need_cols["n_rows"].append(r)
                need_cols["countries"].append(sorted(cs))
                need_cols["sources"].append(sorted(ss))
                need_cols["garbage"].append(garbage(n))
                nseen_need += 1
                if len(need_res) < 20:
                    need_res.append(n)
                elif rng.random() < 20 / nseen_need:
                    need_res[rng.randrange(20)] = n
        print("group", g, dict(tot), flush=True)

    schema = pa.schema(
        [
            ("product_name_original", pa.string()),
            ("bucket", pa.int64()),
            *[(f"miss_{tg}", pa.bool_()) for tg in tags],
            ("n_rows", pa.int64()),
            ("countries", pa.list_(pa.string())),
            ("sources", pa.list_(pa.string())),
            ("garbage", pa.string()),
        ]
    )
    table = pa.table({f.name: need_cols[f.name] for f in schema}, schema=schema)
    pq.write_table(table, out / "need.parquet", compression="zstd")
    pq.write_table(
        pa.table(
            {
                "name": need_res + cov_res,
                "expect": ["need"] * len(need_res) + ["covered"] * len(cov_res),
            }
        ),
        out / "samples.parquet",
    )
    summary = {
        "totals": dict(tot),
        "need": table.num_rows,
        "need_garbage": sum(1 for x in need_cols["garbage"] if x),
        f"covered_not_in_{first}": dict(cov_extra),
        "store_key_counts": store_counts,
        "stores": {s: str(r) for s, r in stores},
    }
    (out / "need_summary.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False)
    )
    print("NEED_DONE", json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


def verify_samples(out: Path, stores: list[tuple[str, Path]], tags: list[str]) -> int:
    import pyarrow.parquet as pq

    from prices.enrich.classifier import embed_store as es

    bad = 0
    for r in pq.read_table(out / "samples.parquet").to_pylist():
        n, b = r["name"], es.bucket_of(r["name"])
        hits = {}
        for s, root in stores:
            es.STORE_DIR = root
            hits[s] = [tg for tg in tags if n in es.keys_of(tg, b)]
        full = all(any(tg in h for h in hits.values()) for tg in tags)
        ok = (not full) if r["expect"] == "need" else full
        bad += not ok
        where = {k: v for k, v in hits.items() if v}
        print("OK " if ok else "BAD", r["expect"], b, repr(n[:70]), where, flush=True)
    print("VERIFY_DONE bad=", bad, flush=True)
    return bad


def universe(out: Path, pods: int) -> int:
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    t = pq.read_table(out / "need.parquet")
    keep = t.filter(pc.equal(t["garbage"], ""))
    uni = keep.select(["product_name_original", "bucket"])
    path = out / "universe.parquet"
    pq.write_table(uni, path)
    print(
        "universe",
        uni.num_rows,
        "dropped as garbage",
        t.num_rows - keep.num_rows,
        flush=True,
    )
    if uni.num_rows:
        with open(out / "pods.plan", "w") as f:
            subprocess.run(
                [sys.executable, str(FLEET / "plan.py"), "--pods", str(pods)],
                env={**os.environ, "EMBED_UNIVERSE": str(path)},
                stdout=f,
                check=True,
            )
    return uni.num_rows


def _store_list(cfg: embed_stores.Stores) -> list[tuple[str, Path]]:
    stores = list(cfg.stores)
    if cfg.week_store.is_dir():
        stores.append(("week", cfg.week_store))
    return stores


def run(args, countries: list[str] | None) -> int:
    from prices.enrich.prepare_shards import PREPARED_DIR

    status = Status(args.week_dir, "embed")
    cfg = embed_stores.load(args.week)
    embed_stores.require_present(cfg.stores)
    stores = _store_list(cfg)
    out = out_dir(args.week)
    if (out / "need.parquet").exists():
        _common.say(status, f"FAILED {out}/need.parquet exists; refusing to overwrite")
        return 1
    out.mkdir(parents=True, exist_ok=True)
    files = _common.prepared_files(PREPARED_DIR, countries)
    print(
        f"stores from {cfg.config}: " + ", ".join(f"{s}={r}" for s, r in stores),
        flush=True,
    )
    parts = out / "_parts"
    if parts.exists():
        _common.say(
            status, f"FAILED {parts} exists (an interrupted run); move it aside first"
        )
        return 1
    _common.say(status, f"part {len(files)} prepared files")
    part(files, parts)
    _common.say(status, f"need over {len(stores)} stores")
    summary = need(parts, out, stores, cfg.tags)
    shutil.rmtree(parts)
    bad = verify_samples(out, stores, cfg.tags)
    if bad:
        _common.say(status, f"FAILED sample check bad={bad}")
        return 1
    n = universe(out, PODS)
    _common.say(status, f"need {summary['need']}, universe {n} names, out {out}")
    if n:
        _print_fleet(out, cfg, args.week)
    return 0


def _print_fleet(out: Path, cfg: embed_stores.Stores, week: str) -> None:
    pods = [
        line.split("\t")[0]
        for line in (out / "pods.plan").read_text().splitlines()
        if line.strip()
    ]
    env = (
        f"PODS_FILE={out}/pods.txt KIT={out}/kit.tar.gz UNIVERSE_NAME=universe.parquet"
        f" DEST={cfg.week_store}"
    )
    cmds = [
        f"{FLEET}/kit.sh {out}/universe.parquet {out}/kit.tar.gz",
        "asm-exec -- env RUNPOD_API_KEY='{{resolve:secretsmanager:<secret-id>:SecretString:<key>}}' "
        f"python {FLEET}/pods.py --work {out} create --plan {out}/pods.plan --gpu '<GPU id>'  # add --yes after the price check",
        *[
            f"systemd-run --user --collect --unit=po-embed-{week}-{p} -p MemoryMax=2G "
            f"env {env} {FLEET}/run_pod.sh {p}"
            for p in pods
        ],
        f"PODS_FILE={out}/pods.txt {FLEET}/monitor.sh  # then ls {out}/finish/READY_*",
        f"asm-exec -- env RUNPOD_API_KEY=... python {FLEET}/pods.py --work {out} delete <ids with READY_>",
        f"{FLEET}/backup.sh {cfg.week_store} {cfg.backup_root}/{week} {len(cfg.tags) * 256}",
    ]
    print("nothing rented. To embed the universe:", flush=True)
    for c in cmds:
        print(f"    {c}", flush=True)


def assemble(args) -> int:
    import pyarrow.parquet as pq

    if not (args.names and args.dst):
        raise SystemExit("--phase assemble needs --names and --dst")
    cfg = embed_stores.load(args.week)
    embed_stores.require_present(cfg.stores)
    t = pq.read_table(args.names, columns=["name", "bucket"]).to_pydict()
    want = defaultdict(set)
    for n, b in zip(t["name"], t["bucket"]):
        want[int(b)].add(n)
    tot, absent = embed_stores.copy_vectors(dict(want), cfg.stores, args.dst, cfg.tags)
    print(
        "ASSEMBLE_DONE names",
        sum(len(v) for v in want.values()),
        json.dumps(tot),
        "absent",
        len(absent),
        [repr(n)[:60] for n in absent[:10]],
        flush=True,
    )
    return 0


def main() -> int:
    ap = _common.parser("embed")
    ap.add_argument("--names", type=Path, default=None)
    ap.add_argument("--dst", type=Path, default=None)
    args = ap.parse_args()
    if args.phase == "assemble":
        return assemble(args)
    return run(args, _common.countries(args.countries))


if __name__ == "__main__":
    sys.exit(main())
