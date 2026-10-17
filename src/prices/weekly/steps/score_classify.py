"""Step `score_classify` (W42 runbook step 11, was ~/scratch/w42_score/chain.sh + w42_classify/check.py).

1. snapshot: `_hierlex_pred` and `enrich/cache` copied to the 5TB with sha256 per
   file; refuses when the snapshot target exists and differs (kept when it matches).
2. score from this week's delta store (append-only; PRICES_EMBED_STORE_DIR is set
   for that process only). Skipped only when the embed step found nothing to embed.
3. extract: names of pairs still unscored are old names in new (name, country) pairs;
   their vectors are copied from the configured stores into this week's old store, so
   this works without ~/data/embed_store as long as some configured store holds them.
4. score again from that old store, if anything was copied.
5. verify: every pre-score pred row is unchanged; prints pairs left unscored.
6. classify per country (`prices process --stage classify --backend hierlex --only
   <region/subregion/country>`), one process each, log per country.
7. check: every prepared key has exactly one decision, one bundle, one tau.

`--countries` scopes classify and check. Score, extract and verify have no country
filter: they cover every (name, country) pair in `_prepared`.
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from prices.weekly import embed_stores
from prices.weekly.status import Status
from prices.weekly.step import REPO_ROOT
from prices.weekly.steps import _common

MODULE = "prices.weekly.steps.score_classify"
SCORE_WORKERS = 2


def _paths():
    from prices.enrich import config
    from prices.enrich.prepare_shards import PREPARED_DIR

    e = config.ENRICH_DIR
    return (
        e,
        PREPARED_DIR,
        e / "_hierlex_pred",
        e / "cache",
        e / "cache" / "decisions_hierlex",
    )


def _version() -> str:
    from prices.enrich.hierlex import package

    return package.manifest(package.resolve(None))["method_version"]


def _shas(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        out[str(p.relative_to(root))] = h.hexdigest()
    return out


def snapshot(src: Path, dst: Path) -> None:
    if not src.exists():
        # A fresh tree (first classify) has no cache yet: nothing to protect.
        print(f"snapshot {src}: absent, nothing to copy", flush=True)
        return
    if dst.exists():
        # A re-run after a later phase failed: keep a snapshot that still matches.
        if _shas(src) == _shas(dst):
            print(f"snapshot {dst} exists and matches {src}, kept", flush=True)
            return
        raise SystemExit(f"snapshot target exists and differs: {dst}")
    dst.mkdir(parents=True)
    subprocess.run(["rsync", "-rt", f"{src}/", f"{dst}/"], check=True)
    a, b = _shas(src), _shas(dst)
    if a != b:
        raise SystemExit(f"snapshot sha differs: {dst} ({len(a)} vs {len(b)} files)")
    print(f"snapshot {src} -> {dst}: {len(a)} files, sha256 equal", flush=True)


def score() -> int:
    from prices.enrich.classifier import embed_store
    from prices.enrich.hierlex import driver

    _common.setup_logging()
    _, prepared, pred, _, _ = _paths()
    print("STORE", embed_store.STORE_DIR, flush=True)
    assert str(embed_store.STORE_DIR) == os.environ["PRICES_EMBED_STORE_DIR"]
    s = driver.run(
        products_path=prepared, pred_root=pred, workers=SCORE_WORKERS, append_only=True
    )
    print("SCORE_DONE", json.dumps(s), flush=True)
    return 0


def extract(week: str) -> int:
    import pandas as pd

    _, _, pred_root, _, _ = _paths()
    pred = pred_root / _version()
    cfg = embed_stores.load(week)
    embed_stores.require_present(cfg.stores)
    t = time.time()
    want, npairs = {}, 0
    for b in range(256):
        pairs = pd.read_parquet(pred / f"_pairs/pairs_{b:03d}.parquet")
        sh = pd.read_parquet(
            pred / f"pred_{b:03d}.parquet", columns=["name", "country"]
        )
        have = set(zip(sh["name"].astype(str), sh["country"].astype(str)))
        todo = [
            (n, c)
            for n, c in zip(pairs["name"].astype(str), pairs["country"].astype(str))
            if (n, c) not in have
        ]
        npairs += len(todo)
        if todo:
            want[b] = {n for n, _ in todo}
    print(
        "unscored pairs",
        npairs,
        "names",
        sum(len(v) for v in want.values()),
        flush=True,
    )
    tot, absent = embed_stores.copy_vectors(want, cfg.stores, cfg.old_store, cfg.tags)
    print(
        "EXTRACT_DONE pairs",
        npairs,
        json.dumps(tot),
        "absent",
        len(absent),
        [repr(n)[:60] for n in absent[:10]],
        f"{time.time() - t:.0f}s",
        flush=True,
    )
    return 0


def verify(snap: Path) -> int:
    import pandas as pd

    _, _, pred_root, _, _ = _paths()
    version = _version()
    new, old = pred_root / version, snap / version
    tot = dict(old_rows=0, old_missing_or_changed=0, new_rows=0, pairs=0, unscored=0)
    uns = []
    for b in range(256):
        o = pd.read_parquet(old / f"pred_{b:03d}.parquet")
        n = pd.read_parquet(new / f"pred_{b:03d}.parquet")
        head = n.iloc[: len(o)].reset_index(drop=True)
        if not head.equals(o.reset_index(drop=True)):
            m = o.merge(
                n.drop_duplicates(["name", "country"]), how="left", indicator=True
            )
            tot["old_missing_or_changed"] += int((m["_merge"] != "both").sum())
        tot["old_rows"] += len(o)
        tot["new_rows"] += len(n) - len(o)
        p = pd.read_parquet(new / f"_pairs/pairs_{b:03d}.parquet")
        have = set(zip(n["name"].astype(str), n["country"].astype(str)))
        left = [
            (a, c)
            for a, c in zip(p["name"].astype(str), p["country"].astype(str))
            if (a, c) not in have
        ]
        tot["pairs"] += len(p)
        tot["unscored"] += len(left)
        uns += left
        if b % 64 == 0:
            print(b, tot, flush=True)
    print("VERIFY", json.dumps(tot), [repr(x)[:70] for x in uns[:10]], flush=True)
    return 0 if tot["old_missing_or_changed"] == 0 else 1


def classify_one(key: str) -> int:
    from prices.enrich.cli import process_command

    _common.setup_logging()
    process_command.main(
        args=["--stage", "classify", "--backend", "hierlex", "--only", key],
        standalone_mode=False,
    )
    return 0


def check(countries: list[str] | None) -> int:
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    _, prepared, _, _, dec = _paths()
    files = _common.prepared_files(prepared, countries)
    scope = {p.stem for p in files}
    last = {}
    for line in open(dec / "_decide.jsonl"):
        r = json.loads(line)
        for c in r["countries"]:
            if c in scope:
                last[c] = r
    runs = list({id(r): r for r in last.values()}.values())
    st = collections.Counter()
    for r in runs:
        st.update(r["states"])
    bundles, taus = {r["bundle"] for r in runs}, {r["tau"] for r in runs}
    print(
        "decide records", len(runs), "countries", len(last), bundles, taus, flush=True
    )
    print(
        "states", dict(st), "decisions", sum(r["decisions"] for r in runs), flush=True
    )
    tot = missing = dupd = extra = 0
    unsc = collections.Counter()
    nodec = []
    for p in files:
        c = p.stem
        pk = set(pq.read_table(p, columns=["input_hash"])["input_hash"].to_pylist())
        f = dec / f"{c}.parquet"
        if not f.exists():
            nodec.append(c)
            missing += len(pk)
            tot += len(pk)
            continue
        t = pq.read_table(f, columns=["input_hash", "state"])
        h = t["input_hash"].to_pylist()
        dk = set(h)
        dupd += len(h) - len(dk)
        tot += len(pk)
        missing += len(pk - dk)
        extra += len(dk - pk)
        n = pc.sum(pc.equal(t["state"], "unscored")).as_py() or 0
        if n:
            unsc[c] = n
    print(
        "input keys",
        tot,
        "without decision",
        missing,
        "decisions not in input",
        extra,
        "dup decision keys",
        dupd,
        flush=True,
    )
    print("countries without a part", nodec, flush=True)
    print("unscored rows", sum(unsc.values()), dict(unsc), flush=True)
    ok = missing == 0 and dupd == 0 and len(bundles) == 1 and len(taus) == 1
    return 0 if ok else 1


def _embed_universe(week: str) -> int | None:
    from prices.weekly.steps.embed import out_dir

    f = out_dir(week) / "need_summary.json"
    if not f.exists():
        return None
    s = json.loads(f.read_text())
    return s["need"] - s.get("need_garbage", 0)


def _classify_all(args, status: Status, countries: list[str] | None) -> int:
    _, prepared, _, _, _ = _paths()
    files = _common.prepared_files(prepared, countries)
    logs = args.week_dir / "classify"
    logs.mkdir(parents=True, exist_ok=True)
    failed = []
    for p in files:
        key = str(p.relative_to(prepared).with_suffix(""))
        s = time.time()
        with open(logs / f"{key.replace('/', '_')}.log", "a") as out:
            argv = [
                "env",
                f"PYTHONPATH={REPO_ROOT / 'src'}",
                sys.executable,
                "-u",
                "-m",
                MODULE,
                "--week",
                args.week,
                "--week-dir",
                str(args.week_dir),
                "--phase",
                "classify",
                "--only",
                key,
            ]
            rc = subprocess.run(
                argv, cwd=REPO_ROOT, stdout=out, stderr=subprocess.STDOUT
            ).returncode
        print(f"{key} rc={rc} {time.time() - s:.0f}s", flush=True)
        if rc != 0:
            failed.append(key)
    if countries:
        missing = sorted(set(countries) - {p.stem for p in files})
        if missing:
            print(
                f"no prepared parquet, not classified: {', '.join(missing)}", flush=True
            )
    if failed:
        _common.say(
            status,
            f"classify FAILED in {len(failed)}/{len(files)}: {', '.join(failed)}",
        )
        return 1
    _common.say(status, f"classify {len(files)}/{len(files)} rc=0")
    return 0


def run(args, countries: list[str] | None) -> int:
    status = Status(args.week_dir, "score_classify")
    cfg = embed_stores.load(args.week)
    _, _, pred, cache, _ = _paths()
    snaps = args.backup_mount / "po_snapshots" / REPO_ROOT.name / args.week
    _common.say(status, f"snapshot pred + cache to {snaps}")
    snapshot(pred, snaps / "pred-prescore")
    snapshot(cache, snaps / "cache-preclassify")

    if cfg.week_store.is_dir():
        _common.say(status, f"score 1/2 from {cfg.week_store}")
        if _common.phase(
            MODULE, args, "score", env={"PRICES_EMBED_STORE_DIR": cfg.week_store}
        ):
            _common.say(status, "FAILED score from the week store")
            return 1
    else:
        n = _embed_universe(args.week)
        if n is None or n > 0:
            why = "embed step has not run" if n is None else f"{n} names to embed"
            _common.say(status, f"FAILED no week store {cfg.week_store} and {why}")
            return 1
        _common.say(status, "score 1/2 skipped: embed found nothing to embed")

    _common.say(status, f"extract old vectors for new pairs into {cfg.old_store}")
    if _common.phase(MODULE, args, "extract"):
        _common.say(status, "FAILED extract")
        return 1
    if cfg.old_store.is_dir():
        _common.say(status, f"score 2/2 from {cfg.old_store}")
        if _common.phase(
            MODULE, args, "score", env={"PRICES_EMBED_STORE_DIR": cfg.old_store}
        ):
            _common.say(status, "FAILED score from the old store")
            return 1

    _common.say(status, "verify old rows unchanged")
    if _common.phase(
        MODULE, args, "verify", "--snapshot", str(snaps / "pred-prescore")
    ):
        _common.say(status, "FAILED verify: old pred rows changed")
        return 1

    _common.say(status, "classify per country")
    if _classify_all(args, status, countries):
        return 1
    _common.say(status, "classify check")
    if _common.phase(MODULE, args, "check"):
        _common.say(
            status,
            "FAILED check: keys without decision, dup keys, or more than one bundle/tau",
        )
        return 1
    return 0


def main() -> int:
    ap = _common.parser("score_classify")
    ap.add_argument("--backup-mount", type=Path, default=Path("/mnt/backup5tb"))
    ap.add_argument("--snapshot", type=Path, default=None)
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    countries = _common.countries(args.countries)
    phases = {
        "score": score,
        "extract": lambda: extract(args.week),
        "verify": lambda: verify(args.snapshot),
        "classify": lambda: classify_one(args.only),
        "check": lambda: check(countries),
    }
    if args.phase:
        return phases[args.phase]()
    return run(args, countries)


if __name__ == "__main__":
    sys.exit(main())
